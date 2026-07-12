[![image-alt](grass_logo.png)](https://grass.osgeo.org/grass-stable/manuals/index.html)

------------------------------------------------------------------------

## NAME

***i.sentinel_1*** is a GRASS GIS addon toolset that searches,
downloads, imports and preprocesses SAR data from the [Alaska Satellite
Facility](https://asf.alaska.edu/) using ESA's
[SNAP](https://step.esa.int/main/download/snap-download/) software. If a
region is covered by multiple Sentinel-1 GRD tiles, a mosaic can be
created. Additionally, a forest extraction tool is included.

## KEYWORDS

[imagery](https://grass.osgeo.org/grass-stable/manuals/raster.html),
[import](https://grass.osgeo.org/grass-stable/manuals/topic_import.html),
[satellite](keywords.md#satellite), [Sentinel](keywords.md#Sentinel)

## DESCRIPTION

The *i.sentinel_1* toolset consists of currently five modules:

[i.sentinel_1.download_asf](i.sentinel_1.download_asf.md)  
searches and downloads SAR data from the [Alaska Satellite
Facility](https://asf.alaska.edu/)

[i.sentinel_1.import](i.sentinel_1.import)  
preprocesses and imports Sentinel-1 GRD SAR data using ESA's
[SNAP](https://step.esa.int/main/download/snap-download/) software

[i.sentinel_1.mosaic](i.sentinel_1.mosaic.md)  
downloads and imports an entire Sentinel-1 GRD SAR coverage for the
current region using
[i.sentinel_1.download_asf](i.sentinel_1.download_asf.html.md) and
[i.sentinel_1.import](i.sentinel_1.import)

[i.sentinel_1.change](i.sentinel_1.change.md)  
extracts areas of change from two Sentinel-1 GRD SAR data time-steps
using a user-defined change threshold of backscatter ratio

[i.sentinel_1.forest.mask](i.sentinel_1.forest.mask.md)  
extracts forest areas based on Sentinel-1 gamma0 VV and VH data using a
rule-based image segmentation approach

## REQUIREMENTS

Downloading ([i.sentinel_1.download_asf](i.sentinel_1.download_asf.md)):

- [aria2](https://aria2.github.io/)
- [NASA Earthdata](https://urs.earthdata.nasa.gov/) credentials

Preprocessing & importing
([i.sentinel_1.import](i.sentinel_1.import.md)):

- ESA's [SNAP](https://step.esa.int/main/download/snap-download/)
- SNAP-Python (snappy) interface needs to be configured
  ([instruction](https://senbox.atlassian.net/wiki/spaces/SNAP/pages/50855941/Configure+Python+to+use+the+SNAP-Python+snappy+interface))

Mosaicking ([i.sentinel_1.mosaic](i.sentinel_1.mosaic.md)):

- All of the above
- [i.sentinel.download](i.sentinel.download.md)
- [i.sentinel.import](i.sentinel.import.md)

Forest Extraction
([i.sentinel_1.forest.mask](i.sentinel_1.forest.mask.md)):

- [grass-gis-helpers](https://github.com/mundialis/grass-gis-helpers/)

## AUTHORS

Guido Riembauer, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Hajar Benelcadi, [mundialis GmbH & Co. KG](https://www.mundialis.de/)  
Johannes Halbauer, [mundialis GmbH & Co.
KG](https://www.mundialis.de/)  
