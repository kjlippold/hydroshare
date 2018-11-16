# -*- coding: utf-8 -*-

"""
Generate metadata and bag for a resource from Django

"""
from hs_core.management.utils import check_bag, ResourceCommand


class Command(ResourceCommand):
    help = "Create metadata files and bag for a resource."

    def add_arguments(self, parser):

        # add arguments from resource template
        super(Command, self).add_arguments(parser)

        # a list of resource id's, or none to check all resources
        parser.add_argument('resource_ids', nargs='*', type=str)

        # Named (optional) arguments

        parser.add_argument(
            '--reset',
            action='store_true',  # True for presence, False for absence
            dest='reset',  # value is options['reset']
            help='delete metadata and bag and start over'
        )

        parser.add_argument(
            '--reset_metadata',
            action='store_true',  # True for presence, False for absence
            dest='reset_metadata',  # value is options['reset_metadata']
            help='delete metadata files and start over'
        )

        parser.add_argument(
            '--reset_bag',
            action='store_true',  # True for presence, False for absence
            dest='reset_bag',  # value is options['reset_bag']
            help='delete bag and start over'
        )

        parser.add_argument(
            '--generate',
            action='store_true',  # True for presence, False for absence
            dest='generate',  # value is options['generate']
            help='force generation of metadata and bag'
        )

        parser.add_argument(
            '--generate_metadata',
            action='store_true',  # True for presence, False for absence
            dest='generate_metadata',  # value is options['generate_metadata']
            help='force generation of metadata and bag'
        )

        parser.add_argument(
            '--generate_bag',
            action='store_true',  # True for presence, False for absence
            dest='generate_bag',  # value is options['generate_bag']
            help='force generation of metadata and bag'
        )

        parser.add_argument(
            '--if_needed',
            action='store_true',  # True for presence, False for absence
            dest='if_needed',  # value is options['if_needed']
            help='generate only if not present'
        )

        parser.add_argument(
            '--download_bag',
            action='store_true',  # True for presence, False for absence
            dest='download_bag',  # value is options['download_bag']
            help='try downloading the bag'
        )

        parser.add_argument(
            '--open_bag',
            action='store_true',  # True for presence, False for absence
            dest='open_bag',  # value is options['open_bag']
            help='try opening the bag in http without downloading'
        )

        parser.add_argument(
            '--login',
            default='admin',
            dest='login',  # value is options['login']
            help='HydroShare login name'
        )

        parser.add_argument(
            '--password',
            default=None,
            dest='password',  # value is options['password']
            help='HydroShare password'
        )

    def resource_action(self, resource, options):
        check_bag(resource.short_id, options)
