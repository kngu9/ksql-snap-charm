from charms.layer.ksql import KSQL_PORT

from charms.reactive import when


@when('website.available', 'ksql.configured')
def setup_website(website):
    website.configure(KSQL_PORT)
