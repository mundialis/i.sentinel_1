#!/usr/bin/env python3
############################################################################
#
# MODULE:      i.sentinel_1.change test
# AUTHOR(S):   Guido Riembauer
#
# PURPOSE:     Tests i.sentinel_1.change GRASS module
# COPYRIGHT:   (C) 2021-2022 mundialis GmbH & Co. KG, and the GRASS
#              Development Team
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

import os

from grass.gunittest.case import TestCase
from grass.gunittest.main import test
from grass.gunittest.gmodules import SimpleModule
import grass.script as grass


class TestISentinel1Change(TestCase):
    """Test class"""

    pid_str = str(os.getpid())
    # from the nc_spm dataset:
    reg_n = 228520
    reg_s = 214970
    reg_w = 629990
    reg_e = 645020
    # to be generated:
    date1 = f"date1_{pid_str}"
    date2 = f"date2_{pid_str}"
    # The two environmental variables must point to the respective credentials
    # files
    s2_creds = os.environ["S2_CREDENTIALS_PATH"]
    asf_creds = os.environ["ASF_CREDENTIALS_PATH"]
    change_map = f"s1_change_map_{pid_str}"
    old_region = f"old_region_{pid_str}"

    @classmethod
    # pylint: disable=invalid-name
    def setUpClass(cls):
        """Ensures expected computational region and generated data"""
        grass.run_command("g.region", save=cls.old_region)
        grass.run_command(
            "g.region",
            n=cls.reg_n,
            s=cls.reg_s,
            w=cls.reg_w,
            e=cls.reg_e,
            res=10,
            flags="a",
        )
        # download and import Sentinel-1 data from date 1
        grass.run_command(
            "i.sentinel_1.mosaic",
            settings=cls.s2_creds,
            asf_credentials=cls.asf_creds,
            start="2017-07-01",
            end="2017-07-15",
            output=cls.date1,
            bandname="Gamma0_VV,Gamma0_VH",
            flags="s",
            quiet=True,
        )
        # download and import Sentinel-1 data from date 2
        grass.run_command(
            "i.sentinel_1.mosaic",
            settings=cls.s2_creds,
            asf_credentials=cls.asf_creds,
            start="2020-07-01",
            end="2020-07-15",
            output=cls.date2,
            bandname="Gamma0_VV,Gamma0_VH",
            flags="s",
            quiet=True,
        )

    @classmethod
    # pylint: disable=invalid-name
    def tearDownClass(cls):
        """Remove the temporary region and generated data"""
        grass.run_command("g.region", region=cls.old_region)
        grass.run_command(
            "g.remove",
            type="raster",
            name=(
                f"{cls.date1}_Gamma0_VV_log,"
                f"{cls.date1}_Gamma0_VH_log,"
                f"{cls.date2}_Gamma0_VV_log,"
                f"{cls.date2}_Gamma0_VH_log"
            ),
            flags="f",
        )
        grass.run_command(
            "g.remove", type="region", name=cls.old_region, flags="f"
        )
        grass.try_remove(cls.asf_creds)
        grass.try_remove(cls.s2_creds)

    # pylint: disable=invalid-name
    def tearDown(self):
        """Remove the outputs created
        This is executed after each test run.
        """
        grass.run_command(
            "g.remove", type="raster", name=self.change_map, flags="f"
        )

    def test_sentinel1_change_success(self):
        """Test a successful change extraction"""
        s1_change = SimpleModule(
            "i.sentinel_1.change",
            date1_vv=f"{self.date1}_Gamma0_VV_log",
            date1_vh=f"{self.date1}_Gamma0_VH_log",
            date2_vv=f"{self.date2}_Gamma0_VV_log",
            date2_vh=f"{self.date2}_Gamma0_VH_log",
            min_size=0.5,
            change_threshold=0.5,
            output=self.change_map,
        )
        self.assertModule(s1_change)
        self.assertRasterExists(self.change_map)

        raster_cats = list(
            grass.parse_command(
                "r.category", map=self.change_map, separator=":"
            ).keys()
        )
        ref_cats = [
            "0:No signficant Change",
            "1:Signal Increase",
            "2:Signal Decrease",
        ]
        for ref_cat in ref_cats:
            self.assertIn(
                ref_cat,
                raster_cats,
                (f"Category {ref_cat} is not" " in output map"),
            )

    def test_sentinel1_change_nochange(self):
        """Test a successful change extraction without any changes
        (min_size very large)
        """
        s1_change = SimpleModule(
            "i.sentinel_1.change",
            date1_vv=f"{self.date1}_Gamma0_VV_log",
            date1_vh=f"{self.date1}_Gamma0_VH_log",
            date2_vv=f"{self.date2}_Gamma0_VV_log",
            date2_vh=f"{self.date2}_Gamma0_VH_log",
            min_size=1000,
            change_threshold=0.5,
            output=self.change_map,
        )
        self.assertModule(s1_change)
        self.assertRasterExists(self.change_map)
        stats = grass.parse_command("r.univar", map=self.change_map, flags="g")
        self.assertEqual(stats["max"], "0", "Output map should contain only 0")


if __name__ == "__main__":
    test()
