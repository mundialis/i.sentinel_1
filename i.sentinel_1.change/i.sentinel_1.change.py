#!/usr/bin/env python3
#
############################################################################
#
# MODULE:      i.sentinel_1.change
# AUTHOR(S):   Guido Riembauer, <riembauer at mundialis.de>
#
# PURPOSE:     extracts changes from Sentinel-1 Scenes from two dates
# COPYRIGHT:   (C) 2021-2022 mundialis GmbH & Co. KG, and the GRASS Development Team
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
# % description: Extracts changes from Sentinel-1 Scenes from two dates.
# % keyword: imagery
# % keyword: Sentinel
# % keyword: satellite
# % keyword: change
# %End

# %option G_OPT_R_INPUT
# % key: date1_vv
# % label: Input raster map of first date in VV polarization (dB)
# %end

# %option G_OPT_R_INPUT
# % key: date1_vh
# % label: Input raster map of first date in VH polarization (dB)
# %end

# %option G_OPT_R_INPUT
# % key: date2_vv
# % label: Input raster map of second date in VV polarization (dB)
# %end

# %option G_OPT_R_INPUT
# % key: date2_vh
# % label: Input raster map of second date in VH polarization (dB)
# %end

# %option
# % key: change_threshold
# % type: double
# % label: Minimum change in ratio (date2/date1) map to be considered (all areas with values from (1-<change_threshold>) to (1+<change_threshold>) will be considered unchanged)
# % options: 0.0-1.0
# % answer: 0.75
# %end

# %option
# % key: min_size
# % type: double
# % label: Minimum size of identified changed areas in ha
# % answer: 1.0
# %end

# %option G_OPT_R_OUTPUT
# % key: output
# % label: Output raster map containing areas of change
# %end


import grass.script as grass
import os
import atexit

rm_rasters = []


def cleanup():
    nuldev = open(os.devnull, "w")
    kwargs = {"flags": "f", "quiet": True, "stderr": nuldev}
    for rmrast in rm_rasters:
        if grass.find_file(name=rmrast, element="raster")["file"]:
            grass.run_command("g.remove", type="raster", name=rmrast, **kwargs)


def main():

    global rm_rasters
    date1_vv = options["date1_vv"]
    date1_vh = options["date1_vh"]
    date2_vv = options["date2_vv"]
    date2_vh = options["date2_vh"]
    minsize_ha = options["min_size"]
    change_thresh = float(options["change_threshold"])
    output = options["output"]

    pid_str = str(os.getpid())
    tmp_ratio_vv = "ratio_vv_{}".format(pid_str)
    tmp_ratio_vh = "ratio_vh_{}".format(pid_str)
    rm_rasters.extend([tmp_ratio_vv, tmp_ratio_vh])
    # calculate ratios of natural values (10^(<db_val/10>)) to get positive
    # numbers only
    exp_ratio_vv = "{} = float(10^({}/10))/float(10^({}/10))".format(
        tmp_ratio_vv, date2_vv, date1_vv
    )
    exp_ratio_vh = "{} = float(10^({}/10))/float(10^({}/10))".format(
        tmp_ratio_vh, date2_vh, date1_vh
    )
    for exp in [exp_ratio_vv, exp_ratio_vh]:
        grass.message(_("Calculating ratio raster {}...").format(exp.split("=")[0]))
        grass.run_command("r.mapcalc", expression=exp, quiet=True)

    result_rasts = []
    for idx, tuple in enumerate([(tmp_ratio_vv, "vv"), (tmp_ratio_vh, "vh")]):
        ratio = tuple[0]
        grass.message(_("Smoothing ratio raster {}...").format(ratio))

        ratio_smoothed = "{}_tmp_{}_smoothed".format(ratio, idx)
        rm_rasters.append(ratio_smoothed)
        grass.run_command(
            "r.neighbors",
            input=ratio,
            method="median",
            size=9,
            output=ratio_smoothed,
            quiet=True,
        )

        # apply thresholds
        upper_thresh_orig = 1.0 + change_thresh
        lower_thresh_orig = 1.0 - change_thresh
        change_raster = f"{ratio_smoothed}_changes"
        rm_rasters.append(change_raster)
        result_rasts.append(change_raster)
        ch_exp = (
            f"{change_raster} = if({ratio}>={upper_thresh_orig},1,"
            f"if({ratio}<={lower_thresh_orig},2,null()))"
        )
        grass.run_command("r.mapcalc", expression=ch_exp, quiet=True)

    patched = f"changes_patched_{pid_str}"
    rm_rasters.append(patched)
    grass.run_command("r.patch", input=result_rasts, output=patched, quiet=True)

    no_contradictions = f"no_contradictions_{pid_str}"
    rm_rasters.append(no_contradictions)
    contr_exp = (
        f"{no_contradictions} = if(({result_rasts[0]}+"
        f"{result_rasts[1]})==3,null(),{patched})"
    )
    grass.run_command("r.mapcalc", expression=contr_exp, quiet=True)
    try:
        grass.run_command(
            "r.reclass.area",
            input=no_contradictions,
            output=output,
            mode="greater",
            value=minsize_ha,
            quiet=True,
        )
    except Exception as e:
        # reclass.area fails if there are no areas larger than minsize_ha
        grass.warning(
            _(
                f"An Exception occured in r.reclass.area: {e}\n"
                f"No areas larger than {minsize_ha} ha found. "
                "Producing an output raster without changes..."
            )
        )
        grass.run_command("r.mapcalc", expression=f"{output} = null()", quiet=True)

    # adapt the colors
    grass.run_command("r.null", null=0, map=output, quiet=True)
    colors_new = ["0 255:255:255", "1 0:200:0", "2 200:0:0"]
    color_str = "\n".join(colors_new)
    col_proc = grass.feed_command("r.colors", map=output, rules="-", quiet=True)
    col_proc.stdin.write(color_str.encode())
    col_proc.stdin.close()
    col_proc.wait()

    # adapt the category labels
    labels = ["0:No signficant Change", "1:Signal Increase", "2:Signal Decrease"]
    category_text = "\n".join(labels)

    # assign labels
    cat_proc = grass.feed_command("r.category", map=output, rules="-", separator=":")
    cat_proc.stdin.write(category_text.encode())
    cat_proc.stdin.close()
    # feed_command does not wait until finished
    cat_proc.wait()

    grass.message(_(f"Successfully created output raster map <{output}>"))
    return 0


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
