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

from charms.layer.ksql import Ksql, KSQL_SNAP_COMMON

from charmhelpers.core import hookenv

from charms.reactive import (set_state, remove_state, when, when_not,
                             hook, clear_flag, is_flag_set, set_flag,
                             when_any)
from charms.reactive.helpers import data_changed

from charmhelpers.core.hookenv import log


@hook('config-changed')
def config_changed():
    remove_state('ksql.configured')
    set_flag('ksql.force-reconfigure')


@when('snap.installed.ksql-server')
@when_not('ksql.configured')
def configure():
    ksql = Ksql()
    kafkas = ksql.get_kafkas()

    if data_changed('ksql.kafka_units', kafkas) or is_flag_set('ksql.force-reconfigure'):
        ksql.install(kafka_units=kafkas)
        ksql.open_ports()

    clear_flag('ksql.force-reconfigure')
    set_state('ksql.available')
    set_state('ksql.configured')

    hookenv.application_version_set(ksql.version())


@when('snap.installed.ksql-server')
@when_not('ksql.client.keystore.saved')
def waiting_for_certificates():
    remove_state('ksql.available')
    hookenv.status_set('waiting', 'waiting for easyrsa relation')


@when('snap.installed.ksql-server')
@when_not('kafka.joined', 'kafka.joined')
def waiting_for_kafka():
    hookenv.status_set('waiting', 'waiting for kafka relation')


@when(
    'snap.installed.ksql-server',
    'ksql.ready',
    'ksql.client.keystore.saved'
)
@when_not('ksql.available')
def configure_kafka(kafka):
    hookenv.status_set('maintenance', 'setting up ksql')

    remove_state('ksql.configured')
    set_flag('ksql.force-reconfigure')


@when(
    'ksql.configured'
    'kafka.joined'
)
def configure_ksql_kafkas(kafka):
    """
    As kafka brokers come and go, ksql-server.properties will be updated.
    When that file changes, restart Kafka and set appropriate status messages.
    """
    kafkas = kafka.kafkas()

    if not data_changed('ksql.kafka_units', kafkas):
        return

    log('kafka(s) joined, forcing reconfiguration')
    remove_state('ksql.configured')
    set_flag('ksql.force-reconfigure')
