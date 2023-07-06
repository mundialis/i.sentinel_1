#!/usr/bin/env python3

############################################################################
#
# MODULE:       i.sentinel_1.download_asf
#
# AUTHOR(S):    Guido Riembauer
#
# PURPOSE:      Searches and Downloads SAR data from the Alaska Satellite Facility
#
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
# % description: Searches and downloads SAR data from the Alaska Satellite Facility.
# % keyword: imagery
# % keyword: satellite
# % keyword: download
# % keyword: SAR
# % keyword: Sentinel
# %end

# %option
# % key: output
# % type: string
# % required: no
# % description: Name for output directory where to store downloaded Sentinel data
# % label: Directory where to store downloaded data
# %end

# %option
# % key: credentials
# % type: string
# % required: yes
# % multiple: no
# % description: Path to NASA EARTHDATA credentials file
# % label: File has to contain NASA EARTHDATA credentials in the format 'http-user=<USER>\nhttp-passwd=<PW>'
# %end

# %option
# % key: start
# % required: no
# % type: string
# % description: Start date ('YYYY-MM-DD')
# % guisection: Filter
# %end

# %option
# % key: end
# % required: no
# % type: string
# % description: End date ('YYYY-MM-DD')
# % guisection: Filter
# %end

# %option
# % key: platform
# % required: yes
# % type: string
# % description: Satellite platform
# % label: Currently only Sentinel-1 is supported
# % options: Sentinel-1
# % answer: Sentinel-1
# %end

# %option
# % key: processinglevel
# % required: no
# % type: string
# % description: SAR processing level
# % label: Ground-Range-Detected (GRD) or Single-Look-Complex (SLC)
# % options: GRD,SLC
# % answer: GRD
# %end

# %option
# % key: polarization
# % required: no
# % type: string
# % description: SAR polarization
# % label: Vertical (VV), Horizontal (HH), and combinations (e.g. VH)
# % options: VV,VH,VV+VH
# % answer: VV+VH
# %end

# %option
# % key: flight_dir
# % required: no
# % type: string
# % description: Satellite orbit direction during data acquisition
# % label: Satellite orbit direction during data acquisition
# % options: ASCENDING,DESCENDING
# %end

# %option
# % key: limit
# % required: no
# % type: integer
# % description: Maximum results to display/download
# % label: Maximum results to display/download
# %end

# %option
# % key: granules
# % required: no
# % type: string
# % multiple: yes
# % description: Downloads granules regardless of computational region and time
# % label: List of Sentinel-1 granules to download
# %end

# %flag
# % key: l
# % description: Only list available products and exit
# %end

# %rules
# % required: output,-l
# % required: start,granules
# % collective: start,end
# %end

import os
import sys
import csv
import atexit
import subprocess
import shutil
from datetime import datetime
from xml.dom import minidom
import grass.script as grass

rm_files = []
rm_folders = []
cur_wdir = None


def cleanup():
    for rmfile in rm_files:
        try:
            os.remove(rmfile)
        except Exception as e:
            grass.warning(_("Unable to remove file %s: %s") % (rmfile, e))
    for rmfolder in rm_folders:
        try:
            shutil.rmtree(rmfolder)
        except Exception as e:
            grass.warning(_("Unable to remove folder %s: %s") % (rmfolder, e))
    os.chdir(cur_wdir)


def main():
    global rm_files, rm_folders, cur_wdir
    cur_wdir = os.getcwd()

    # parameters
    output_folder = options["output"]
    if flags["l"]:
        output_folder = grass.tempdir()
        rm_folders.append(output_folder)
    credentials = options["credentials"]
    start = options["start"]
    end = options["end"]
    platform = options["platform"]

    # check if os is linux or mac (The aria-URL is composed differently on
    # windows, currently not implemented)
    if not (sys.platform == "linux" or sys.platform == "darwin"):
        grass.fatal(_("Sorry, only Linux/Mac is supported so far"))

    # check if aria2 is installed
    aria2_test = grass.Popen(
        "aria2c --help",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    aria2_test_resp = aria2_test.communicate()
    if len(aria2_test_resp[0]) == 0:
        grass.fatal(
            _(
                "aria2 is required for this addon, please install it first"
                + "\n"
                + "sudo apt-get install aria2"
            )
        )

    # check if end is after start
    if options["start"]:
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        now = datetime.now()
        if end_date < start_date:
            grass.fatal(_("End date is before start date"))
        elif end_date > now:
            grass.warning(
                _("End date is in the future. Setting end to today.")
            )
            end = now.strftime("%Y-%m-%d")

    # try to create the output directory
    if not os.path.isdir(output_folder):
        try:
            os.makedirs(output_folder)
        except Exception as e:
            grass.fatal(
                _("Unable to create directory %s: %s") % (output_folder, e)
            )

    # put together URL
    url = "https://api.daac.asf.alaska.edu/services/search/param?"

    if options["processinglevel"]:
        pl_url = options["processinglevel"]
        if pl_url == "GRD":
            pl_url = "GRD_HD"
            url += "processingLevel=%s&" % (pl_url)
    if options["polarization"]:
        pol_url = options["polarization"]
        if pol_url == "VV+VH":
            pol_url = "VV%2bVH"
            url += "polarization=%s&" % (pol_url)
    if options["granules"]:
        gr_url = options["granules"]
        url += "granule_list=%s&" % gr_url
    else:
        start_url = "%sT00:00:00UTC" % (start)
        end_url = "%sT23:59:59UTC" % (end)
        # get the latlon information from the region
        region_ll = grass.parse_command("g.region", flags="lg")
        polygon_url = (
            "polygon%%28%%28%s+%s,%s+%s,%s+%s,%s+%s,%s+%s%%29%%29"
            % (
                region_ll["nw_long"],
                region_ll["nw_lat"],
                region_ll["ne_long"],
                region_ll["ne_lat"],
                region_ll["se_long"],
                region_ll["se_lat"],
                region_ll["sw_long"],
                region_ll["sw_lat"],
                region_ll["nw_long"],
                region_ll["nw_lat"],
            )
        )
        url += "start=%s&end=%s&intersectsWith=%s&platform=%s&" % (
            start_url,
            end_url,
            polygon_url,
            platform,
        )

        if options["limit"]:
            mR_url = str(options["limit"])
            url += "maxResults=%s&" % (mR_url)
        if options["flight_dir"]:
            fdir_url = options["flight_dir"]
            url += "flightDirection=%s&" % (fdir_url)
    if flags["l"]:
        output_url = "CSV"
    else:
        output_url = "metalink"
    url += "output=%s" % (output_url)
    aria2_cmd = (
        "aria2c --http-auth-challenge=true --conf-path=%s"
        ' --retry-wait=30 --max-tries=20 "%s"'
    ) % (credentials, url)
    # temporarily move to output as workdir
    os.chdir(output_folder)

    # run download or list files, only show stdout of aria2c if we actually
    # download (otherwise there is no progress information)
    aria_kwargs = {"shell": "True"}
    if flags["l"]:
        aria_kwargs["stdout"] = subprocess.PIPE
    aria_process = grass.Popen(aria2_cmd, **aria_kwargs)
    aria_process.wait()

    # get file with either download summary or available data
    resultfile = None
    if len(os.listdir(output_folder)) == 0:
        grass.fatal(_("Server for Sentinel-1 data download not available"))
    for file in os.listdir(output_folder):
        if file.startswith("asf-datapool-results"):
            filepath = os.path.join(output_folder, file)
            resultfile = filepath

    # print download summary
    if not flags["l"]:
        dl_list = []
        rm_files.append(filepath)
        xml = minidom.parse(resultfile)
        files = xml.getElementsByTagName("file")
        for f in files:
            filename = "<%s>" % (f.attributes["name"].value)
            dl_list.append(filename)
        grass.message(_("Downloaded file/s\n%s" % ("\n".join(dl_list))))

    # print available files
    else:
        granule_names = []
        platforms = []
        beam_modes = []
        acq_dates = []
        proc_levels = []
        flight_dirs = []
        sizes = []
        with open(resultfile) as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                granule_names.append(row["Granule Name"])
                platforms.append(row["Platform"])
                beam_modes.append(row["Beam Mode"])
                acq_dates.append(row["Acquisition Date"])
                proc_levels.append(row["Processing Level"])
                flight_dirs.append(row["Ascending or Descending?"])
                sizes.append(row["Size (MB)"])
        if len(granule_names) == 0:
            grass.message(_("No datasets found."))
        else:
            # Print formatted result table
            print(
                "{} Datasets Found:\n{:<70} {:<13} {:<10} "
                "{:<28} {:<18} {:<18} {:<10}".format(
                    str(len(granule_names)),
                    "Granule Name",
                    "Platform",
                    "Beam Mode",
                    "Acquisition Date",
                    "Processing Level",
                    "Flight Direction",
                    "Size (MB)",
                )
            )
            for idx, name in enumerate(granule_names):
                print(
                    "{:<70} {:<13} {:<10} {:<28} {:<18} {:<18} {:<10}".format(
                        name,
                        platforms[idx],
                        beam_modes[idx],
                        acq_dates[idx],
                        proc_levels[idx],
                        flight_dirs[idx],
                        sizes[idx],
                    )
                )


if __name__ == "__main__":
    options, flags = grass.parser()
    atexit.register(cleanup)
    main()
