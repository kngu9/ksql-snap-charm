# /usr/bin/python3

# Simple KSQL nagios utility plugin

import sys
import logging
import requests
import json

from argparse import ArgumentParser

__version__ = (0, 1, 0)


log = logging.getLogger()
logging.basicConfig(level=logging.ERROR)


class KSQLStatus(object):
    @classmethod
    def register_options(cls, parser):
        parser.add_argument(
            '--host', dest='host',
            required=True,
        )

    def __init__(self, args):
        self.args = args

    def execute(self):
        status_code = -1
        msg = None

        try:
            with requests.get('{}/info'.format(self.args.host)) as r:
                info = json.loads(r.content)
                status_code = r.status_code
                msg = 'cluster: {}'.format(
                    info['KsqlServerInfo']['ksqlServiceId']
                )
        except requests.ConnectionError:
            status_code = -1
            msg = 'connection error'
        except Exception as e:
            status_code = -1
            msg = 'exception: {}'.format(e)
        finally:
            return (status_code, msg)


actions = {
    'ksql_status': KSQLStatus
}


def get_version():
    return '.'.join(map(str, __version__))


def parse_cli():
    parser = ArgumentParser(
        prog='check_ksql.py',
        description='Simple KSQL nagios utility plugin',
    )

    parser.add_argument('--version', action='version', version=get_version())
    parser.add_argument('-w', '--warning', dest='warning')
    parser.add_argument('-c', '--critical', dest='critical')
    subparsers = parser.add_subparsers(
        help='perform specific check', dest='action'
    )

    for key, val in actions.items():
        action_parser = subparsers.add_parser(key)
        val.register_options(action_parser)

    return parser.parse_args()


def parse_criteria(val, criteria_str):
    res = eval(criteria_str, {
        'val': val
    })

    return res


def main():
    args = parse_cli()
    val, msg = actions[args.action](args).execute()

    status = 'OK'
    status_code = 0

    if args.warning:
        if parse_criteria(val, args.warning):
            status = 'WARNING'
            status_code = 1
    if args.critical:
        if parse_criteria(val, args.critical):
            status = 'CRITICAL'
            status_code = 2

    print(
        '{status} - {val}'.format(
            status=status,
            val=val
        ),
        end=''
    )

    if msg:
        print(' | {};'.format(msg))
    print()

    return status_code


if __name__ == '__main__':
    sys.exit(main())
