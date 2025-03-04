#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      i.forest.mask
# AUTHOR(S):   Johannes Halbauer
#
# PURPOSE:     Creates forest mask based on monthly Sentinel-1 mosaics
#
# COPYRIGHT:   (C) 2024 by mundialis GmbH & Co. KG and the GRASS
#              Development Team
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
############################################################################

# %Module
# % description: Creates Sentinel-1 monthly mosaic based forest mask
# % keyword: imagery
# % keyword: Sentinel-1
# % keyword: forest
# %end

# %option G_OPT_V_INPUT
# % key: aoi
# % description: Vector map to restrict mask creation to
# % required: no
# %end

# %option G_OPT_R_INPUT
# % key: sar_img_vv
# % description: Raster map containing VV SAR image (db)
# % required: yes
# %end

# %option G_OPT_R_INPUT
# % key: sar_img_vh
# % description: Raster map containing VH SAR image (db)
# % required: yes
# %end

# %option G_OPT_R_OUTPUT
# % key: forest_mask
# % description: Name of output raster map containing the forest mask
# % required: yes
# %end

# %option G_OPT_V_OUTPUT
# % key: forest_mask_vect
# % description: Name of output vector map containing the forest mask
# % required: no
# %end

# %flag
# % key: v
# % description: Vectorize forest map
# %end


import atexit
import grass.script as grass
from grass_gis_helpers.cleanup import general_cleanup

# set global variables
ID = grass.tempname(12)
ORIG_REGION = f"original_region_{ID}"
rm_rast = []
rm_vec = []
rm_groups = []


def cleanup():
    general_cleanup(
        rm_rasters=rm_rast,
        rm_vectors=rm_vec,
        rm_groups=rm_groups,
        orig_region=ORIG_REGION,
    )


def calc_vv_vh_ratio_and_rvi(vv_db, vh_db):
    """Transform SAR images from db to linear scale and
    calculate VV/Vh ratio and Radar Vegetation Index
    Args:
        vv_db (str): Name of VV SAR image (db)
        vh_db (str): Name of VH SAR image (db)
    Returns:
        vv_vh_ratio_lin (str): Name of VV/VH ratio (lin) raster map
        rvi_lin (str): Name of Radar Vegetation Index (lin) raster map
    """
    # transform input SAR images to linear scale
    sar_img_vv_lin = f"sar_img_vv_lin_{ID}"
    sar_img_vh_lin = f"sar_img_vh_lin_{ID}"
    grass.run_command(
        "r.mapcalc",
        expression=f"{sar_img_vv_lin}=10^({vv_db}/10.0)",
        quiet=True,
    )
    rm_rast.append(sar_img_vv_lin)
    grass.run_command(
        "r.mapcalc",
        expression=f"{sar_img_vh_lin}=10^({vh_db}/10.0)",
        quiet=True,
    )
    rm_rast.append(sar_img_vh_lin)

    # define VV/VH ratio raster map name
    vv_vh_ratio_lin = f"vv_vh_ratio_lin_{ID}"

    # calculate VV/VH ratio (lin)
    grass.run_command(
        "r.mapcalc",
        expression=f"{vv_vh_ratio_lin}={sar_img_vv_lin}/{sar_img_vh_lin}",
        quiet=True,
    )
    rm_rast.append(vv_vh_ratio_lin)

    # define Radar Vegetation Index raster map name
    rvi_lin = f"rvi_lin_{ID}"

    # calculate Radar Vegetation Index (lin)
    grass.run_command(
        "r.mapcalc",
        expression=f"{rvi_lin}=(4*{sar_img_vh_lin})/({sar_img_vv_lin}+{sar_img_vh_lin})",
        quiet=True,
    )
    rm_rast.append(rvi_lin)

    return vv_vh_ratio_lin, rvi_lin


def create_forest_segments(seg_group, core_forest_mask):
    """Create segments and extract forest segments
    Args:
        seg_group (str): Name of raster map group to use for segmentation
        core_forest_mask (str): Name of pixel-based core forest mask
    Returns:
        forest_seg_vect (str): Name of forest segments vector map
    """
    # segmentation based on group
    segments = f"segements_{ID}"
    grass.run_command(
        "i.segment",
        group=seg_group,
        output=segments,
        threshold=0.017,
        iterations=30,
        overwrite=True,
    )
    rm_rast.append(segments)

    # vectorize segments
    vh_seg_vect = f"vh_seg_vect_{ID}"
    grass.run_command(
        "r.to.vect",
        input=segments,
        output=vh_seg_vect,
        type="area",
        overwrite=True,
    )
    rm_vec.append(vh_seg_vect)

    # define segments overlapping with core forest areas as forest
    grass.run_command(
        "v.rast.stats",
        map=vh_seg_vect,
        raster=core_forest_mask,
        column_prefix="core",
        method="number,sum",
        overwrite=True,
    )

    # extract forest segments
    forest_seg_vect = f"forest_segments_vect_{ID}"
    grass.run_command(
        "v.extract",
        input=vh_seg_vect,
        output=forest_seg_vect,
        where="(core_sum / core_number) > 0.01",
        overwrite=True,
    )
    rm_vec.append(forest_seg_vect)

    return forest_seg_vect


def smooth_forest_mask(forest_seg_vect, final_forest_mask):
    """Rasterize and smooth forest segments
    Args:
        forest_seg_vect (str): Name of forest segments vector map
        final_forest_mask (str): Name of resulting raster map
    """
    # convert forest segments to raster
    forest_seg_rast = f"forest_seg_rast_{ID}"
    grass.run_command(
        "v.to.rast",
        input=forest_seg_vect,
        output=forest_seg_rast,
        use="val",
        value=1,
        overwrite=True,
        quiet=True,
    )
    rm_rast.append(forest_seg_rast)

    # smooth forest segments raster map
    forest_seg_rast_smooth = f"forest_seg_rast_smooth_{ID}"
    grass.run_command(
        "r.neighbors",
        input=forest_seg_rast,
        output=forest_seg_rast_smooth,
        size=3,
        method="median",
        overwrite=True,
        quiet=True,
    )
    rm_rast.append(forest_seg_rast_smooth)

    # remove through median filter added additional extends
    grass.run_command(
        "r.grow",
        input=forest_seg_rast_smooth,
        output=final_forest_mask,
        radius=-1,
        overwrite=True,
        quiet=True,
    )
    grass.message(_(f"Created raster map <{final_forest_mask}>."))


def main():
    # set input variables
    if options["aoi"]:
        aoi = options["aoi"]
    else:
        aoi = None

    sar_img_vv_db = options["sar_img_vv"]
    sar_img_vh_db = options["sar_img_vh"]

    # set output variables
    final_forest_mask = options["forest_mask"]

    if options["forest_mask_vect"]:
        final_forest_mask_vect = options["forest_mask_vect"]
    else:
        final_forest_mask_vect = None
    if flags["v"] and not final_forest_mask_vect:
        grass.fatal(_("-v flag set, but option <forest_mask_vect> not given."))

    # set region
    if aoi:
        grass.run_command("g.region", save=ORIG_REGION)
        grass.run_command("g.region", vector=aoi)
    else:
        grass.run_command("g.region", save=ORIG_REGION)
        grass.run_command("g.region", raster=sar_img_vv_db)

    # calculate VV/VH ratio and RVI
    vv_vh_ratio_lin, rvi_lin = calc_vv_vh_ratio_and_rvi(
        sar_img_vv_db, sar_img_vh_db
    )

    # calculate core forest mask
    core_forest_mask = f"core_forest_mask_temp_{ID}"
    grass.run_command(
        "r.mapcalc",
        expression=f"{core_forest_mask}=if({sar_img_vh_db} > -28 && {vv_vh_ratio_lin} > 10.0 && {vv_vh_ratio_lin} < 20.0 && {rvi_lin} > 0.2, 1, 0)",
        quiet=True,
    )
    rm_rast.append(core_forest_mask)

    # create raster map group to create segments
    seg_group = f"seg_group_{ID}"
    grass.run_command(
        "i.group",
        group=seg_group,
        input=f"{sar_img_vh_db},{vv_vh_ratio_lin},{rvi_lin}",
        quiet=True,
    )
    rm_groups.append(seg_group)

    # perform segmentation and forest extraction
    forest_seg_vect = create_forest_segments(seg_group, core_forest_mask)

    # smooth raster forest segments
    smooth_forest_mask(forest_seg_vect, final_forest_mask)

    # convert forest mask raster map to vector map
    if flags["v"]:
        grass.run_command(
            "r.to.vect",
            input=final_forest_mask,
            output=final_forest_mask_vect,
            type="area",
            overwrite=True,
            quiet=True,
        )
        grass.message(_(f"Created vector map <{final_forest_mask_vect}>."))


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
