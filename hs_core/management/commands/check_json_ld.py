"""This does a comprehensive test of the json-ld of a resource

This loops through a list of resources and checks the ld+json
metadata against the official Google Structured testing tool.

Please note this requires setting the GOOGLE_COOKIE_HASH
directive inside local_settings.py
"""

from hs_core.management.utils import CheckJSONLD, ResourceCommand


class Command(ResourceCommand):
    help = "Checks resources for appropriate JSON returns"

    def resource_action(self, resource, options): 
        CheckJSONLD(resource.short_id).test(options)
