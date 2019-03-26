from charms.layer.ksql import Ksql

from charmhelpers.core import hookenv

from charms.reactive import when, set_state, remove_state


@when('ksql.available')
def autostart_service():
    '''
    Attempt to restart the service if it is not running.
    '''
    ksql = Ksql()

    if ksql.is_running():
        hookenv.status_set('active', 'ready')
        return

    for i in range(3):
        hookenv.status_set(
            'maintenance',
            'attempting to restart ksql, '
            'attempt: {}'.format(i+1)
        )
        ksql.restart()
        if ksql.is_running():
            hookenv.status_set('active', 'ready')
            return

    hookenv.status_set('blocked', 'failed to start ksql; check syslog')
