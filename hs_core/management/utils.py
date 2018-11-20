# -*- coding: utf-8 -*-

"""
Check synchronization between iRODS and Django

This checks that every file in IRODS corresponds to a ResourceFile in Django.
If a file in iRODS is not present in Django, it attempts to register that file in Django.

* By default, prints errors on stdout.
* Optional argument --log instead logs output to system log.
"""

from hs_core.hydroshare.hs_bagit import create_bag_files
from hs_core.tasks import create_bag_by_irods

import json
import os
import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from django_irods.storage import IrodsStorage
from django_irods.icommands import SessionException

from requests import post

from hs_core.models import BaseResource
from hs_core.hydroshare import get_resource_by_shortkey
from hs_core.hydroshare import hs_requests
from hs_core.views.utils import link_irods_file_to_django
from hs_file_types.utils import set_logical_file_type, get_logical_file_type

import logging


def check_relations(resource, logger, options):
    """Check for dangling relations due to deleted resource files.

    :param resource: resource to check
    """
    for r in resource.metadata.relations.all():
        if r.value.startswith('http://www.hydroshare.org/resource/'):
            target = r.value[len('http://www.hydroshare.org/resource/'):].rstrip('/')
            try:
                get_resource_by_shortkey(target, or_404=False)
            except BaseResource.DoesNotExist:
                log_or_print_verbose("Resource {} does not exist in Django"
                                     .format(target), logger, options)


def fix_irods_user_paths(resource, logger, options, return_actions=False):
    """Move iRODS user paths to the locations specified in settings.

    :param resource: resource to check
    :param logger: output log messages
    :param options: options for logging
    :param return_actions: whether to collect actions in an array and return them.

    This is a temporary fix to the user resources, which are currently stored like
    federated resources but whose paths are dynamically determined. This function points
    the paths for user-level resources to where they are stored in the current environment,
    as specified in hydroshare/local_settings.py.

    * This only does something if the environment is not a production environment.
    * It is idempotent, in the sense that it can be repeated more than once without problems.
    * It must be done once whenever the django database is reloaded.
    * It does not check whether the paths exist afterward. This is done by check_irods_files.
    """
    actions = []
    acount = 0

    # location of the user files in production
    defaultpath = getattr(settings, 'HS_USER_ZONE_PRODUCTION_PATH',
                          '/hydroshareuserZone/home/localHydroProxy')
    # where resource should be found; this is equal to the default path in production
    userpath = '/' + os.path.join(
        getattr(settings, 'HS_USER_IRODS_ZONE', 'hydroshareuserZone'),
        'home',
        getattr(settings, 'HS_LOCAL_PROXY_USER_IN_FED_ZONE', 'localHydroProxy'))

    msg = "fix_irods_user_paths: user path is {}".format(userpath.encode('ascii', 'replace'))
    log_or_print_verbose(msg, logger, options)

    # only take action if you find a path that is a default user path and not in production
    if resource.resource_federation_path == defaultpath and userpath != defaultpath:
        msg = "fix_irods_user_paths: mapping existing user federation path {} to {}"\
              .format(resource.resource_federation_path, userpath.encode('ascii', 'replace'))
        log_or_print(msg, logger, options)
        acount += 1
        if return_actions:
            actions.append(msg)

        resource.resource_federation_path = userpath
        resource.save()
        for f in resource.files.all():
            path = f.storage_path
            if path.startswith(defaultpath):
                newpath = userpath + path[len(defaultpath):]
                f.set_storage_path(newpath, test_exists=False)  # does implicit save
                msg = "fix_irods_user_paths: rewriting {} to {}"\
                    .format(path.encode('ascii', 'replace'),
                            newpath.encode('ascii', 'replace'))
                log_or_print(msg, logger, options)
                acount += 1
                if return_actions:
                    actions.append(msg)
            else:
                msg = ("fix_irods_user_paths: ERROR: malformed path {} in resource" +
                       " {} should start with {}; cannot convert")\
                    .format(path.encode('ascii', 'replace'), resource.short_id, defaultpath)
                log_or_print_error(msg, logger, options)
                acount += 1
                if return_actions:
                    actions.append(msg)

    if acount > 0:  # print information about the affected resource (not really an error)
        msg = "fix_irods_user_paths: affected resource {} type is {}, title is '{}'"\
            .format(resource.short_id, resource.resource_type,
                    resource.title.encode('ascii', 'replace'))
        log_or_print(msg, logger, options)
        if return_actions:
            actions.append(msg)

    return actions, acount  # empty unless return_actions=True


def check_irods_files(resource, logger, options, return_errors=False):
    """Check whether files in resource.files and on iRODS agree.

    :param resource: resource to check
    :param return_errors: whether to collect errors in an array and return them.
    :param options: options from command line

    * options['stop_on_error']: whether to raise a ValidationError exception on first error
    * options['sync_ispublic']: whether to repair deviations between
      ResourceAccess.public and AVU isPublic
    * options['clean_irods']: whether to delete files in iRODs that are not in Django
    * options['clean_django']: whether to delete files in Django that are not in iRODs
    """
    from hs_core.hydroshare.resource import delete_resource_file

    istorage = resource.get_irods_storage()
    errors = []
    ecount = 0
    defaultpath = getattr(settings, 'HS_USER_ZONE_PRODUCTION_PATH',
                          '/hydroshareuserZone/home/localHydroProxy')

    # skip federated resources if not configured to handle these
    if resource.is_federated and not settings.REMOTE_USE_IRODS:
        msg = "check_irods_files: skipping check of federated resource {} in unfederated mode"\
            .format(resource.short_id)
        log_or_print_verbose(msg, logger, options)

    # skip resources that do not exist in iRODS
    elif not istorage.exists(resource.root_path):
            msg = "root path {} does not exist in iRODS".format(resource.root_path)
            log_or_print_error(msg, logger, options)
            ecount += 1
            if return_errors:
                errors.append(msg)

    else:
        # Step 1: repair irods user file paths if necessary
        if getattr(options, 'clean_irods', False) or getattr(options, 'clean_django', False):
            # fix user paths before check (required). This is an idempotent step.
            if resource.resource_federation_path == defaultpath:
                error2, ecount2 = fix_irods_user_paths(resource, logger, options,
                                                       return_actions=False)
                errors.extend(error2)
                ecount += ecount2

        # Step 2: does every file in Django refer to an existing file in iRODS?
        for f in resource.files.all():
            if not istorage.exists(f.storage_path):
                msg = "check_irods_files: django file {} does not exist in iRODS"\
                    .format(f.storage_path)
                if getattr(options, 'clean_django', False):
                    delete_resource_file(resource.short_id, f.short_path, resource.creator,
                                         delete_logical_file=False)
                    msg += " (DELETED FROM DJANGO)"
                log_or_print_error(msg, logger, options)
                ecount += 1
                if return_errors:
                    errors.append(msg)

        # Step 3: for composite resources, does every composite metadata file exist?
        from hs_composite_resource.models import CompositeResource as CR
        if isinstance(resource, CR):
            for lf in resource.logical_files:
                if not istorage.exists(lf.metadata_file_path):
                    msg = "check_irods_files: logical metadata file {} does not exist in iRODS"\
                        .format(lf.metadata_file_path)
                    log_or_print_error(msg, logger, options)
                    ecount += 1
                    if return_errors:
                        errors.append(msg)
                if not istorage.exists(lf.map_file_path):
                    msg = "check_irods_files: logical map file {} does not exist in iRODS"\
                        .format(lf.map_file_path)
                    log_or_print_error(msg, logger, options)
                    ecount += 1
                    if return_errors:
                        errors.append(msg)

        # Step 4: does every iRODS file correspond to a record in files?
        error2, ecount2 = __check_irods_directory(resource, resource.file_path, logger, options,
                                                  return_errors=return_errors)
        errors.extend(error2)
        ecount += ecount2

        # Step 5: check whether the iRODS public flag agrees with Django
        django_public = resource.raccess.public
        irods_public = None
        try:
            irods_public = resource.getAVU('isPublic')
        except SessionException as ex:
            msg = "cannot read isPublic attribute of {}: {}"\
                .format(resource.short_id, ex.stderr)
            log_or_print_error(msg, logger, options)
            ecount += 1
            if return_errors:
                errors.append(msg)

        if irods_public is not None:
            # convert to boolean
            irods_public = str(irods_public).lower() == 'true'

        if irods_public is None or irods_public != django_public:
            ecount += 1
            if not django_public:  # and irods_public
                msg = "check_irods_files: resource {} public in irods, private in Django"\
                    .format(resource.short_id)
                if getattr(options, 'sync_ispublic', False):
                    try:
                        resource.setAVU('isPublic', 'false')
                        msg += " (REPAIRED IN IRODS)"
                    except SessionException as ex:
                        msg += ": (CANNOT REPAIR: {})"\
                            .format(ex.stderr)

            else:  # django_public and not irods_public
                msg = "check_irods_files: resource {} private in irods, public in Django"\
                    .format(resource.short_id)
                if getattr(options, 'sync_ispublic', False):
                    try:
                        resource.setAVU('isPublic', 'true')
                        msg += " (REPAIRED IN IRODS)"
                    except SessionException as ex:
                        msg += ": (CANNOT REPAIR: {})"\
                            .format(ex.stderr)

            if msg != '':
                log_or_print_error(msg, logger, options)
                ecount += 1
                if return_errors:
                    errors.append(msg)

    if ecount > 0:  # print information about the affected resource (not really an error)
        msg = "check_irods_files: affected resource {} type is {}, title is '{}'"\
            .format(resource.short_id, resource.resource_type,
                    resource.title.encode('ascii', 'replace'))
        log_or_print_error(msg, logger, options)
        if return_errors:
            errors.append(msg)

    return errors, ecount  # errors list is empty unless return_errors=True


def __check_irods_directory(resource, dir, logger, options,
                            return_errors=False,
                            clean=False):
    """List a directory and check files there for conformance with django ResourceFiles.

    :param logger: log object for printing to log
    :param options: options from command line
    :param return_errors: whether to collect errors in an array and return them.

    """
    errors = []
    ecount = 0
    istorage = resource.get_irods_storage()
    try:
        listing = istorage.listdir(dir)
        for fname in listing[1]:  # files
            # do not use os.path.join because fname might contain unicode characters
            fullpath = dir + '/' + fname
            found = False
            for f in resource.files.all():
                if f.storage_path == fullpath:
                    found = True
                    break
            if not found and not resource.is_aggregation_xml_file(fullpath):
                msg = "check_irods_files: file {} in iRODs does not exist in Django"\
                    .format(fullpath.encode('ascii', 'replace'))
                if clean:
                    try:
                        istorage.delete(fullpath)
                        msg += " (DELETED FROM IRODS)"
                    except SessionException as ex:
                        msg += ": (CANNOT DELETE: {})"\
                            .format(ex.stderr)
                log_or_print_error(msg, logger, options)
                ecount += 1
                if return_errors:
                    errors.append(msg)

        for dname in listing[0]:  # directories
            # do not use os.path.join because paths might contain unicode characters!
            error2, ecount2 = __check_irods_directory(resource, dir + '/' + dname,
                                                      logger, options,
                                                      return_errors=return_errors,
                                                      clean=clean)
            ecount += ecount2
            errors.extend(error2)

    except SessionException:
        pass  # not an error not to have a file directory.
        # Non-existence of files is checked elsewhere.

    return errors, ecount  # empty unless return_errors=True


def ingest_irods_files(resource,
                       logger,
                       options,
                       return_errors=False):

    istorage = resource.get_irods_storage()
    errors = []
    ecount = 0

    # skip federated resources if not configured to handle these
    if resource.is_federated and not settings.REMOTE_USE_IRODS:
        msg = "ingest_irods_files: skipping ingest of federated resource {} in unfederated mode"\
            .format(resource.short_id)
        log_or_print(msg, logger, options)

    else:
        # flag non-existent resources in iRODS
        if not istorage.exists(resource.root_path):
            msg = "root path {} does not exist in iRODS".format(resource.root_path)
            log_or_print_error(msg, logger, options)
            ecount += 1
            if return_errors:
                errors.append(msg)

        # flag non-existent file paths in iRODS
        elif not istorage.exists(resource.file_path):
            msg = "file path {} does not exist in iRODS".format(resource.file_path)
            log_or_print_error(msg, logger, options)
            ecount += 1
            if return_errors:
                errors.append(msg)

        else:
            return __ingest_irods_directory(resource,
                                            resource.file_path,
                                            logger,
                                            options,
                                            return_errors=False)

    return errors, ecount


def __ingest_irods_directory(resource,
                             dir,
                             logger,
                             options,
                             return_errors=False):
    """
    list a directory and ingest files there for conformance with django ResourceFiles

    :param return_errors: whether to collect errors in an array and return them.

    """
    errors = []
    ecount = 0
    istorage = resource.get_irods_storage()
    try:
        listing = istorage.listdir(dir)
        for fname in listing[1]:  # files
            # do not use os.path.join because fname might contain unicode characters
            fullpath = dir + '/' + fname
            found = False
            for res_file in resource.files.all():
                if res_file.storage_path == fullpath:
                    found = True

            if not found and not resource.is_aggregation_xml_file(fullpath):
                msg = "ingest_irods_files: file {} in iRODs does not exist in Django (INGESTING)"\
                    .format(fullpath.encode('ascii', 'replace'))
                log_or_print_error(msg, logger, options)
                ecount += 1
                if return_errors:
                    errors.append(msg)
                # TODO: does not ingest logical file structure for composite resources
                link_irods_file_to_django(resource, fullpath)

                # Create required logical files as necessary
                if resource.resource_type == "CompositeResource":
                    file_type = get_logical_file_type(res=resource, user=None,
                                                      file_id=res_file.pk, fail_feedback=False)
                    # TODO: check that this is warranted under new model.
                    if not res_file.has_logical_file and file_type is not None:
                        msg = "ingest_irods_files: setting required logical file for {}"\
                              .format(fullpath)
                        log_or_print_error(msg, logger, options)
                        ecount += 1
                        if return_errors:
                            errors.append(msg)
                        set_logical_file_type(res=resource, user=None, file_id=res_file.pk,
                                              fail_feedback=False)
                    elif res_file.has_logical_file and file_type is not None and \
                            not isinstance(res_file.logical_file, file_type):
                        msg = "ingest_irods_files: logical file for {} has type {}, should be {}"\
                            .format(res_file.storage_path.encode('ascii', 'replace'),
                                    type(res_file.logical_file).__name__,
                                    file_type.__name__)
                        log_or_print_error(msg, logger, options)
                        ecount += 1
                        if return_errors:
                            errors.append(msg)
                    # This is not really an error. Users can create this situation.
                    # elif res_file.has_logical_file and file_type is None:
                    #     msg = "ingest_irods_files: logical file for {} has type {}, not needed"\
                    #         .format(res_file.storage_path, type(res_file.logical_file).__name__,
                    #                 file_type.__name__)
                    #     if echo_errors:
                    #         print(msg)
                    #     if log_errors:
                    #         logger.error(msg)
                    #     if return_errors:
                    #         errors.append(msg)
                    #     if getattr(options, 'stop_on_error', False):
                    #         raise ValidationError(msg)

        for dname in listing[0]:  # directories
            # do not use os.path.join because fname might contain unicode characters
            error2, ecount2 = __ingest_irods_directory(resource,
                                                       dir + '/' + dname,
                                                       logger,
                                                       options,
                                                       return_errors=return_errors)
            errors.extend(error2)
            ecount += ecount2

    except SessionException as se:
        print("iRODs error: {}".format(se.stderr))
        logger.error("iRODs error: {}".format(se.stderr))

    return errors, ecount  # empty unless return_errors=True


def check_for_dangling_irods(logger, options, return_errors=False):
    """ This checks for resource trees in iRODS with no correspondence to Django at all

    :param return_errors: whether to collect errors in an array and return them.
    """

    istorage = IrodsStorage()  # local only
    toplevel = istorage.listdir('.')  # list the resources themselves
    logger = logging.getLogger(__name__)

    errors = []
    ecount = 0
    for id in toplevel[0]:  # directories
        try:
            get_resource_by_shortkey(id, or_404=False)
        except BaseResource.DoesNotExist:
            msg = "resource {} does not exist in Django".format(id)
            log_or_print_error(msg, logger, options)
            ecount += 1
            if return_errors:
                errors.append(msg)
    return errors, ecount


class CheckJSONLD(object):
    def __init__(self, short_id):
        self.short_id = short_id
        self.logger = logging.getLogger(__name__)

    def test(self, options):
        default_site = Site.objects.first()
        validator_url = "https://search.google.com/structured-data/testing-tool/validate"
        url = "https://" + default_site.domain + "/resource/" + self.short_id
        cookies = {"NID": settings.GOOGLE_COOKIE_HASH}

        response = post(validator_url, {"url": url}, cookies=cookies)

        response_json = json.loads(response.text[4:])
        if response_json.get("totalNumErrors") > 0:
            for error in response_json.get("errors"):
                if "includedInDataCatalog" not in error.get('args'):
                    errors = response_json.get("errors")
                    log_or_print_error("Error found on resource {}: {}"
                                       .format(self.short_id, errors),
                                       self.logger, options)
                    return

        if response_json.get("totalNumWarnings") > 0:
            warnings = response_json.get("warnings")
            log_or_print_warning("Warnings found on resource {}: {}"
                                 .format(self.short_id, warnings),
                                 self.logger, options)
            return


def log_or_print_verbose(message, logger, options):
    if getattr(options, 'verbose', False):
        if getattr(options, 'log', False):
            logger.info(message)
        else:
            print(message)


def log_or_print_error(message, logger, options):
    log_or_print(message, logger, options, error=True)


def log_or_print_warning(message, logger, options):
    log_or_print(message, logger, options, warning=True)


def log_or_print(message, logger, options, error=False, warning=False):
    if getattr(options, 'log', False):
        if error:
            logger.error(message)
        elif warning:
            logger.warn(message)
        else:
            logger.info(message)
    else:
        print(message)
    if error and getattr(options, 'stop_on_error', False):
        raise ValidationError(message)


def repair_resource(res, logger, options, return_errors=False):
    errors = []
    ecount = 0
    try:
        resource = get_resource_by_shortkey(res.short_id, or_404=False)
    except BaseResource.DoesNotExist:
        msg = "Resource {} does not exist in Django".format(res.short_id)
        log_or_print_error(msg, logger, options)
        ecount = ecount + 1
        if return_errors:
            errors.append(msg)
        return errors, ecount

    print("REPAIRING RESOURCE {}".format(resource.short_id))

    # ingest any dangling iRODS files that you can
    # Do this before check because otherwise, errors get printed twice
    # TODO: This does not currently work properly for composite resources
    # if resource.resource_type == 'CompositeResource' or \
    if resource.resource_type == 'GenericResource' or \
       resource.resource_type == 'ModelInstanceResource' or \
       resource.resource_type == 'ModelProgramResource':
        _, count = ingest_irods_files(resource,
                                      logger,
                                      echo_errors=True,
                                      log_errors=False,
                                      return_errors=False)
        if count:
            log_or_print_error("... affected resource {} has type {}, title '{}'"
                               .format(resource.short_id, resource.resource_type,
                                       resource.title.encode('ascii', 'replace')),
                               logger, options)

    _, count = check_irods_files(resource, logger, options, return_errors=False)
    if count:
        log_or_print_error("... affected resource {} has type {}, title '{}'"
                           .format(resource.short_id, resource.resource_type,
                                   resource.title.encode('ascii', 'replace')),
                           logger, options)


class CheckResource(object):
    """ comprehensively check a resource """
    header = False

    def __init__(self, short_id):
        self.short_id = short_id

    def label(self):
        if not self.header:
            print("resource {}:".format(self.resource.short_id))
            self.header = True

    def check_avu(self, label):
        try:
            value = self.resource.getAVU(label)
            if value is None:
                self.label()
                print("  AVU {} is None".format(label))
            return value
        except SessionException:
            self.label()
            print("  AVU {} NOT FOUND.".format(label))
            return None

    def test(self, logger, options):
        """ Test view for resource depicts output of various integrity checking scripts """

        # print("TESTING {}".format(self.short_id))  # leave this for debugging

        try:
            self.resource = get_resource_by_shortkey(self.short_id, or_404=False)
        except BaseResource.DoesNotExist:
            print("Resource {} does not exist in Django".format(self.short_id))
            return

        # skip federated resources if not configured to handle these
        if self.resource.is_federated and not settings.REMOTE_USE_IRODS:
            msg = "check_resource: skipping check of federated resource {} in unfederated mode"\
                .format(self.resource.short_id)
            log_or_print(msg, logger, options)

        istorage = self.resource.get_irods_storage()

        if not istorage.exists(self.resource.root_path):
            self.label()
            log_or_print("  root path {} does not exist in iRODS".format(self.resource.root_path),
                         logger, options)
            log_or_print("  ... resource {} has type {} and title {}"
                         .format(self.resource.short_id,
                                 self.resource.resource_type,
                                 self.resource.title.encode('ascii', 'replace')),
                         logger, options)
            return

        for a in ('bag_modified', 'isPublic', 'resourceType', 'quotaUserName'):
            value = self.check_avu(a)
            if a == 'resourceType' and value is not None and value != self.resource.resource_type:
                self.label()
                log_or_print("  AVU resourceType is {}, should be {}"
                             .format(value.encode('ascii', 'replace'),
                                     self.resource.resource_type),
                             logger, options)
            if a == 'isPublic' and value is not None and value != self.resource.raccess.public:
                self.label()
                log_or_print("  AVU isPublic is {}, but public is {}"
                             .format(str(value), self.resource.raccess.public), logger, options)

        irods_issues, irods_errors = check_irods_files(self.resource, logger, options,
                                                       return_errors=True)

        if irods_errors:
            self.label()
            log_or_print("  iRODS errors:", logger, options)
            for e in irods_issues:
                log_or_print("    {}".format(e), logger, options)

        if self.resource.resource_type == 'CompositeResource':
            logical_issues = []
            for res_file in self.resource.files.all():
                file_type = get_logical_file_type(res=self.resource, user=None,
                                                  file_id=res_file.pk, fail_feedback=False)
                if not res_file.has_logical_file and file_type is not None:
                    msg = "check_resource: file {} does not have required logical file {}"\
                          .format(res_file.storage_path.encode('ascii', 'replace'),
                                  file_type.__name__)
                    logical_issues.append(msg)
                elif res_file.has_logical_file and file_type is None:
                    msg = "check_resource: logical file for {} has type {}, not needed"\
                          .format(res_file.storage_path.encode('ascii', 'replace'),
                                  type(res_file.logical_file).__name__)
                    logical_issues.append(msg)
                elif res_file.has_logical_file and file_type is not None and \
                        not isinstance(res_file.logical_file, file_type):
                    msg = "check_resource: logical file for {} has type {}, should be {}"\
                          .format(res_file.storage_path.encode('ascii', 'replace'),
                                  type(res_file.logical_file).__name__,
                                  file_type.__name__)
                    logical_issues.append(msg)

            if logical_issues:
                self.label()
                log_or_print("  Logical file errors:", logger, options)
                for e in logical_issues:
                    log_or_print("    {}".format(e), logger, options)


def debug_resource(short_id, logger, options):
    """ Debug view for resource depicts output of various integrity checking scripts """

    try:
        res = get_resource_by_shortkey(short_id, or_404=False)
    except BaseResource.DoesNotExist:
        log_or_print_error("{} does not exist".format(short_id), logger, options)

    resource = res.get_content_model()
    assert resource, (res, res.content_model)

    irods_issues, irods_errors = check_irods_files(resource, logger, options,
                                                   return_errors=True)
    log_or_print("resource: {}"
                 .format(short_id), logger, options)
    log_or_print("resource type: {}"
                 .format(resource.resource_type), logger, options)
    log_or_print("resource creator: {} {}"
                 .format(resource.creator.first_name, resource.creator.last_name),
                 logger, options)
    log_or_print("resource irods bag modified: {}"
                 .format(str(resource.getAVU('bag_modified'))), logger, options)
    log_or_print("resource irods isPublic: {}"
                 .format(str(resource.getAVU('isPublic'))), logger, options)
    log_or_print("resource irods resourceType: {}"
                 .format(str(resource.getAVU('resourceType'))), logger, options)
    log_or_print("resource irods quotaUserName: {}"
                 .format(str(resource.getAVU('quotaUserName'))), logger, options)

    if irods_errors:
        log_or_print_error("iRODS errors:", logger, options)
        for e in irods_issues:
            log_or_print_error("    {}".format(e), logger, options)
    else:
        log_or_print("No iRODS errors", logger, options)

    if resource.resource_type == 'CompositeResource':
        print("Resource file logical files:")
        for res_file in resource.files.all():
            if res_file.has_logical_file:
                log_or_print("    {} logical file {} is [{}]"
                             .format(res_file.short_path,
                                     str(type(res_file.logical_file)),
                                     str(res_file.logical_file.id)),
                             logger, options)


def check_bag(rid, logger, options):
    requests.packages.urllib3.disable_warnings()
    try:
        resource = get_resource_by_shortkey(rid, or_404=False)
    except BaseResource.DoesNotExist:
        print("check_bag: Resource {} does not exist in Django"
              .format(resource.short_id))
        return

    istorage = resource.get_irods_storage()
    root_exists = istorage.exists(resource.root_path)

    if root_exists:
        # print status of metadata/bag system
        scimeta_path = os.path.join(resource.root_path, 'data',
                                    'resourcemetadata.xml')
        scimeta_exists = istorage.exists(scimeta_path)
        if scimeta_exists:
            log_or_print("resource metadata {} found".format(scimeta_path), logger, options)
        else:
            log_or_print("resource metadata {} NOT FOUND".format(scimeta_path), logger, options)

        resmap_path = os.path.join(resource.root_path, 'data', 'resourcemap.xml')
        resmap_exists = istorage.exists(resmap_path)
        if resmap_exists:
            log_or_print("resource map {} found".format(resmap_path), logger, options)
        else:
            log_or_print("resource map {} NOT FOUND".format(resmap_path), logger, options)

        bag_exists = istorage.exists(resource.bag_path)
        if bag_exists:
            log_or_print("bag {} found".format(resource.bag_path), logger, options)
        else:
            log_or_print("bag {} NOT FOUND".format(resource.bag_path), logger, options)

        dirty = resource.getAVU('metadata_dirty')
        log_or_print("{}.metadata_dirty is {}".format(rid, str(dirty)), logger, options)

        modified = resource.getAVU('bag_modified')
        log_or_print("{}.bag_modified is {}".format(rid, str(modified)), logger, options)

        if getattr(options, 'reset', False):  # reset all data to pristine
            resource.setAVU('metadata_dirty', 'true')
            print("{}.metadata_dirty set to true".format(rid))
            try:
                istorage.delete(resource.scimeta_path)
                log_or_print("{} deleted".format(resource.scimeta_path), logger, options)
            except SessionException as ex:
                log_or_print_error("{} delete failed: {}"
                                   .format(resource.scimeta_path, ex.stderr),
                                   logger, options)
            try:
                istorage.delete(resource.resmap_path)
                log_or_print("{} deleted".format(resource.resmap_path), logger, options)
            except SessionException as ex:
                log_or_print_error("{} delete failed: {}"
                                   .format(resource.resmap_path, ex.stderr),
                                   logger, options)

            resource.setAVU('bag_modified', 'true')
            log_or_print("{}.bag_modified set to true".format(rid), logger, options)
            try:
                istorage.delete(resource.bag_path)
                log_or_print("{} deleted".format(resource.bag_path), logger, options)
            except SessionException as ex:
                log_or_print_error("{} delete failed: {}"
                                   .format(resource.bag_path, ex.stderr),
                                   logger, options)

        if getattr(options, 'reset_metadata', False):
            resource.setAVU('metadata_dirty', 'true')
            log_or_print("{}.metadata_dirty set to true".format(rid), logger, options)
            try:
                istorage.delete(resource.scimeta_path)
                log_or_print("{} deleted".format(resource.scimeta_path), logger, options)
            except SessionException as ex:
                log_or_print_error("delete of {} failed: {}"
                                   .format(resource.scimeta_path, ex.stderr),
                                   logger, options)
            try:
                istorage.delete(resource.resmap_path)
                log_or_print("{} deleted".format(resource.resmap_path), logger, options)
            except SessionException as ex:
                log_or_print_error("{} delete failed: {}"
                                   .format(resource.resmap_path, ex.stderr),
                                   logger, options)

        if getattr(options, 'reset_bag', False):
            resource.setAVU('bag_modified', 'true')
            log_or_print("{}.bag_modified set to true".format(rid), logger, options)
            try:
                istorage.delete(resource.bag_path)
                log_or_print("{} deleted".format(resource.bag_path), logger, options)
            except SessionException as ex:
                log_or_print_error("{} delete failed: {}"
                                   .format(resource.bag_path, ex.stderr),
                                   logger, options)

        if getattr(options, 'generate', False):  # generate usable bag
            if not getattr(options, 'if_needed', False) or \
               dirty or not scimeta_exists or not resmap_exists:
                try:
                    create_bag_files(resource)
                except ValueError as e:
                    log_or_print_error("{}: value error encountered: {}".format(rid, e.message),
                                       logger, options)
                    return

                log_or_print("{} metadata generated from Django".format(rid), logger, options)
                resource.setAVU('metadata_dirty', 'false')
                resource.setAVU('bag_modified', 'true')
                log_or_print("{}.metadata_dirty set to false".format(rid), logger, options)
                log_or_print("{}.bag_modified set to true".format(rid), logger, options)

            if not getattr(options, 'if_needed', False) or modified or not bag_exists:
                create_bag_by_irods(rid)
                log_or_print("{} bag generated from iRODs".format(rid), logger, options)
                resource.setAVU('bag_modified', 'false')
                log_or_print("{}.bag_modified set to false".format(rid), logger, options)

        if getattr(options, 'generate_metadata', False):
            if not getattr(options, 'if_needed', False) or \
               dirty or not scimeta_exists or not resmap_exists:
                try:
                    create_bag_files(resource)
                except ValueError as e:
                    log_or_print_error("{}: value error encountered: {}".format(rid, e.message),
                                       logger, options)
                    return
                log_or_print("{}: metadata generated from Django".format(rid), logger, options)
                resource.setAVU('metadata_dirty', 'false')
                log_or_print("{}.metadata_dirty set to false".format(rid), logger, options)
                resource.setAVU('bag_modified', 'true')
                log_or_print("{}.bag_modified set to false".format(rid), logger, options)

        if getattr(options, 'generate_bag', False):
            if not getattr(options, 'if_needed', False) or modified or not bag_exists:
                create_bag_by_irods(rid)
                log_or_print("{}: bag generated from iRODs".format(rid), logger, options)
                resource.setAVU('bag_modified', 'false')
                log_or_print("{}.bag_modified set to false".format(rid), logger, options)

        if getattr(options, 'download_bag', False):
            if getattr(options, 'password', '') != '' and getattr(options, 'login', '') != '':
                server = getattr(settings, 'FQDN_OR_IP', 'www.hydroshare.org')
                uri = "https://{}/hsapi/resource/{}/".format(server, rid)
                log_or_print("download uri is {}".format(uri))
                r = hs_requests.get(uri, verify=False, stream=True,
                                    auth=requests.auth.HTTPBasicAuth(options['login'],
                                                                     options['password']))
                print("download return status is {}".format(str(r.status_code)))
                print("redirects:")
                for thing in r.history:
                    print("...url: {}".format(thing.url))
                filename = 'tmp/check_bag_block'
                with open(filename, 'wb') as fd:
                    for chunk in r.iter_content(chunk_size=128):
                        fd.write(chunk)
            else:
                print("cannot download bag without username and password.")

        if getattr(options, 'open_bag', False):
            if getattr(options, 'password', '') != '' and getattr(options, 'login', '') != '':
                server = getattr(settings, 'FQDN_OR_IP', 'www.hydroshare.org')
                uri = "https://{}/hsapi/resource/{}/".format(server, rid)
                print("download uri is {}".format(uri))
                r = hs_requests.get(uri, verify=False, stream=True,
                                    auth=requests.auth.HTTPBasicAuth(options['login'],
                                                                     options['password']))
                print("download return status is {}".format(str(r.status_code)))
                print("redirects:")
                for thing in r.history:
                    print("...url: {}".format(thing.url))
                filename = 'tmp/check_bag_block'
                with open(filename, 'wb') as fd:
                    for chunk in r.iter_content(chunk_size=128):
                        fd.write(chunk)
                        break
            else:
                print("cannot open bag without username and password.")
    else:
        print("Resource with id {} does not exist in iRODS".format(rid))


class ResourceCommand(BaseCommand):
    """
    Simplified interface to commands that act on resources.

    This interface is based upon BaseCommand and reused for several
    kinds of commands that act on resources, including listing, repairing, etc.
    One inherits from this class and overrides one function resource_action.
    Then that function is applied to all resources listed on the command line,
    using filters that are also interpreted on the command line.

    Arguments include:
        --log
        --verbose
        --type=CompositeResource
        --storage=federated
        --access=public
        --has_subfolders
    etc.

    """
    help = "Repeat an action for a list of resources."

    default_to_all = True  # by default, with no arguments, operate on all resources

    def resource_action(self, options):
        """
        Do an action on a resource

        :param options: options from the command line based upon the BaseCommand package

        This must be overridden with the appropriate action

        """
        print("Function resource_action must be overridden for ResourceCommand to work.")
        exit(1)

    def add_arguments(self, parser):
        """
        Specify arguments that apply to resource selection
        """
        # a list of resource id's: none means all unless default_to_all is False
        parser.add_argument('resource_ids', nargs='*', type=str)

        # Named (optional) arguments
        parser.add_argument(
            '--log',
            action='store_true',  # True for presence, False for absence
            dest='log',           # value is options['log']
            help='log errors to system log',
        )

        parser.add_argument(
            '--verbose',
            action='store_true',  # True for presence, False for absence
            dest='verbose',       # value is options['verbose']
            help='print verbose log of actions',
        )

        parser.add_argument(  # type is resource.resource_type
            '--type',
            dest='type',
            help='limit to resources of a particular type'
        )

        parser.add_argument(
            '--storage',
            dest='storage',
            help='limit to specific storage medium (local, user, federated)'
        )

        parser.add_argument(
            '--access',
            dest='access',
            help='limit to specific access class (public, discoverable, private)'
        )

        parser.add_argument(
            '--has_subfolders',
            action='store_true',  # True for presence, False for absence
            dest='has_subfolders',  # value is options['has_subfolders']
            help='limit to resources with subfolders',
        )

        parser.add_argument(
            '--stop_on_error',
            action='store_true',  # True for presence, False for absence
            dest='stop_on_error',  # value is options['stop_on_error']
            help='stop on first error',
        )

    logger = logging.getLogger(__name__)

    def log_or_print_verbose(self, message, options):
        """ only print or log in verbose mode """
        if options['verbose']:
            log_or_print(self, message, options)

    def log_or_print(self, message, options, error=False, warning=False):
        """ use options to determine whether to log or print a message. """
        if options['log']:
            if error:
                self.logger.error(message)
            elif warning:
                self.logger.warn(message)
            else:
                self.logger.info(message)
        else:
            print(message)

    def log_or_print_error(self, message, options):
        log_or_print(self, message, options, error=True)

    def log_or_print_warning(self, message, options):
        log_or_print(self, message, options, warning=True)

    @staticmethod
    def has_subfolders(resource):
        """
        Returns true if a resource has subfolders present in its file hierarchy.

        :param resource: a fully type-qualified resource as returned from get_resource_by_shortkey
        """
        for f in resource.files.all():
            if '/' in f.short_path:
                return True
        return False

    def include_resource(self, resource, options):
        """
        filter a resource according to command-line options

        :param resource: a fully type-qualified resource as returned from get_resource_by_shortkey
        :param options: an option list as returned by BaseCommand as argument to handle()
        """
        if (options['type'] is None or resource.resource_type == options['type']) and \
           (options['storage'] is None or resource.storage_type == options['storage']) and \
           (options['access'] != 'public' or resource.raccess.public) and \
           (options['access'] != 'discoverable' or resource.raccess.discoverable) and \
           (options['access'] != 'private' or not resource.raccess.discoverable) and \
           (not options['has_subfolders'] or ResourceCommand.has_subfolders(resource)):
            return True
        else:
            return False

    def handle(self, *args, **options):
        """
        handle a command that involves multiple resources

        options are defined via add_arguments above.
        """

        if len(options['resource_ids']) > 0:  # an array of resource short_id to check.
            for rid in options['resource_ids']:
                try:
                    resource = get_resource_by_shortkey(rid, or_404=False)
                except BaseResource.DoesNotExist:
                    self.log_or_print("Resource {} does not exist in Django"
                                      .format(resource.short_id), options)
                    continue
                if options['verbose']:
                    self.log_or_print("Processing {}".format(resource.short_id), options)

                self.resource_action(resource, options)
        else:
            if self.default_to_all:
                if options['verbose']:
                    self.log_or_print("ACTING ON ALL RESOURCES", options)
                for r in BaseResource.objects.all():
                    try:
                        resource = get_resource_by_shortkey(r.short_id, or_404=False)
                    except BaseResource.DoesNotExist:
                        self.log_or_print("Resource {} does not exist in Django"
                                          .format(r.short_id), options)
                        continue
                    if options['verbose']:
                        self.log_or_print("Processing {}".format(resource.short_id), options)
                    self.resource_action(resource, options)
            else:
                self.log_or_print("no resources specified.", options)
