import os
import shutil

from charmhelpers.core import hookenv

from charms.reactive import when, when_not, set_state

from charms.layer.ksql import KSQL_PORT


@when('local-monitors.available')
def local_monitors_available(nagios):
    setup_nagios(nagios)


@when('nrpe-external-master.available')
def nrpe_external_master_available(nagios):
    setup_nagios(nagios)


def setup_nagios(nagios):
    config = hookenv.config()
    unit_name = hookenv.local_unit()
    checks = [{
        'name': 'ksql_webservice_status',
        'description': 'Status code when returning /info for the ksql server',
        'crit': 'val != 200',
        'action': 'ksql_status',
        'opts': {
            'host': 'http://{addr}:{port}'.format(
                addr=hookenv.unit_private_ip(),
                port=KSQL_PORT
            )
        }
    }]

    check_cmd = [
        'python3', '/usr/local/lib/nagios/plugins/check_ksql.py'
    ]

    for check in checks:
        cmd = check_cmd

        if 'warn' in check:
            cmd += ['-w', "'{}'".format(check['warn'])]
        if 'crit' in check:
            cmd += ['-c', "'{}'".format(check['crit'])]

        cmd += [check['action']]
        if 'opts' in check:
            for key, val in check['opts'].items():
                cmd += ['--{}'.format(key), val]

        nagios.add_check(
            cmd,
            name=check['name'],
            description=check['description'],
            context=config['nagios_context'],
            servicegroups=(
                config.get('nagios_servicegroups') or config['nagios_context']
            ),
            unit=unit_name
        )
    nagios.updated()
    set_state('ksql.nrpe_helper.registered')


@when('ksql.nrpe_helper.registered')
@when_not('ksql.nrpe_helper.installed')
def install_nrpe_helper():
    dst_dir = '/usr/local/lib/nagios/plugins/'
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    src = '{}/files/check_ksql.py'.format(hookenv.charm_dir())
    dst = '{}/check_ksql.py'.format(dst_dir)
    shutil.copy(src, dst)
    os.chmod(dst, 0o755)
    set_state('ksql.nrpe_helper.installed')
