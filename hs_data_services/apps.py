from django.apps import AppConfig


class DataServices(AppConfig):
	name = "hs_data_services"


	def ready(self):
		import receivers
