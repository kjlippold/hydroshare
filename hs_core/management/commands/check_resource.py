"""This does a comprehensive test of a resource.

This checks:
* IRODS files
* IRODS AVU values
* Existence of Logical files
"""

from hs_core.management.utils import CheckResource, ResourceCommand


class Command(ResourceCommand):
    help = "Print results of testing resource integrity."

    def resource_action(self, resource, options):
        CheckResource(resource.short_id).test(self.logger, options)
