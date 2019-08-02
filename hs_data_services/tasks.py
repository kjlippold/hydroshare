'''from celery import shared_task
from hs_data_services.utilities import get_database_list, unregister_geoserver_databases, \
	unregister_hydroserver_databases, create_services_status, register_geoserver_workspace, \
	unregister_geoserver_database, register_geoserver_database, get_geoserver_list, \
	register_hydroserver_network, unregister_hydroserver_database, register_hydroserver_database, \
	get_hydroserver_list, update_resource_metadata


@shared_task
def update_data_services(resource_id):

	resource_databases = get_database_list(resource_id)

	registered_services = {
		"geoserver": [],
		"hydroserver": []
	}

	if resource_databases["access"] == ("private" or "not_found"):

		unregister_geoserver_databases(resource_id)
		unregister_hydroserver_databases(resource_id)

		services_status = create_services_status(registered_services)

	elif resource_databases["access"] == "public":

		if resource_databases["geoserver"]["create_workspace"] is True:
			workspace_status = register_geoserver_workspace(resource_id)

		for database in resource_databases["geoserver"]["unregister"]:
			database_status = unregister_geoserver_database(resource_id, database)

		for database in resource_databases["geoserver"]["register"]:
			database_status = register_geoserver_database(resource_id, database)
			registered_services["geoserver"].append(database_status)
			if database_status["success"] is False:
				unregister_geoserver_database(resource_id, database)

		geoserver_list = get_geoserver_list(resource_id)
		if not geoserver_list:
			unregister_geoserver_databases(resource_id)

		if resource_databases["hydroserver"]["create_network"] is True:
			network_status = register_hydroserver_network(resource_id)

		for database in resource_databases["hydroserver"]["unregister"]:
			database_status = unregister_hydroserver_database(resource_id, database)

		for database in resource_databases["hydroserver"]["register"]:
			database_status = register_hydroserver_database(resource_id, database)
			registered_services["hydroserver"].append(database_status)
			if database_status["success"] is False:
				unregister_hydroserver_database(resource_id, database)

		hydroserver_list = get_hydroserver_list(resource_id)
		if not hydroserver_list:
			unregister_hydroserver_databases

		services_status = create_services_status(registered_services)

	update_resource_metadata(services_status)'''
