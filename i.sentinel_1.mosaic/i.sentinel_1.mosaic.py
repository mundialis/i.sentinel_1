#!/usr/bin/env python3

############################################################################
#
# MODULE:       i.sentinel_1.mosaic.py
#
# AUTHOR(S):    Guido Riembauer <riembauer at mundialis.de>
#
# PURPOSE:      Searches for Sentinel-1 scenes based on current region,
#               downloads, preprocesses, imports and patches.
#
# COPYRIGHT:	(C) 2020-2022 by mundialis GmbH & Co. KG and the GRASS Development Team
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
# % description: Searches for Sentinel-1 scenes based on current region, downloads, preprocesses, imports and patches.
# % keyword: imagery
# % keyword: satellite
# % keyword: Sentinel
# % keyword: SAR
# % keyword: download
# % keyword: import
# % keyword: mosaic
# %end

# %option G_OPT_F_INPUT
# % key: settings
# % label: Full path to ESA scihub settings file (user, password)
# %end

# %option G_OPT_F_INPUT
# % key: asf_credentials
# % label: Full path to asf-credentials file
# %end

# %option
# % key: start
# % type: string
# % label: Start date ('YYYY-MM-DD')
# % description: Time difference between start and end date must be within 60 days
# % guisection: Filter
# %end

# %option
# % key: end
# % type: string
# % label: End date ('YYYY-MM-DD')
# % description: Time difference between start and end date must be within 60 days
# % guisection: Filter
# %end

# %option G_OPT_F_OUTPUT
# % key: output
# % label: Output mosaicked sentinel_1 raster.
# % description: Bandname suffix (e.g. Sigma0_VV_log/Sigma0_VH_log) will be added to output raster
# % required: yes
# %end

# %option
# % key: outpath
# % type: string
# % required: no
# % multiple: no
# % label: Path to temporarily save downloaded files
# %end

# %option
# % key: bandname
# % type: string
# % required: yes
# % multiple: yes
# %label: Bands to be processed
# % description: Bands to be processed
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

# %option G_OPT_MEMORYMB
# %end

# %flag
# % key: s
# % description: Apply speckle filter
# %end


import atexit
import numpy as np
import os
import psutil
import shutil
from itertools import combinations
from pyproj import Transformer
from datetime import datetime

import grass.script as grass

# initialize global vars
rm_regions = []
rm_vectors = []
rm_rasters = []
rm_files = []
tempdirs = []
saved_region = None


def cleanup():
    nuldev = open(os.devnull, "w")
    kwargs = {"flags": "f", "quiet": True, "stderr": nuldev}
    if saved_region:
        grass.run_command("g.region", region=saved_region)
    for rmr in rm_regions:
        if rmr in [x for x in grass.parse_command("g.list", type="region")]:
            grass.run_command("g.remove", type="region", name=rmr, **kwargs)
    for rmv in rm_vectors:
        if grass.find_file(name=rmv, element="vector")["file"]:
            grass.run_command("g.remove", type="vector", name=rmv, **kwargs)
    for rmrast in rm_rasters:
        if grass.find_file(name=rmrast, element="raster")["file"]:
            grass.run_command("g.remove", type="raster", name=rmrast, **kwargs)
    for rmfile in rm_files:
        try:
            os.remove(rmfile)
        except Exception as e:
            grass.warning(_("Cannot remove file <%s>: %s" % (rmfile, e)))
    for tempdir in tempdirs:
        try:
            shutil.rmtree(tempdir)
        except Exception as e:
            grass.warning(_("Cannot remove directory <%s>: %s" % (tempdir, e)))


def freeRAM(unit, percent=100):
    """The function gives the amount of the percentages of the installed RAM.
    Args:
        unit(string): 'GB' or 'MB'
        percent(int): number of percent which shoud be used of the free RAM
                      default 100%
    Returns:
        memory_MB_percent/memory_GB_percent(int): percent of the free RAM in
                                                  MB or GB

    """
    # use psutil cause of alpine busybox free version for RAM/SWAP usage
    mem_available = psutil.virtual_memory().available
    swap_free = psutil.swap_memory().free
    memory_GB = (mem_available + swap_free) / 1024.0**3
    memory_MB = (mem_available + swap_free) / 1024.0**2

    if unit == "MB":
        memory_MB_percent = memory_MB * percent / 100.0
        return int(round(memory_MB_percent))
    elif unit == "GB":
        memory_GB_percent = memory_GB * percent / 100.0
        return int(round(memory_GB_percent))
    else:
        grass.fatal("Memory unit <%s> not supported" % unit)


def test_memory():
    # check memory
    memory = int(options["memory"])
    free_ram = freeRAM("MB", 100)
    if free_ram < memory:
        grass.warning(
            _("Using %d MB but only %d MB RAM available." % (memory, free_ram))
        )
        options["memory"] = free_ram
        grass.warning(_("Set used memory to %d MB." % (options["memory"])))


def transform_coord(array, from_epsg, to_epsg):
    transformer = Transformer.from_crs(
        "epsg:%s" % from_epsg, "epsg:%s" % to_epsg, always_xy=True
    )
    transformed = transformer.transform(array[0], array[1])
    return np.array(transformed)


def move_pointa_towards_pointb(pointa, pointb, distance):
    dist_total = np.sqrt(sum((pointa - pointb) ** 2))
    dist_prop = distance / dist_total
    dir_vector = pointb - pointa
    newpoint = pointa + dist_prop * dir_vector
    return newpoint


def shrink_footprint(input, distance, memory, unit):
    # simplify the footprint to a 4 vertex polygon and remove <distance> meters
    # on each side in range direction (orthogonal to flight direction)
    global rm_vectors, rm_rasters
    # get all vertices from the footprint
    grass.use_temp_region()
    grass.run_command("g.region", vector=input, quiet=True)
    vertices = list(
        grass.parse_command(
            "v.out.ascii", input=input, output="-", format="wkt"
        ).keys()
    )
    # get xs and ys
    nums_only = vertices[0].split("((")[1].split("))")[0].split(",")
    # add a space to first item to make it consistent
    nums_only[0] = " %s" % nums_only[0]
    # remove any remaining brackets
    nums_only_corrected = [
        item.replace(")", "").replace("(", "") for item in nums_only
    ]
    xs = [float(pair.split(" ")[1]) for pair in nums_only_corrected]
    ys = [float(pair.split(" ")[2]) for pair in nums_only_corrected]
    x_min = min(xs)
    x_max = max(xs)
    y_min = min(ys)
    y_max = max(ys)
    # the four main (corner) vertices
    pn1 = np.array((xs[ys.index(y_max)], y_max))
    ps1 = np.array((xs[ys.index(y_min)], y_min))
    pe = np.array((x_max, ys[xs.index(x_max)]))
    pw = np.array((x_min, ys[xs.index(x_min)]))
    # we need to compare the two northernmost and the two southernmost points.
    # we need to determine which from pe and pw are pn2 and ps2 (depends on orbit)
    if pe[1] > pw[1]:
        pn2 = pe
        ps2 = pw
    else:
        pn2 = pw
        ps2 = pe

    # if projection is in degrees, the points are converted to utm for
    # footprint correction to easily apply a shift in meters
    if unit.lower() == "degree":
        # get current epsg
        proj = grass.parse_command("g.proj", flags="g")
        if "epsg" in proj:
            orig_epsg = proj["epsg"]
        else:
            orig_epsg = proj["srid"].split("EPSG:")[1]
        # get target utm zone from centroid
        c = np.mean((pn1, pn2, ps1, ps2), 0)
        zone = int((c[0] + 180) / 6 + 1)
        utm_sn = "6"
        if c[1] < 0.0:
            utm_sn = "7"
        utm_epsg = int("32" + utm_sn + str(zone))
        # c
        pn1_m = transform_coord(pn1, orig_epsg, utm_epsg)
        pn2_m = transform_coord(pn2, orig_epsg, utm_epsg)
        ps1_m = transform_coord(ps1, orig_epsg, utm_epsg)
        ps2_m = transform_coord(ps2, orig_epsg, utm_epsg)
    elif unit.lower() == "meter":
        pn1_m = pn1
        ps1_m = ps1
        pn2_m = pn2
        ps2_m = ps2
    else:
        grass.fatal(_("Sorry, projection unit %s is not supported" % unit))

    # create new points
    pn1_corrected = move_pointa_towards_pointb(pn1_m, pn2_m, distance)
    pn2_corrected = move_pointa_towards_pointb(pn2_m, pn1_m, distance)
    ps1_corrected = move_pointa_towards_pointb(ps1_m, ps2_m, distance)
    ps2_corrected = move_pointa_towards_pointb(ps2_m, ps1_m, distance)
    c_corrected = np.mean(
        (pn1_corrected, pn2_corrected, ps1_corrected, ps2_corrected), 0
    )

    # if the original unit is degrees, we have to transform the new
    # coordinates back
    if unit.lower() == "degree":
        pn1_new = transform_coord(pn1_corrected, utm_epsg, orig_epsg)
        pn2_new = transform_coord(pn2_corrected, utm_epsg, orig_epsg)
        ps1_new = transform_coord(ps1_corrected, utm_epsg, orig_epsg)
        ps2_new = transform_coord(ps2_corrected, utm_epsg, orig_epsg)
        c_new = transform_coord(c_corrected, utm_epsg, orig_epsg)
    else:
        pn1_new = pn1_corrected
        pn2_new = pn2_corrected
        ps1_new = ps1_corrected
        ps2_new = ps2_corrected
        c_new = c_corrected

    newvect = "%s_shrunk" % input
    rm_vectors.append(newvect)
    # create new vector layer
    # create string to feed to v.in.ascii
    boundary_text = ["VERTI:", "B  5"]
    # build vertex order
    if pn1_new[0] > pn2_new[0]:
        points = [pn1_new, ps2_new, ps1_new, pn2_new, pn1_new]
    else:
        points = [pn1_new, pn2_new, ps1_new, ps2_new, pn1_new]
    for point in points:
        boundary_text.append("%s %s" % (str(point[0]), str(point[1])))
    boundary_text.append("C  1 1")
    boundary_text.append("%s %s" % (str(c_new[0]), str(c_new[1])))
    boundary_text.append("1 20")

    boundary_string = "\n".join(boundary_text)
    create_proc = grass.feed_command(
        "v.in.ascii",
        output=newvect,
        format="standard",
        input="-",
        separator="space",
        quiet=True,
    )
    create_proc.stdin.write(boundary_string.encode())
    create_proc.stdin.close()
    # add table and identifier column to new vector
    grass.run_command("v.db.addtable", map=newvect, quiet=True)
    identifier = list(
        grass.parse_command(
            "v.db.select", map=input, column="identifier"
        ).keys()
    )[1]

    grass.run_command(
        "v.db.addcolumn",
        map=newvect,
        columns="identifier VARCHAR(100)",
        quiet=True,
    )
    grass.run_command(
        "v.db.update",
        map=newvect,
        column="identifier",
        value=identifier,
        quiet=True,
    )

    # delete temp region so we are back at the original extent and resolution
    # for the rasterization
    grass.del_temp_region()
    newvect_rast = "%s_rast" % identifier
    rm_rasters.append(newvect_rast)
    grass.run_command(
        "v.to.rast",
        input=newvect,
        output=newvect_rast,
        use="val",
        value=1,
        memory=memory,
        quiet=True,
    )
    return newvect_rast


def main():

    global rm_regions, rm_rasters, rm_vectors, tempdir, rm_files, saved_region

    # check if we have required addons
    if not grass.find_program("i.sentinel.download", "--help"):
        grass.fatal(
            _(
                "The 'i.sentinel.download' module was not found, "
                "install it first:"
            )
            + "\n"
            + "g.extension i.sentinel"
        )
    if not grass.find_program("i.sentinel.import", "--help"):
        grass.fatal(
            _(
                "The 'i.sentinel.import' module was not found, "
                "install it first:"
            )
            + "\n"
            + "g.extension i.sentinel"
        )
    if not grass.find_program("i.sentinel_1.import", "--help"):
        grass.fatal(
            _(
                "The 'i.sentinel_1.import' module was not found, "
                "install it first:"
            )
            + "\n"
            + ("g.extension " "i.sentinel_1.import url=/path/to/addon")
        )
    if not grass.find_program("i.sentinel_1.download_asf", "--help"):
        grass.fatal(
            _(
                "The 'i.sentinel_1.download_asf' module was not found, "
                "install it first:"
            )
            + "\n"
            + ("g.extension" " i.sentinel_1.download_asf url=/path/to/addon")
        )

    # parameters
    settings = options["settings"]
    asf_credentials = options["asf_credentials"]
    start = options["start"]
    end = options["end"]
    bandnames = options["bandname"].split(",")
    output = options["output"]
    # reduce footprints by x meters in range (orthogonal to flight) direction:
    footprint_correction_m = 3000
    # get projection unit
    unit = grass.parse_command("g.proj", flags="g")["unit"]

    # avoid long runtime by restricting maximum time range to 2 months.
    # S-1 coverage should be guaranteed easily within 2 months
    start_date = datetime.strptime(start, "%Y-%m-%d")
    end_date = datetime.strptime(end, "%Y-%m-%d")
    if (end_date - start_date).days > 60:
        grass.fatal(
            _(
                "Difference between start and end date is more "
                "than 60 days, please choose shorter timerange."
            )
        )

    # save region as vector and region
    pid = os.getpid()
    region_vector = "region_vector_%s" % pid
    rm_vectors.append(region_vector)
    grass.run_command("v.in.region", output=region_vector, quiet=True)
    grass.run_command("v.db.addtable", map=region_vector, quiet=True)

    saved_region = "saved_region_%s" % pid
    rm_regions.append(saved_region)
    grass.run_command("g.region", save=saved_region)

    # Download footprints
    footprint_vect = "footprint_vect_%s" % pid
    rm_vectors.append(footprint_vect)
    scene_intersect_parse = grass.parse_command(
        "i.sentinel.download",
        settings=settings,
        start=start,
        end=end,
        producttype="GRD",
        footprints=footprint_vect,
        area_relation="Intersects",
        flags="l",
        quiet=True,
    )
    if len(scene_intersect_parse) == 0:
        grass.fatal(
            _("No input scenes found between %s and %s" % (start, end))
        )
    grass_resp = list(scene_intersect_parse.keys())
    # list of all scenes that intersect with the region
    scenes_intersect = [scene.split(" ")[1] for scene in grass_resp]
    # correct the footprints in range direction
    grass.message(_("Correcting Sentinel-1 footprints..."))
    # if the location is using degrees, we have to set the region resolution to
    # the equivalent of a 10m resolution to get a proper rasterized version of
    # the footprint assuming  Latitude:  1 deg = 111 km (+/- 0.5 km)
    #                         Longitude: 1 deg = 111.320*cos(latitude) km
    # if the location is in metres, it can be left as it is
    if unit == "degree":
        nsres = float(10 / 111000)
        # get the latitude from the region center
        lat = float(
            grass.parse_command("g.region", flags="gc")["center_northing"]
        )
        ewres = float(10 / (111320 * np.cos(np.radians(lat))))
        # shrink_footprint() and r.s1.grd.import use grass.use_temp_region() so
        # we cant use it here. Region is fixed here and rolled back during
        # cleanup
        grass.run_command(
            "g.region",
            vector=region_vector,
            nsres=nsres,
            ewres=ewres,
            flags="a",
        )

    footprints_corrected = []
    test_memory()
    for scene in scenes_intersect:
        # get individual footprints and dissolve. this is necessary because
        # the footprints consist of individual overlap areas
        footprint_extracted = "extracted_%s_%s" % (grass.tempname(5), pid)
        rm_vectors.append(footprint_extracted)
        grass.run_command(
            "v.extract",
            input=footprint_vect,
            output=footprint_extracted,
            where="identifier='%s'" % scene,
            quiet=True,
        )
        footprint_dissolved = "dissolved_%s_%s" % (grass.tempname(5), pid)
        rm_vectors.append(footprint_dissolved)
        grass.run_command(
            "v.dissolve",
            input=footprint_extracted,
            output=footprint_dissolved,
            column="identifier",
            quiet=True,
        )
        reduced_footprint = shrink_footprint(
            footprint_dissolved,
            footprint_correction_m,
            options["memory"],
            unit,
        )
        footprints_corrected.append(reduced_footprint)

    # before looping through different scene combinations: check if full
    # coverage can be achieved with ALL scenes (avoid looping through all
    # combinations and only find at the end that there are not enough scenes)

    all_scenes_rast = "all_scenes_rast_%s" % pid
    rm_rasters.append(all_scenes_rast)
    expression_str = "%s = %s" % (
        all_scenes_rast,
        "|||".join(footprints_corrected),
    )
    grass.run_command("r.mapcalc", expression=expression_str, quiet=True)
    null_cells_all = int(
        grass.parse_command("r.univar", map=all_scenes_rast, flags="g")[
            "null_cells"
        ]
    )
    if null_cells_all > 0:
        grass.fatal(
            _(
                "No full coverage with Sentinel-1 scenes can"
                " be achieved. Try again with a wider timerange."
            )
        )

    # optimal scenario: only one scene is required, increment if necessary
    grass.message(_("Searching for optimum scene combination..."))
    scenes_to_import = []
    combination_length = 1
    max_found = 0
    while max_found == 0:
        all_combs = list(
            combinations(footprints_corrected, combination_length)
        )
        for combi in all_combs:
            if len(combi) == 1:
                null_cells = int(
                    grass.parse_command("r.univar", map=combi[0], flags="g")[
                        "null_cells"
                    ]
                )
                if null_cells == 0:
                    scenes_to_import.append(combi[0].split("_rast")[0])
                    max_found = 1
                    break
            else:
                combi_rast = "combi_rast_%s_%s" % (grass.tempname(5), pid)
                rm_rasters.append(combi_rast)
                mapcalc_str = "%s = " % combi_rast + "|||".join(combi)
                grass.run_command(
                    "r.mapcalc", expression=mapcalc_str, quiet=True
                )
                null_cells = int(
                    grass.parse_command("r.univar", map=combi_rast, flags="g")[
                        "null_cells"
                    ]
                )
                # manually remove combi_rast here so the mapset does not get
                # too full
                grass.run_command(
                    "g.remove",
                    type="raster",
                    name=combi_rast,
                    flags="f",
                    quiet=True,
                )
                if null_cells == 0:
                    scenes_to_import.extend(
                        [rast.split("_rast")[0] for rast in combi]
                    )
                    max_found = 1
                    break

        if max_found == 1:
            break
        elif combination_length < len(footprints_corrected):
            combination_length += 1
        else:
            # in theory this should never happen
            grass.fatal(
                _(
                    "No full coverage with Sentinel-1 scenes can"
                    " be achieved. Try again with a wider timerange."
                )
            )

    grass.message(
        _(
            "Scene/s %s cover the current region, downloading..."
            % (", ".join(scenes_to_import))
        )
    )

    # download the data from ASF
    outpath = options["outpath"]
    if not outpath:
        outpath = grass.tempdir()
        tempdirs.append(outpath)
    else:
        if not os.path.isdir(outpath):
            try:
                os.makedirs(outpath)
            except Exception as e:
                grass.fatal(
                    _("Unable to create directory <%s>: %s" % (outpath, e))
                )

    grass.run_command(
        "i.sentinel_1.download_asf",
        output=outpath,
        credentials=asf_credentials,
        processinglevel="GRD",
        granules=",".join(scenes_to_import),
        quiet=True,
    )
    s1_zips = [
        os.path.join(outpath, "%s.zip" % scene) for scene in scenes_to_import
    ]
    rm_files = s1_zips

    # import S-1 scenes into GRASS
    scenes_imported = []
    outpath_import = os.path.join(outpath, "s1_grd_processing")
    tempdirs.append(outpath_import)
    for idx, s1_file in enumerate(s1_zips):
        params = {
            "input": s1_file,
            "outpath": outpath_import,
            "extent": "region",
            "memory": options["memory"],
            "bandname": options["bandname"],
        }
        if options["external_dem"]:
            params["external_dem"] = options["external_dem"]
        if flags["s"]:
            params["flags"] = "s"

        grass.run_command("r.s1.grd.import", **params, quiet=True)
        for bandname in bandnames:
            imported_scene = "%s_%s_log" % (scenes_to_import[idx], bandname)
            scenes_imported.append(imported_scene)
            rm_rasters.append(imported_scene)

    # patch it together
    for bandname in bandnames:
        rasters_to_patch = [
            scene for scene in scenes_imported if bandname in scene
        ]
        output_name = "%s_%s_log" % (output, bandname)
        if len(rasters_to_patch) == 1:
            grass.run_command(
                "g.copy",
                raster="%s,%s" % (rasters_to_patch[0], output_name),
                quiet=True,
            )
        else:
            grass.run_command(
                "r.patch",
                input=rasters_to_patch,
                output=output_name,
                quiet=True,
            )
        grass.message(_("Generated output raster <%s>" % output_name))


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
