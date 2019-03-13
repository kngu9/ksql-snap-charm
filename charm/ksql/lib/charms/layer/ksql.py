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

from charmhelpers.core import hookenv, host

KSQL_PORT=8086
KSQL_SNAP='ksql-server'
KSQL_SERVICE='snap.{}.ksql-server.service'.format(KSQL_SNAP)
KSQL_SNAP_COMMON='/var/snap/{}/common'.format(KSQL_SNAP)

class KSQL(object):
    def open_ports(self):
        hookenv.open_port(KSQL_PORT)
    
    def close_ports(self):
        hookenv.close_ports(KSQL_PORT)

    def configure(self, kafka_units, network_interface=None):
        kafka = []
        for unit in kafka_units:
            ip = resolve_private_address(unit['host'])
            zks.append("%s:%s" % (ip, unit['port']))
        kafka.sort()
        kafka_connect = ','.join(kafka)

        ip = get_ip_for_interface(network_interface) if network_interface else hookenv.unit_private_ip()
        
        context = {
            'bootstrap_servers': kafka_connect,
            'listener_addr': ':'.join([ip, str(KSQL_PORT)])
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
            perms=0o644
        )

        self.restart()

    def restart(self):
        self.stop()
        self.start()

    def start(self):
        host.service_start(KSQL_SERVICE)

    def stop(self):
        host.service_stop(KSQL_SERVICE)


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


def get_ip_for_interface(self, network_interface):
    """
    Helper to return the ip address of this machine on a specific
    interface.

    @param str network_interface: either the name of the
    interface, or a CIDR range, in which we expect the interface's
    ip to fall. Also accepts 0.0.0.0 (and variants, like 0/0) as a
    special case, which will simply return what you passed in.

    """
    if network_interface.startswith('0') or network_interface == '::':
        # Allow users to reset the charm to listening on any
        # interface.  Allow operators to specify this however they
        # wish (0.0.0.0, ::, 0/0, etc.).
        return network_interface

    # Is this a CIDR range, or an interface name?
    is_cidr = len(network_interface.split(".")) == 4 or len(
        network_interface.split(":")) == 8

    if is_cidr:
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            try:
                ip = netifaces.ifaddresses(interface)[2][0]['addr']
            except KeyError:
                continue

            if ipaddress.ip_address(ip) in ipaddress.ip_network(
                    network_interface):
                return ip

        raise Exception(
            u"This machine has no interfaces in CIDR range {}".format(
                network_interface))
    else:
        try:
            ip = netifaces.ifaddresses(network_interface)[2][0]['addr']
        except ValueError:
            raise BigtopError(
                u"This machine does not have an interface '{}'".format(
                    network_interface))
        return ip
