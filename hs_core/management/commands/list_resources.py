"""This lists all the large resources and their statuses.
   This helps in checking that they download properly.

* By default, prints errors on stdout.
* Optional argument --log: logs output to system log.
"""

from hs_core.management.utils import ResourceCommand
from hs_core.models import BaseResource


def measure_resource(short_id):
    """ Print size and sharing status of a resource """

    try:
        res = BaseResource.objects.get(short_id=short_id)
    except BaseResource.DoesNotExist:
        print("{} does not exist".format(short_id))

    resource = res.get_content_model()
    assert resource, (res, res.content_model)

    istorage = resource.get_irods_storage()
    if resource.raccess.public:
        status = "public"
    elif resource.raccess.discoverable:
        status = "discoverable"
    else:
        status = "private"

    if istorage.exists(resource.file_path):
        print("{} {} {} {} {} {}".format(resource.size, short_id, status, resource.storage_type,
                                         resource.resource_type, resource.title))
    else:
        print("{} {} {} {} {} {} NO IRODS FILES".format('-', short_id, status,
                                                        resource.storage_type,
                                                        resource.resource_type,
                                                        resource.title))


class Command(ResourceCommand):
    help = "List a set of resources."

    # this defines what to do when a resource is qualified according to the command line
    def resource_action(self, resource, options):
        storage = resource.get_irods_storage()
        if storage.exists(resource.root_path):
            measure_resource(resource.short_id)
        else:
            print("Resource {} does not exist in iRODS".format(resource.short_id))
