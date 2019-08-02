'''from django.conf import settings
from django.dispatch import receiver
from hs_core.signals import post_delete_resource, post_add_geofeature_aggregation, \
    post_add_generic_aggregation, post_add_netcdf_aggregation, post_add_raster_aggregation, \
    post_add_timeseries_aggregation, post_add_reftimeseries_aggregation, \
    post_remove_file_aggregation, post_raccess_change
from hs_data_services.tasks import update_data_services


@receiver(post_add_generic_aggregation)
@receiver(post_add_geofeature_aggregation)
@receiver(post_add_raster_aggregation)
@receiver(post_add_netcdf_aggregation)
@receiver(post_add_timeseries_aggregation)
@receiver(post_add_reftimeseries_aggregation)
@receiver(post_remove_file_aggregation)
@receiver(post_delete_resource)
@receiver(post_raccess_change)
def hs_update_web_services(sender, **kwargs):
    
    if settings.HSDS_ACTIVE:
        update_data_services.apply_async((
            kwargs.get("resource").short_id
        ), countdown=120)'''
