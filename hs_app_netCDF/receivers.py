from django.dispatch import receiver
from hs_core.signals import *
from hs_app_netCDF.models import NetcdfResource, NetcdfMetaData, Variable
from hs_app_netCDF.forms import *
from hs_core import hydroshare


# receiver used to extract metadata after user click on "create resource"
@receiver(pre_create_resource, sender=NetcdfResource)
def netcdf_create_resource_trigger(sender, **kwargs):
    if sender is NetcdfResource:
        files = kwargs['files']
        metadata = kwargs['metadata']
        if files:
            # Extract the metadata from netcdf file
            infile = files[0]
            import nc_functions.nc_meta as nc_meta
            try:
                res_md_dict = nc_meta.get_nc_meta_dict(infile.file.name)
                res_dublin_core_meta = res_md_dict['dublin_core_meta']
                res_type_specific_meta = res_md_dict['type_specific_meta']
            except:
                res_dublin_core_meta = {}
                res_type_specific_meta = {}

            # add title
            if res_dublin_core_meta.get('title'):
                title = {'title': {'value': res_dublin_core_meta['title']}}
                metadata.append(title)
            # add description
            if res_dublin_core_meta.get('description'):
                description = {'description': {'abstract': res_dublin_core_meta['description']}}
                metadata.append(description)
            # add source
            if res_dublin_core_meta.get('source'):
                source = {'source': {'derived_from': res_dublin_core_meta['source']}}
                metadata.append(source)
            # add relation
            if res_dublin_core_meta.get('references'):
                relation = {'relation': {'type': 'cites', 'value': res_dublin_core_meta['references']}}
                metadata.append(relation)
            # add coverage - period
            if res_dublin_core_meta.get('period'):
                period = {'coverage': {'type': 'period', 'value': res_dublin_core_meta['period']}}
                metadata.append(period)
            # add coverage - box
            if res_dublin_core_meta.get('box'):
                box = {'coverage': {'type': 'box', 'value': res_dublin_core_meta['box']}}
                metadata.append(box)

            # Save extended meta to metadata variable
            for var_name, var_meta in res_type_specific_meta.items():
                meta_info = {}
                for element, value in var_meta.items():
                    if value != '':
                        meta_info[element] = value
                metadata.append({'variable': meta_info})

@receiver(post_create_resource,sender=NetcdfResource)
def netcdf_create_ncdump_file(sender, **kwargs):
    if sender is NetcdfResource:
        nc_res = kwargs['resource']
        nc_files = nc_res.files.all()
        if nc_files:
            nc_file = nc_res.files.all()[0]
            nc_file_name = nc_file.resource_file.path
            # create InMemoryUploadedFile text file to store the dump info and add it to resource
            import nc_functions.nc_dump as nc_dump
            if nc_dump.get_nc_dump_string_by_ncdump(nc_file_name):
                dump_str = nc_dump.get_nc_dump_string_by_ncdump(nc_file_name)
            else:
                dump_str = nc_dump.get_nc_dump_string(nc_file_name)

            if dump_str:
                from django.core.files.uploadedfile import InMemoryUploadedFile
                import StringIO, os
                io = StringIO.StringIO()
                io.write(dump_str)
                dump_file_name = '.'.join(os.path.basename(nc_file_name).split('.')[:-1])+'_header_info.txt'
                dump_file = InMemoryUploadedFile(io, None, dump_file_name, 'text', io.len, None)
                dump_file.seek(0)
                hydroshare.add_resource_files(nc_res.short_id, dump_file)


@receiver(pre_metadata_element_create, sender=NetcdfResource)
def metadata_element_pre_create_handler(sender, **kwargs):
    request = kwargs['request']
    element_name = kwargs['element_name']
    if element_name == "variable":
        element_form = VariableForm(data=request.POST)

    if element_form.is_valid():
        return {'is_valid': True, 'element_data_dict': element_form.cleaned_data}
    else:
        return {'is_valid': False, 'element_data_dict': None}

# This handler is executed only when a metadata element is added as part of editing a resource
@receiver(pre_metadata_element_update, sender=NetcdfResource)
def metadata_element_pre_update_handler(sender, **kwargs):
    element_name = kwargs['element_name'].lower()
    element_id = kwargs['element_id']
    request = kwargs['request']
    if element_name == 'variable':
        form_data = {}
        for field_name in VariableValidationForm().fields:
            matching_key = [key for key in request.POST if '-'+field_name in key][0]
            form_data[field_name] = request.POST[matching_key]

        element_form = VariableValidationForm(form_data)
    if element_form.is_valid():
        return {'is_valid': True, 'element_data_dict': element_form.cleaned_data}
    else:
        # TODO: need to return form errors
        return {'is_valid': False, 'element_data_dict': None}