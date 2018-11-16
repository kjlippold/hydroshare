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

from hs_core.management.utils import repair_resource, ResourceCommand


class Command(ResourceCommand):
    help = "Check synchronization between iRODS and Django."

    def resource_action(self, resource, options):

        _, count = repair_resource(resource, self.logger, options,
                                   return_errors=False)
        if count:
            msg = "... affected resource {} has type {}, title '{}'"\
                  .format(resource.short_id, resource.resource_type,
                          resource.title.encode('ascii', 'replace'))
            self.log_or_print(msg, options)
