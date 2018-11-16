# -*- coding: utf-8 -*-

"""
Modify user paths for test environment.

For testing, user resources live in a different place than the default,
which is hard-coded into the django database.

* By default, prints errors on stdout.
* Optional argument --log instead logs output to system log.
"""


from django.conf import settings
from hs_core.management.utils import fix_irods_user_paths, ResourceCommand


class Command(ResourceCommand):
    help = "Modify user paths for test environment."

    def resource_action(self, resource, options):
        defaultpath = getattr(settings, 'HS_USER_ZONE_PRODUCTION_PATH',
                              '/hydroshareuserZone/home/localHydroProxy')

        if resource.resource_federation_path == defaultpath:
            self.log("REMAPPING RESOURCE {} TO LOCAL USERSPACE".format(resource.short_path))
            fix_irods_user_paths(resource, self.logger,
                                 echo_actions=not options['log'],
                                 log_actions=options['log'],
                                 return_actions=False)
        else:
            self.log_or_print_error("Resource with id {} is not a default userspace resource"
                                    .format(resource.short_path),
                                    options)
