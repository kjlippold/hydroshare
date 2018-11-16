# -*- coding: utf-8 -*-

"""
Check synchronization between iRODS and Django

This checks that every file in IRODS corresponds to a ResourceFile in Django.
If a file in iRODS is not present in Django, it attempts to register that file in Django.

* By default, prints errors on stdout.
* Optional argument --log instead logs output to system log.
"""

from hs_core.management.utils import ingest_irods_files, ResourceCommand


class Command(ResourceCommand):
    help = "Synchronize iRODS and Django concepts of files."

    def resource_action(self, resource, options):
        # Pabitra: Not sure why are we skipping other resource types
        # Alva: cannot preserve file integrity constraints for other file types.
        if resource.resource_type != 'CompositeResource' and \
           resource.resource_type != 'GenericResource' and \
           resource.resource_type != 'ModelInstanceResource' and \
           resource.resource_type != 'ModelProgramResource':
            if options['verbose']:
                self.log_or_print("resource {} has type {}: skipping"
                                  .format(resource.short_id, resource.resource_type),
                                  options)
        else:
            self.log_or_print_verbose("LOOKING FOR UNREGISTERED IRODS FILES FOR {} ({} files)"
                .format(resource.short_id, str(resource.files.all().count())), options)
        _, count = ingest_irods_files(resource,
                                      self.logger,
                                      options,
                                      return_errors=False)
        if count:
            msg = "... affected resource {} has type {}, title '{}'"\
                .format(resource.short_id, resource.resource_type, resource.title)
            self.log_or_print(msg, options)
