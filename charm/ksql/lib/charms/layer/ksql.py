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

import os
import re
import socket

from base64 import b64encode
from pathlib import Path

from charmhelpers.core import hookenv, host
from charmhelpers.core.templating import render
from charmhelpers.core.hookenv import config

from charms.reactive.relations import RelationBase

from charms.layer import snap

KSQL_PORT = 8088
KSQL_SNAP = 'ksql-server'
KSQL_SERVICE = 'snap.{}.ksql-server.service'.format(KSQL_SNAP)
KSQL_SNAP_COMMON = '/var/snap/{}/common'.format(KSQL_SNAP)
KSQL_KEYTOOL_PATH = ('/snap/{}/current/usr/lib/jvm/default-java'
                     '/bin/keytool').format(KSQL_SNAP)


class Ksql(object):
    def open_ports(self):
        '''
        Attempts to open the KSQL port.
        '''
        hookenv.open_port(KSQL_PORT)

    def close_ports(self):
        '''
        Attempts to close the Kafka port.
        '''
        hookenv.close_port(KSQL_PORT)

    def install(self, kafka_units=[]):
        '''
        Generates ksql-server.properties with the current system state.
        '''
        kafka = []
        for unit in kafka_units:
            ip = resolve_private_address(unit['host'])
            kafka.append('{}:{}'.format(ip, unit['port']))
        kafka.sort()
        kafka_connect = ','.join(kafka)

        context = {
            'bootstrap_servers': kafka_connect,
            'listener_addr': ':'.join([hookenv.unit_private_ip(),
                                       str(KSQL_PORT)]),
            'keystore_password': keystore_password(),
            'snap_name': KSQL_SNAP,
            'ca_keystore': os.path.join(
                KSQL_SNAP_COMMON,
                'etc',
                "ksql.client.jks"
            ),
            'client_keystore': os.path.join(
                KSQL_SNAP_COMMON,
                'etc',
                "ksql.client.truststore.jks"
            ),
            'ksql_cluster_id': config()['ksql-cluster-id']
        }

        render(
            source='ksql-server.properties',
            target=os.path.join(KSQL_SNAP_COMMON, 'etc',
                                'ksql-server.properties'),
            owner="root",
            perms=0o644,
            context=context
        )

        render(
            source='log4j.properties',
            target=os.path.join(KSQL_SNAP_COMMON, 'etc', 'log4j.properties'),
            owner="root",
            perms=0o644,
            context={}
        )

        self.restart()

    def restart(self):
        '''
        Restarts the KSQL service.
        '''
        host.service_restart(KSQL_SERVICE)

    def start(self):
        '''
        Starts the KSQL service.
        '''
        host.service_reload(KSQL_SERVICE)

    def stop(self):
        '''
        Stops the KSQL service.

        '''
        host.service_stop(KSQL_SERVICE)

    def is_running(self):
        '''
        Restarts the KSQL service.
        '''
        return host.service_running(KSQL_SERVICE)

    def get_kafkas(self):
        '''
        Will attempt to read kafka nodes from the kafka.joined state.

        If the flag has never been set, an empty list will be returned.
        '''
        kafka = RelationBase.from_flag('kafka.ready')
        if kafka:
            return kafka.kafkas()
        else:
            return []

    def version(self):
        '''
        Will attempt to get the version from the version field of the Ksql
        snap file.

        If there is a reader exception or a parser exception, unknown will
        be returned
        '''
        return snap.get_installed_version(KSQL_SNAP) or 'unknown'


def keystore_password():
    path = os.path.join(
        KSQL_SNAP_COMMON,
        "keystore.secret"
    )
    if not os.path.isfile(path):
        with os.fdopen(
                os.open(path, os.O_WRONLY | os.O_CREAT, 0o440),
                'wb') as f:
            token = b64encode(os.urandom(32))
            f.write(token)
            password = token.decode('ascii')
    else:
        password = Path(path).read_text().rstrip()
    return password


def resolve_private_address(addr):
    IP_pat = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
    contains_IP_pat = re.compile(r'\d{1,3}[-.]\d{1,3}[-.]\d{1,3}[-.]\d{1,3}')
    if IP_pat.match(addr):
        return addr  # already IP
    try:
        ip = socket.gethostbyname(addr)
        return ip
    except socket.error as e:
        hookenv.log(
            'Unable to resolve private IP: %s (will attempt to guess)' %
            addr,
            hookenv.ERROR
        )
        hookenv.log('%s' % e, hookenv.ERROR)
        contained = contains_IP_pat.search(addr)
        if not contained:
            raise ValueError(
                'Unable to resolve private-address: {}'.format(addr)
            )
        return contained.groups(0).replace('-', '.')
