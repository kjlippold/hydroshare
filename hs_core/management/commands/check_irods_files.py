# -*- coding: utf-8 -*-

"""
Check synchronization between iRODS and Django

This checks that:

1. every ResourceFile corresponds to an iRODS file
2. every iRODS file in {short_id}/data/contents corresponds to a ResourceFile
3. every iRODS directory {short_id} corresponds to a Django resource

* By default, prints errors on stdout.
* Optional argument --log instead logs output to system log.
"""

from hs_core.management.utils import check_irods_files, check_for_dangling_irods, ResourceCommand


class Command(ResourceCommand):
    help = "Check synchronization between iRODS and Django."

    def add_arguments(self, parser):

        print("adding default arguments.")
        super(Command, self).add_arguments(parser)

        # Named (optional) arguments
        parser.add_argument(
            '--sync_ispublic',
            action='store_true',  # True for presence, False for absence
            dest='sync_ispublic',
            help='synchronize iRODS isPublic AVU with Django',
        )
        parser.add_argument(
            '--clean_irods',
            action='store_true',  # True for presence, False for absence
            dest='clean_irods',
            help='delete unreferenced iRODS files',
        )
        parser.add_argument(
            '--clean_django',
            action='store_true',  # True for presence, False for absence
            dest='clean_django',
            help='delete unreferenced Django file objects',
        )
        # Named (optional) arguments
        parser.add_argument(
            '--unreferenced',
            action='store_true',  # True for presence, False for absence
            dest='unreferenced',
            help='check for unreferenced iRODS directories',
        )

    def handle(self, *args, **options):
        if options['unreferenced']:
            if options['verbose']:
                print("LOOKING FOR IRODS RESOURCES NOT IN DJANGO")
            check_for_dangling_irods(echo_errors=not options['log'],
                                     log_errors=options['log'],
                                     return_errors=False)

        else:
            if options['verbose']:
                print("LOOKING FOR FILE ERRORS FOR ALL RESOURCES")
                if options['clean_irods']:
                    print(' (deleting unreferenced iRODs files)')
                if options['clean_django']:
                    print(' (deleting Django file objects without files)')
                if options['sync_ispublic']:
                    print(' (correcting isPublic in iRODs)')
            # handle list of resources or all resources
            super(Command, self).handle(*args, **options)

    def resource_action(self, resource, options):
        if options['verbose']:
            self.log("LOOKING FOR FILE ERRORS FOR RESOURCE {}".format(resource.short_id), options)
        check_irods_files(resource, self.logger, options, return_errors=False)
