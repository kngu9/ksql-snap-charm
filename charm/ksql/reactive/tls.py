import os
import tempfile

from OpenSSL import crypto
from subprocess import check_call

from charms.layer import tls_client
from charms.layer.ksql import keystore_password, KSQL_SNAP_COMMON

from charms.reactive import (when, when_file_changed, remove_state,
                             when_not, set_state, set_flag)
from charms.reactive.helpers import data_changed

from charmhelpers.core import hookenv

from charmhelpers.core.hookenv import log


@when('certificates.available')
def send_data():
    # Request a server cert with this information.
    tls_client.request_client_cert(
        'system:snap-ksql',
        crt_path=os.path.join(
            KSQL_SNAP_COMMON,
            'etc',
            'client.crt',
        ),
        key_path=os.path.join(
            KSQL_SNAP_COMMON,
            'etc',
            'client.key'
        )
    )


@when_file_changed(
    os.path.join(KSQL_SNAP_COMMON, 'etc', 'ksql.client.jks'),
    os.path.join(KSQL_SNAP_COMMON, 'etc', 'ksql.client.truststore.jks')
)
def restart_when_keystore_changed():
    remove_state('ksql.configured')
    set_flag('ksql.force-reconfigure')


@when('tls_client.certs.changed')
def import_srv_crt_to_keystore():
    password = keystore_password()
    crt_path = os.path.join(
        KSQL_SNAP_COMMON,
        'etc',
        'client.crt'
    )
    key_path = os.path.join(
        KSQL_SNAP_COMMON,
        'etc',
        'client.key'
    )

    if os.path.isfile(crt_path) and os.path.isfile(key_path):
        with open(crt_path, 'rt') as f:
            cert = f.read()
            loaded_cert = crypto.load_certificate(
                crypto.FILETYPE_PEM,
                cert
            )
            if not data_changed(
                'ksql_client_certificate',
                cert
            ):
                log('server certificate of key file missing')
                return

        with open(key_path, 'rt') as f:
            loaded_key = crypto.load_privatekey(
                crypto.FILETYPE_PEM,
                f.read()
            )

        with tempfile.NamedTemporaryFile() as tmp:
            log('server certificate changed')

            keystore_path = os.path.join(
                KSQL_SNAP_COMMON,
                'etc',
                'ksql.client.jks'
            )

            pkcs12 = crypto.PKCS12Type()
            pkcs12.set_certificate(loaded_cert)
            pkcs12.set_privatekey(loaded_key)
            pkcs12_data = pkcs12.export(password)
            log('opening tmp file {}'.format(tmp.name))

            # write cert and private key to the pkcs12 file
            tmp.write(pkcs12_data)
            tmp.flush()

            log('importing pkcs12')
            # import the pkcs12 into the keystore
            check_call([
                'keytool',
                '-v', '-importkeystore',
                '-srckeystore', str(tmp.name),
                '-srcstorepass', password,
                '-srcstoretype', 'PKCS12',
                '-destkeystore', keystore_path,
                '-deststoretype', 'JKS',
                '-deststorepass', password,
                '--noprompt'
            ])
            os.chmod(keystore_path, 0o440)

            remove_state('tls_client.certs.changed')
            set_state('ksql.client.keystore.saved')


@when('tls_client.ca_installed')
@when_not('ksql.ca.keystore.saved')
def import_ca_crt_to_keystore():
    ca_path = '/usr/local/share/ca-certificates/{}.crt'.format(
        hookenv.service_name()
    )

    if os.path.isfile(ca_path):
        with open(ca_path, 'rt') as f:
            changed = data_changed('ca_certificate', f.read())

        if changed:
            ca_keystore = os.path.join(
                KSQL_SNAP_COMMON,
                'etc',
                'ksql.client.truststore.jks'
            )
            check_call([
                'keytool',
                '-import', '-trustcacerts', '-noprompt',
                '-keystore', ca_keystore,
                '-storepass', keystore_password(),
                '-file', ca_path
            ])
            os.chmod(ca_keystore, 0o440)

            remove_state('tls_client.ca_installed')
            set_state('ksql.ca.keystore.saved')
