# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from charms.layer.ksql import Ksql

from charmhelpers.core import hookenv, unitdata

from charms.reactive import (set_state, remove_state, when, when_not,
                             hook, clear_flag, is_flag_set, set_flag)
from charms.reactive.helpers import data_changed


@hook('config-changed')
def config_changed():
    remove_state('ksql.configured')
    set_flag('ksql.force-reconfigure')


@when('snap.installed.ksql-server')
@when_not('ksql.configured')
def configure(kafka_units=None):
    ksql = Ksql()
    kafkas = kafka_units or ksql.get_kafkas()
    state_dir = unitdata.kv().get('ksql.storage.state_dir')
    changed = any((
       data_changed('ksql.kafka_units', kafkas),
       data_changed('ksql.storage.state_dir', state_dir)
    ))

    if changed or is_flag_set('ksql.force-reconfigure'):
        ksql.install(kafka_units=kafkas, state_dir=state_dir)
        ksql.open_ports()

    clear_flag('ksql.force-reconfigure')
    set_state('ksql.available')
    set_state('ksql.configured')

    hookenv.application_version_set(ksql.version())


@when('ksql.available')
@when_not('kafka.joined')
def waiting_for_kafka():
    ksql = Ksql()
    ksql.close_ports()
    ksql.stop()
    hookenv.status_set('blocked', 'waiting for relation to kafka')


@when_not(
    'ksql.ca.keystore.saved',
    'ksql.server.keystore.saved',
)
@when('ksql.available')
def waiting_for_certificates():
    hookenv.status_set('waiting', 'waiting for easyrsa relation')


@when(
    'ksql.available',
    'kafka.ready',
    'ksql.ca.keystore.saved',
    'ksql.client.keystore.saved'
)
@when_not('ksql.started')
def configure_ksql(kafka):
    hookenv.status_set('maintenance', 'setting up ksql')

    configure(kafka.kafkas())
    hookenv.status_set('active', 'ready')
