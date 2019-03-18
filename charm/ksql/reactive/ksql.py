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
import socket
import tempfile
import glob
import subprocess

from pathlib import Path
from OpenSSL import crypto
from subprocess import check_call

from charms.reactive import set_state, remove_state, when, when_not, hook, when_file_changed
from charmhelpers.core import hookenv
from charms.reactive.helpers import data_changed
from charmhelpers.core.hookenv import log, config

from charms.layer.ksql import KSQL_SNAP, KSQL_SNAP_COMMON, KSQL_PORT, Ksql
from charms.layer import tls_client

@when_not('ksql.available')
def install():
    install_snap()

@hook('upgrade-charm')
def upgrade():
    upgrade_snap()

@hook('stop')
def uninstall():
    try:
        check_call(['snap', 'remove', KSQL_SNAP])
    except subprocess.CalledProcessError as e:
        hookenv.log("failed to remove snap: {}".format(e))

def install_snap():
    cfg = config()
    # KSQL-Server's snap presedence is:
    # 1. Included in snap
    # 2. Included with resource of charm of 'ksql-server'
    # 3. Snap store with release channel specified in config
    snap_file = get_snap_file_from_charm() or hookenv.resource_get('ksql-server')
    if snap_file:
        check_call(['snap', 'install', '--dangerous', snap_file])
    if not snap_file:
        check_call(['snap', 'install', '--{}'.format(cfg['ksql-release-channel']), KSQL_SNAP])
    
    set_state('ksql.available')

def upgrade_snap():
    cfg = config()
    check_call(['snap', 'refresh', '--{}'.format(cfg['ksql-release-channel']), KSQL_SNAP])
    set_state('ksql.available')

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

    ksql = Ksql()
    ksql.configure(kafka.kafkas())
    ksql.open_ports()
    set_state('ksql.started')
    hookenv.status_set('active', 'ready')
    # set app version string for juju status output
    ksql_version = ksql.version() or 'unknown'
    hookenv.application_version_set(ksql_version)

@when_file_changed(
    os.path.join(KSQL_SNAP_COMMON, 'etc', "ksql.client.jks"),
    os.path.join(KSQL_SNAP_COMMON, 'etc', 'ksql-server.properties')
)
def restart_when_files_changed():
    hookenv.status_set('maintenance', 'restarting ksql')
    Ksql().restart()
    hookenv.status_set('active', 'ready')

@when('certificates.available')
def get_client_cert():
    # Request client certs from easyrsa
    tls_client.request_client_cert(
        'system:snap-ksql-server',
        crt_path=os.path.join(
            KSQL_SNAP_COMMON,
            'etc',
            'ksql-server.client.crt',
        ),
        key_path=os.path.join(
            KSQL_SNAP_COMMON,
            'etc',
            'client.key'
        )
    )

@when('tls_client.certs.changed')
def import_srv_crt_to_keystore():
    keystore_path = os.path.join(
        KSQL_SNAP_COMMON,
        'etc',
        "ksql.client.jks"
    )
    keystore_password = _keystore_password()
    crt_path = os.path.join(
        KSQL_SNAP_COMMON,
        'etc',
        'ksql-server.client.crt'
    )
    key_path = os.path.join(
        KSQL_SNAP_COMMON,
        'etc',
        "client.key"
    )
    if os.path.isfile(crt_path) and os.path.isfile(key_path):
        with open(crt_path, 'rt') as f:
            cert = f.read()
            loaded_cert = crypto.load_certificate(
                crypto.FILETYPE_PEM,
                cert
            )
        
        if not data_changed('ksql_ca_certificate', cert):
            return
        log('server certificate changed')

        with open(key_path, 'rt') as f:
            key = f.read()
            loaded_key = crypto.load_privatekey(
                crypto.FILETYPE_PEM,
                key
            )

        pkcs12 = crypto.PKCS12Type()
        pkcs12.set_certificate(loaded_cert)
        pkcs12.set_privatekey(loaded_key)
        pkcs12_data = pkcs12.export(keystore_password)
        fd, path = tempfile.mkstemp()
        log('opening tmp file {}'.format(path))
        try:
            with os.fdopen(fd, 'wb') as tmp:
                # write cert and private key to the pkcs12 file
                tmp.write(pkcs12_data)
                log('Writing pkcs12 temporary file {0}'.format(
                    path
                ))
                tmp.close()
                log('importing pkcs12')
                # import the pkcs12 into the keystore
                check_call(
                    '/snap/{snap_name}/current/usr/lib/jvm/default-java/bin/keytool -v -importkeystore -srckeystore {path} -srcstorepass {password} -srcstoretype PKCS12 -destkeystore {keystore} -deststoretype JKS -deststorepass {password} --noprompt'.format(
                        snap_name=KSQL_SNAP,
                        path=path,
                        password=keystore_password,
                        keystore=keystore_path
                    ),
                    shell=True
                )
                os.chmod(keystore_path, 0o440)
                remove_state('tls_client.certs.changed')
                set_state('ksql.client.keystore.saved')
        finally:
            os.remove(path)
    else:
        log('server certificate of key file missing'.format(
            cert=os.path.isfile(crt_path),
            key=os.path.isfile(key_path)
        ))


@when('tls_client.ca_installed')
@when_not('ksql.ca.keystore.saved')
def import_ca_crt_to_keystore():
    service_name = hookenv.service_name()
    ca_path = '/usr/local/share/ca-certificates/{0}.crt'.format(service_name)

    if os.path.isfile(ca_path):
        changed = False

        with open(ca_path, 'rt') as f:
            ca_cert = f.read()
            changed = data_changed('ca_certificate', ca_cert)

        if changed:
            ca_keystore = os.path.join(
                KSQL_SNAP_COMMON,
                'etc',
                "ksql.client.truststore.jks"
            )
            password = _keystore_password()
            check_call(
                '/snap/{snap_name}/current/usr/lib/jvm/default-java/bin/keytool -import -trustcacerts -keystore {keystore} -storepass  {keystorepass} -file {path} -noprompt'.format(
                    snap_name=KSQL_SNAP,
                    path=ca_path,
                    keystore=ca_keystore,
                    keystorepass=password
                ),
                shell=True
            )
            os.chmod(ca_keystore, 0o440)
            remove_state('tls_client.ca_installed')
            set_state('ksql.ca.keystore.saved')

def _keystore_password():
    path = os.path.join(
        KSQL_SNAP_COMMON,
        'etc',
        "keystore.secret"
    )
    if not os.path.isfile(path):
        _ensure_directory(path)
        check_call(
            ['head -c 32 /dev/urandom | base64 > {}'.format(path)],
            shell=True
        )
        os.chmod(path, 0o440)
    password = Path(path).read_text()
    return password.rstrip()


def _ensure_directory(path):
    '''Ensure the parent directory exists creating directories if necessary.'''
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    os.chmod(directory, 0o770)

def get_snap_file_from_charm():
    snap_files = sorted(glob.glob(os.path.join(hookenv.charm_dir(), "{}*.snap".format(KSQL_SNAP))))[::-1]
    if not snap_files:
        return None
    return snap_files[0]