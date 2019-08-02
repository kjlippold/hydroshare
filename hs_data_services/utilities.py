'''import requests
import json
import os


def get_layer_style(max_value, min_value, ndv_value, layer_id):
    """
    Sets default style for raster layers.
    """
    if ndv_value < min_value:
        low_ndv = "<ColorMapEntry color=\"#000000\" quantity=\"%s\" label=\"nodata\" opacity=\"0.0\" />" % ndv_value
        high_ndv = ""
    elif ndv_value > max_value:
        low_ndv = ""
        high_ndv = "<ColorMapEntry color=\"#000000\" quantity=\"%s\" label=\"nodata\" opacity=\"0.0\" />" % ndv_value
    else:
        low_ndv = ""
        high_ndv = ""
    layer_style = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
      xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
      <NamedLayer>
        <Name>simpleraster</Name>
        <UserStyle>
          <Name>%s</Name>
          <Title>Default raster style</Title>
          <Abstract>Default greyscale raster style</Abstract>
          <FeatureTypeStyle>
            <Rule>
              <RasterSymbolizer>
                <Opacity>1.0</Opacity>
                <ColorMap>
                  %s
                  <ColorMapEntry color="#000000" quantity="%s" label="values" />
                  <ColorMapEntry color="#FFFFFF" quantity="%s" label="values" />
                  %s
                </ColorMap>
              </RasterSymbolizer>
            </Rule>
          </FeatureTypeStyle>
        </UserStyle>
      </NamedLayer>
    </StyledLayerDescriptor>""" % (layer_id, low_ndv, min_value, max_value, high_ndv)

return layer_style'''


