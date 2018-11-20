"""This prints the state of a logical file.

* By default, prints errors on stdout.
* Optional argument --log: logs output to system log.
"""
from hs_core.management.utils import debug_resource, ResourceCommand


class Command(ResourceCommand):
    help = "Print debugging information about resources."

    default_to_all = False

    def resource_action(self, resource, options):
        debug_resource(resource.short_id, self.logger, options)
