"""This does a comprehensive test of a resource.

This checks:
* IRODS files
* IRODS AVU values
* Existence of Logical files

Notes:
* By default, this script prints errors on stdout.
* Optional argument --log: logs output to system log.
"""

from hs_core.management.utils import CheckResource, ResourceCommand


class Command(ResourceCommand):
    help = "Print results of testing resource integrity."

    def resource_action(self, resource):
        CheckResource(resource.short_id).test()
