# -*- coding: utf-8 -*-

"""
Check relations

This checks that every relation to a resource refers to an existing resource
"""
from hs_core.management.utils import check_relations, ResourceCommand


class Command(ResourceCommand):
    help = "Check for dangling relationships among resources."

    def resource_action(self, resource, options):
        self.log_or_print_verbose("LOOKING FOR RELATION ERRORS FOR RESOURCE {}"
                                  .format(resource.short_id), options)
        check_relations(resource, self.logger, options)
