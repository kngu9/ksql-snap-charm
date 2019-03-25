from charms.layer.ksql import Ksql, KSQL_PORT

from charms.reactive import (when, when_file_changed, remove_state,
                             when_not, set_state, set_flag)

@when('website.available', 'ksql.ready')
def setup_website(website):
    website.configure(KSQL_PORT)