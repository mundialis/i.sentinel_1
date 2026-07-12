## DESCRIPTION

*i.sentinel_1.change* is a GRASS GIS addon that extracts areas of
changed backscatter values from two Sentinel-1 input scenes. The input
backscatter values are expected in dB scale. The addon calculates two
polarisation ratios (date2_vv/date1_vv and date2_vh/date1_vh), smoothes
them with a median filter in
[r.neighbors](https://grass.osgeo.org/grass-stable/manuals/r.neighbors.html)
and applies the user-defined thresholds 1+**change_threshold** and
1-**change_threshold** to identify areas of change. For example, a
**change_threshold** of 0.5 would mean that areas with a ratio \<= 0.5
are identified as signal decrease, and areas with a ratio of \>= 1.5 are
identified as signal increase.

## EXAMPLE

```sh
i.sentinel_1.change date1_vv=Date1_Sigma0_VV_log date1_vh=Date1_Sigma0_VH_log date2_vv=Date2_Sigma0_VV_log date2_vh=Date2_Sigma0_VH_log output=changed_areas change_threshold=0.75 min_size=1.0 --o
```

## SEE ALSO

*[r.mapcalc](https://grass.osgeo.org/grass-stable/manuals/r.mapcalc.html),
[r.neighbors](https://grass.osgeo.org/grass-stable/manuals/r.neighbors.html),
[r.null](https://grass.osgeo.org/grass-stable/manuals/r.null.html),
[r.colors](https://grass.osgeo.org/grass-stable/manuals/r.colors.html),
[r.category](https://grass.osgeo.org/grass-stable/manuals/r.category.html)*

## AUTHOR

Guido Riembauer, [mundialis](https://www.mundialis.de/), Germany
