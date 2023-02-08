#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      i.sentinel_1.import
# AUTHOR(S):   Hajar Benelcadi and
#              Guido Riembauer, <riembauer at mundialis.de>
#
# PURPOSE:     Uses snappy (SNAP ESA) to preprocess and import
#              Sentinel 1 GRD data
#
# COPYRIGHT:   (C) 2020-2022 by mundialis GmbH & Co. KG and the GRASS Development Team
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#############################################################################
# %Module
# % description: Uses snappy (SNAP ESA) to preprocess and import Sentinel 1 GRD data.
# % keyword: display
# % keyword: raster
# % keyword: Sentinel
# % keyword: SAR
# % keyword: satellite
# % keyword: snappy
# %End

# %option
# % key: input
# % type: string
# % required: yes
# % multiple: no
# % label: Path to the S-1 scene
# % description: Sentinel-1 data must be in .zip format
# %end

# %option
# % key: outpath
# % type: string
# % required: yes
# % multiple: no
# % label: Path to store BEAM-DIMAPs as intermediate products
# %end

# %option G_OPT_MEMORYMB
# %end

# %option
# % key: extent
# % type: string
# % required: no
# % multiple: no
# % label: Extent of imported raster map
# % options: input,region
# % answer: input
# %end

# %option
# % key: bandname
# % type: string
# % required: yes
# % multiple: yes
# %label: Bands to process
# % description: Bands to process
# % options: Sigma0_VV,Sigma0_VH,Gamma0_VV,Gamma0_VH
# % answer: Sigma0_VV,Sigma0_VH
# %end

# %option
# % key: external_dem
# % type: string
# % required: no
# % multiple: no
# % label: Path to locally stored DEM
# % description: Path to locally stored DEM to perform terrain correction
# %end

# %flag
# % key: s
# % description: Apply speckle filter
# %end


import os
import atexit
import shutil
import grass.script as grass
import snappy
import sys

try:
    from snappy import ProductIO
    from snappy import GPF
except Exception:
    grass.error(
        _(
            "ESA SNAP installation not found (https://senbox.atlassian.net/wiki/spaces/SNAP/pages/50855941/Configure+Python+to+use+the+SNAP-Python+snappy+interface)."
        )
    )

rm_rasters = []
temp_dem = None

sys.path.insert(
    1, os.path.join(os.path.dirname(sys.path[0]), "etc", "i.sentinel_1.import")
)


def cleanup():
    nuldev = open(os.devnull, "w")
    kwargs = {"flags": "f", "quiet": True, "stderr": nuldev}
    for rmrast in rm_rasters:
        if grass.find_file(name=rmrast, element="raster")["file"]:
            grass.run_command("g.remove", type="raster", name=rmrast, **kwargs)
    try:
        os.remove(temp_dem)
        os.remove(temp_dem + ".aux.xml")
    except Exception:
        grass.warning(_("Cannot not remove <%s>" % temp_dem))


def main():
    global rm_rasters, temp_dem
    from SnappyFunctions import (
        AutoDetectUtmZone,
        ApplyOrbitFile,
        ThermalNoiseRemoval,
        RCalibration,
        BorderNoiseRemoval,
    )
    from SnappyFunctions import (
        TerrainCorrection,
        SpeckleFilter,
        TerrainFlattening,
        SceneExtent,
        ImSubset,
    )

    fileimage = options["input"]
    bandname = options["bandname"]
    outpath = options["outpath"]
    memory = int(options["memory"])
    extent = options["extent"]
    speckle = flags["s"]
    ext_dem = options["external_dem"]
    if ext_dem:
        if not os.path.exists(ext_dem):
            grass.fatal(_("File {name} not found.".format(name=ext_dem)))
    else:
        dem = "auto"

    gamma = False
    if "Gamma" in bandname:
        gamma = True

    # Hashmap is used to give us access to all JAVA oerators
    GPF.getDefaultInstance().getOperatorSpiRegistry().loadOperatorSpis()
    # HashMap = snappy.jpy.get_type("java.util.HashMap")
    File = snappy.jpy.get_type("java.io.File")

    if not os.path.exists(fileimage):
        grass.fatal(_("File {name} not found.".format(name=fileimage)))

    if not fileimage.endswith(".zip"):
        grass.fatal(_("Input is not a Sentinel-1 .zip file"))

    if not os.path.isdir(outpath):
        try:
            os.makedirs(outpath)
        except Exception:
            grass.fatal(_("Unable to create output directory"))

    base = os.path.basename(fileimage)
    filename = os.path.splitext(base)[0]

    im_ts_n = ProductIO.readProduct(fileimage)
    grass.message(_("Reading from file %s..." % input))

    im_crsWkt = AutoDetectUtmZone(im_ts_n)

    # get dem if external dem is used

    if extent == "region":
        bbox = grass.parse_command("g.region", flags="gb")
        lon_min = float(bbox["ll_w"])
        lon_max = float(bbox["ll_e"])
        lat_min = float(bbox["ll_s"])
        lat_max = float(bbox["ll_n"])
        wkt_temp = (
            "POLYGON ((%(lon_min)s %(lat_min)s,"
            + "%(lon_max)s %(lat_min)s,"
            + "%(lon_max)s %(lat_max)s,"
            + "%(lon_min)s %(lat_max)s,"
            + "%(lon_min)s %(lat_min)s))"
        )
        wkt = wkt_temp % {
            "lon_min": lon_min,
            "lon_max": lon_max,
            "lat_min": lat_min,
            "lat_max": lat_max,
        }
    elif extent == "input":
        lon_min, lon_max, lat_min, lat_max = SceneExtent(im_ts_n)

    if ext_dem:
        from osgeo import gdal

        # cut the extent from the external dem using gdal
        temp_dem = os.path.join(outpath, "temporary_dem_%s.tif" % os.getpid())
        dem_data = gdal.Open(ext_dem)
        dem_data = gdal.Translate(
            temp_dem,
            dem_data,
            projWin=[lon_min, lat_max, lon_max, lat_min],
            noData=-999,
        )
        dem_data = None

        # test if dem contains values
        info = gdal.Info(temp_dem, stats=True)
        valpercent = [
            item
            for item in info.split("\n")
            if "STATISTICS_VALID_PERCENT" in item
        ][0].split("=")[1]
        if valpercent == "0":
            grass.fatal(
                _(
                    "No DEM values available in external DEM with extent = %s"
                    % extent
                )
            )

        dem = temp_dem

    # perform Border Noise Removal. This step has to come first to be applied
    # properly. also it only works if the VV band is used as input
    # (either alone or together with VH)
    im_ts_n_bnr = BorderNoiseRemoval(im_ts_n)
    grass.message("BorderNoiseRemoval...")

    # perform ApplyOrbitFile
    im_ts_n_bnr_orb = ApplyOrbitFile(im_ts_n_bnr)
    grass.message(_("Applying Orbit-File..."))

    # apply subsetting if extent = region
    if extent == "region":
        # calculate subset
        im_ts_n_bnr_orb_subs = ImSubset(im_ts_n_bnr_orb, wkt)
        grass.message(_("Subsetting..."))
    else:
        # subsetting is not necessary if an external dem is provided because
        # the external dem is automatically subsetted during terrain correction
        im_ts_n_bnr_orb_subs = im_ts_n_bnr_orb

    # perform ThermalNoiseRemoval
    im_ts_n_bnr_orb_subs_tnr = ThermalNoiseRemoval(im_ts_n_bnr_orb_subs)
    grass.message(_("ThermalNoiseRemoval..."))

    # perform radiometric calibration
    cal_measure = "Sigma0"
    if gamma:
        # if gamma0 is selected, the data has to be calibrated to beta0 first
        # and terrain flattened to gamma0 afterwards
        cal_measure = "Beta0"

    im_ts_n_bnr_orb_subs_tnr_c = RCalibration(
        im_ts_n_bnr_orb_subs_tnr, cal_measure
    )
    grass.message(_("Calibration to %s..." % (cal_measure)))

    # apply terrain flattening if we want gamma0
    if gamma:
        im_ts_n_bnr_orb_subs_tnr_c_tf = TerrainFlattening(
            im_ts_n_bnr_orb_subs_tnr_c, dem
        )
        grass.message(_("TerrainFlattening to %s..." % (bandname)))
        im_ts_n_bnr_orb_subs_tnr_cal = im_ts_n_bnr_orb_subs_tnr_c_tf
    else:
        im_ts_n_bnr_orb_subs_tnr_cal = im_ts_n_bnr_orb_subs_tnr_c

    # perform speckle filtering
    if speckle:
        grass.message(_("Speckle-Filtering..."))
        im_ts_n_bnr_orb_subs_tnr_cal_sp = SpeckleFilter(
            im_ts_n_bnr_orb_subs_tnr_cal, bandname, "Lee Sigma"
        )
    else:
        im_ts_n_bnr_orb_subs_tnr_cal_sp = im_ts_n_bnr_orb_subs_tnr_cal

    # perform Terrain correction
    grass.message(_("Terrain-Correction..."))
    exp_product = TerrainCorrection(
        im_ts_n_bnr_orb_subs_tnr_cal_sp, im_crsWkt, bandname, dem
    )

    # writing to BEAM
    grass.message(_("Exporting to BEAM-DIMAP..."))
    mapname = "%s" % (filename)
    mapnamedim = "%s.dim" % (mapname)
    outname = os.path.join(outpath, mapnamedim)
    # out_dim = ProductIO.writeProduct(
    ProductIO.writeProduct(
        exp_product, File(outname), "BEAM-DIMAP", True
    )
    # importing to GRASS
    # open the .data folder:
    datafolder = os.path.splitext(outname)[0] + ".data"
    for file in os.listdir(datafolder):
        if file.endswith(".img"):
            filepath = os.path.join(datafolder, file)
            grassname = "%s_%s" % (mapname, file.split(".")[0])
            import_kwargs = {
                "input": filepath,
                "output": grassname,
                "memory": memory,
                "extent": extent,
            }
            locprojunit = grass.parse_command("g.proj", flags="g")["units"]
            if locprojunit == "meters":
                import_kwargs["resample"] = "bilinear"
                import_kwargs["resolution"] = "value"
                import_kwargs["resolution_value"] = "10"
            grass.run_command("r.import", **import_kwargs, overwrite=True)
            rm_rasters.append(grassname)
            grass.use_temp_region()
            grass.message(_("Setting 0 to NoData"))
            grass.run_command("g.region", raster=grassname, flags="ap")
            grass.run_command("r.null", map=grassname, setnull="0")
            grass.message(_("Calculating to dB"))
            grass.run_command(
                "r.mapcalc",
                expression="%s = float(10*log(%s,10))"
                % (grassname + "_log", grassname),
                overwrite=True,
            )
            grass.del_temp_region()

    # delete BEAM-DIMAPs
    # to do: put in cleanup function, didnt work so far
    try:
        shutil.rmtree(datafolder)
        os.remove(outname)
    except Exception:
        grass.warning("Unable to delete temporary data")


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
