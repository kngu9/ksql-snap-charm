import os

from charms.layer.ksql import Ksql

from charmhelpers.core import hookenv, unitdata

from charms.reactive import remove_state, hook, set_state

from charmhelpers.core.hookenv import log


@hook('state-storage-attached')
def storage_attach():
    storageids = hookenv.storage_list('state')
    if not storageids:
        hookenv.status_set('blocked', 'cannot locate attached storage')
        return
    storageid = storageids[0]

    mount = hookenv.storage_get('location', storageid)
    if not mount:
        hookenv.status_set('blocked', 'cannot locate attached storage mount')
        return

    state_dir = os.path.join(mount, "state")
    unitdata.kv().set('ksql.storage.state_dir', state_dir)
    hookenv.log('Ksql storage attached at {}'.format(state_dir))

    remove_state('ksql.configured')
    set_state('ksql.storage.state.attached')


@hook('state-storage-detaching')
def storage_detaching():
    unitdata.kv().unset('ksql.storage.state_dir')
    Ksql().stop()

    log('log storage detatched, reconfiguring to use temporary storage')

    remove_state('ksql.configured')
    remove_state('ksql.storage.state.attached')
