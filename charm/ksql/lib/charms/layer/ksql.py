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

import ipaddress
import os
import re
import shutil
import socket
import yaml
from pathlib import Path

from charmhelpers.core import hookenv, host
from charmhelpers.core.templating import render
from charmhelpers.core.hookenv import config

KSQL_PORT=8088
KSQL_SNAP='ksql-server'
KSQL_SERVICE='snap.{}.ksql-server.service'.format(KSQL_SNAP)
KSQL_SNAP_COMMON='/var/snap/{}/common'.format(KSQL_SNAP)
KSQL_CLUSTER_ID='production'

class Ksql(object):
    def __init__(self):
        self.cfg = config()

    def open_ports(self):
        hookenv.open_port(KSQL_PORT)
    
    def close_ports(self):
        hookenv.close_port(KSQL_PORT)

    def configure(self, kafka_units):
        kafka = []
        for unit in kafka_units:
            ip = resolve_private_address(unit['host'])
            kafka.append('{}:{}'.format(ip, unit['port']))
        kafka.sort()
        kafka_connect = ','.join(kafka)

        ip = hookenv.unit_private_ip()
        
        context = {
            'bootstrap_servers': kafka_connect,
            'listener_addr': ':'.join(['0.0.0.0', str(KSQL_PORT)]),
            # TODO: We should set this to be http if we're related to easyrsa automatically
            # Issue: https://github.com/cloud-green/ksql-snap-charm/pull/3
            'listener_protocol': self.cfg['ksql-listener-protocol'],
            'keystore_password': _read_keystore_password(),
            'snap_name': KSQL_SNAP,
            'use_ssl': self.cfg['use-ssl'],
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
            'ksql_cluster_id': KSQL_CLUSTER_ID
        }

        render(
            source='ksql-server.properties',
            target=os.path.join(KSQL_SNAP_COMMON, 'etc', 'ksql-server.properties'),
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
        self.stop()
        self.start()

    def start(self):
        host.service_start(KSQL_SERVICE)

    def stop(self):
        host.service_stop(KSQL_SERVICE)

    def version(self):
        with open('/snap/{}/current/meta/snap.yaml'.format(KSQL_SNAP), 'r') as f:
            meta = yaml.load(f)
        return meta.get('version')

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
            raise ValueError('Unable to resolve or guess IP from private-address: %s' % addr)
        return contained.groups(0).replace('-', '.')

def _read_keystore_password():
    path = os.path.join(
        KSQL_SNAP_COMMON,
        'etc',
        'keystore.secret'
    )
    password = Path(path).read_text()
    return password.rstrip()
