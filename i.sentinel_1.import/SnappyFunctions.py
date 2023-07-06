"""
Name:       SnappyFunctions
Purpose:    Collection of functions to call ESA SNAP software steps
Author:     Hajar Benelcadi, Guido Riembauer
Copyright:  (C) 2020-2022 mundialis GmbH & Co. KG and the GRASS Development Team
License:    This program is free software; you can redistribute it and/or modify
            it under the terms of the GNU General Public License as published by
            the Free Software Foundation; either version 2 of the License, or
            (at your option) any later version.

            This program is distributed in the hope that it will be useful,
            but WITHOUT ANY WARRANTY; without even the implied warranty of
            MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
            GNU General Public License for more details.
"""


import snappy

from snappy import GPF
from snappy import PixelPos
from osgeo.osr import SpatialReference
import json
from shapely.geometry import shape
from shapely.wkt import dumps

# Hashmap is used to access to all JAVA oerators
GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
HashMap = snappy.jpy.get_type("java.util.HashMap")


# Function to auto detect UTM zone of sentinel_1 GRD mode image
def AutoDetectUtmZone(raster):
    x = raster.getSceneRasterWidth() / 2
    y = raster.getSceneRasterHeight() / 2
    coding = raster.getSceneGeoCoding()
    latlon = coding.getGeoPos(PixelPos(x, y), None)
    zone = int((latlon.lon + 180) / 6 + 1)
    utm_sn = "6"
    if latlon.lat < 0.0:
        utm_sn = "7"
    ref = SpatialReference()
    epsg = int("32" + utm_sn + str(zone))
    ref.ImportFromEPSG(epsg)
    crsWkt = ref.ExportToWkt()
    print(crsWkt)
    return crsWkt


def SceneExtent(raster):
    xmin = 0
    ymin = 0
    xmax = raster.getSceneRasterWidth()
    ymax = raster.getSceneRasterHeight()
    coding = raster.getSceneGeoCoding()
    # raster width is of image in orbit direction, not bbox
    # we need all four corner pixels because it can be ASC or DESC
    # also depening on position, minimum lon/minimum lat is not necessarily
    # western/southern border
    latlon_1 = coding.getGeoPos(PixelPos(xmin, ymin), None)
    latlon_2 = coding.getGeoPos(PixelPos(xmax, ymax), None)
    latlon_3 = coding.getGeoPos(PixelPos(xmin, ymax), None)
    latlon_4 = coding.getGeoPos(PixelPos(xmax, ymin), None)

    lon_min = min(latlon_1.lon, latlon_2.lon, latlon_3.lon, latlon_4.lon)
    lon_max = max(latlon_1.lon, latlon_2.lon, latlon_3.lon, latlon_4.lon)
    lat_min = min(latlon_1.lat, latlon_2.lat, latlon_3.lat, latlon_4.lat)
    lat_max = max(latlon_1.lat, latlon_2.lat, latlon_3.lat, latlon_4.lat)
    return lon_min, lon_max, lat_min, lat_max


def GeoJson2WKT(geojson_file):
    str = ""
    with open(geojson_file, "r") as file:
        str += file.read()
    s = shape(json.loads(str)["features"][0]["geometry"])
    return dumps(s)


# perform Apply-Orbit-File
def ApplyOrbitFile(input_product):
    parameters = HashMap()
    parameters.put("orbitType", "Sentinel Precise (Auto Download)")
    parameters.put("continueOnFail", True)
    parameters.put("polyDegree", 3)
    output_product = GPF.createProduct(
        "Apply-Orbit-File", parameters, input_product
    )
    return output_product


# perform ThermalNoiseRemoval
def ThermalNoiseRemoval(input_product):
    parameters = HashMap()
    parameters.put("selectedPolarisations", "VV,VH")
    parameters.put("reIntroduceThermalNoise", False)
    parameters.put("removeThermalNoise", True)
    output_product = GPF.createProduct(
        "ThermalNoiseRemoval", parameters, input_product
    )
    return output_product


# perform radiometric Calibration
def RCalibration(input_product, cal_measure):
    parameters = HashMap()
    parameters.put("sourceBands", "")
    if cal_measure == "Sigma0":
        parameters.put("outputSigmaBand", True)
        parameters.put("outputBetaBand", False)
    elif cal_measure == "Beta0":
        parameters.put("outputSigmaBand", False)
        parameters.put("outputBetaBand", True)
    parameters.put("outputImageScaleInDb", False)
    parameters.put("createGammaBand", False)
    parameters.put("selectedPolarisations", "")
    parameters.put("outputGammaBand", False)
    parameters.put("outputImageInComplex", False)
    parameters.put("externalAuxFile", "")
    parameters.put("auxFile", "Product Auxiliary File")
    parameters.put("createBetaBand", False)
    output_product = GPF.createProduct(
        "Calibration", parameters, input_product
    )
    return output_product


def TerrainCorrection(input_product, crsWkt, sourceBands, dem):
    parameters = HashMap()
    parameters.put("saveLatLon", False)
    parameters.put("saveIncidenceAngleFromEllipsoid", False)
    parameters.put("nodataValueAtSea", True)
    parameters.put("alignToStandardGrid", False)
    parameters.put("pixelSpacingInMeter", 10.0)
    crs = SpatialReference(crsWkt)
    crs.AutoIdentifyEPSG()
    code = crs.GetAuthorityName(None) + ":" + crs.GetAuthorityCode(None)
    parameters.put("mapProjection", code)
    parameters.put("saveBetaNought", False)
    if dem == "auto":
        parameters.put("externalDEMFile", "")
        parameters.put("demName", "SRTM 1Sec HGT")
        parameters.put("externalDEMNoDataValue", 0.0)
    else:
        parameters.put("demName", "External DEM")
        parameters.put("externalDEMNoDataValue", "-999")
        parameters.put("externalDEMFile", dem)
    parameters.put("demResamplingMethod", "BILINEAR_INTERPOLATION")
    parameters.put("imgResamplingMethod", "BILINEAR_INTERPOLATION")
    parameters.put("saveSigmaNought", False)
    parameters.put(
        "incidenceAngleForSigma0",
        "Use projected local incidence angle from DEM",
    )
    parameters.put("sourceBands", sourceBands)
    parameters.put("applyRadiometricNormalization", False)
    parameters.put("externalDEMApplyEGM", True)
    parameters.put("saveSelectedSourceBand", True)
    parameters.put("outputComplex", False)
    parameters.put("saveProjectedLocalIncidenceAngle", False)
    parameters.put(
        "incidenceAngleForGamma0",
        "Use projected local incidence angle from DEM",
    )
    parameters.put("saveGammaNought", False)
    parameters.put("saveLocalIncidenceAngle", False)
    parameters.put("standardGridOriginX", 0.0)
    parameters.put("saveDEM", False)
    parameters.put("standardGridOriginY", 0.0)
    parameters.put("pixelSpacingInDegree", "8.983152841195215E-5")
    parameters.put("externalAuxFile", "")
    parameters.put("auxFile", "Latest Auxiliary File")
    output_product = GPF.createProduct(
        "Terrain-Correction", parameters, input_product
    )
    return output_product


def ImSubset(input_product, wkt):
    # geom = WKTReader().read(crsWkt)
    parameters = HashMap()
    parameters.put("sourceBands", "")
    parameters.put("fullSwath", False)
    # parameters.put('tiePointGridNames', '')
    parameters.put("geoRegion", wkt)
    parameters.put("copyMetadata", True)
    parameters.put("region", "0,0,0,0")
    # subsetting by number of pixels
    # subsampling
    parameters.put(
        "subSamplingX", 1
    )  # one pixel, increase or decrease (under or over sampling)
    parameters.put("subSamplingY", 1)  # one pixel, increase or decrease
    output_product = GPF.createProduct("Subset", parameters, input_product)
    return output_product


def ApplyBandMath(input_target_bands, targetBands):
    parameters = HashMap()
    parameters.put("unit", "")
    parameters.put("name", "bm_name")
    parameters.put("noDataValue", 0.0)
    parameters.put("description", "")
    parameters.put("targetBands", targetBands)
    output_product = GPF.createProduct(
        "BandMaths", parameters, input_target_bands
    )
    return output_product


def CreateLayerStack(input_n_dim_array):
    parameters = HashMap()
    parameters.put("extent", "Master")
    parameters.put("resamplingType", "NONE")
    parameters.put("initialOffsetMethod", "Orbit")
    output_product = GPF.createProduct(
        "CreateStack", parameters, input_n_dim_array
    )
    return output_product


def SpeckleFilter(input_product, sourceBands, filter):
    parameters = HashMap()
    parameters.put("sourceBands", sourceBands)
    parameters.put("filter", filter)
    parameters.put("windowSize", "5x5")
    parameters.put("sigma", 0.9)
    parameters.put("targetWindowSize", "3x3")
    parameters.put("enl", 1.0)
    parameters.put("anSize", 50)
    parameters.put("filterSizeY", 3)
    parameters.put("filterSizeX", 3)
    parameters.put("numLooksStr", "1")
    parameters.put("dampingFactor", 2)
    parameters.put("estimateENL", True)
    output_product = GPF.createProduct(
        "Speckle-Filter", parameters, input_product
    )
    return output_product


def TerrainFlattening(input_product, dem):
    parameters = HashMap()
    parameters.put("additionalOverlap", 0.1)
    parameters.put("outputSimulatedImage", False)
    parameters.put("externalDEMApplyEGM", False)
    parameters.put("oversamplingMultiple", 1.5)
    if dem == "auto":
        parameters.put("demName", "SRTM 1Sec HGT")
    else:
        parameters.put("demName", "External DEM")
        parameters.put("externalDEMNoDataValue", "-999")
        parameters.put("externalDEMFile", dem)
    parameters.put("demResamplingMethod", "BILINEAR_INTERPOLATION")
    parameters.put("externalDEMNoDataValue", 0.0)
    output_product = GPF.createProduct(
        "Terrain-Flattening", parameters, input_product
    )
    return output_product


def BorderNoiseRemoval(input_product):
    parameters = HashMap()
    parameters.put("trimThreshold", 0.5)
    parameters.put("borderLimit", 500)
    # parameters.put('borderLimit', 1000)
    output_product = GPF.createProduct(
        "Remove-GRD-Border-Noise", parameters, input_product
    )
    return output_product
