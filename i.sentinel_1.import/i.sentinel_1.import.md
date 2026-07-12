## DESCRIPTION

*i.sentinel_1.import* is a GRASS GIS addon Python script based on snappy
(Python API of the Sentinel Tool Box SNAP from ESA). It is used to
preprocess a Sentinel-1 IW mode, GRD scene using the software ([ESA
SNAP](http://step.esa.int/main/toolboxes/snap/)). After preprocessing,
the scene is imported into GRASS.

## NOTES

*i.sentinel_1.import* is a preprocessing chain function for Sentinel-1
IW mode, GRD scenes. It runs the SNAP functions Border Noise Removal,
Orbit File Application, Thermal Noise Removal, Calibration, Terrain
Flattening (if Gamma0 is selected as output), Speckle Filtering
(indicated by the **-s** flag), and Terrain Correction. Data are
imported to GRASS using [r.import](r.import.md). For Terrain Flattening
and Terrain Correction, an external DEM can be provided instead of the
default auto-download of SRTM 1-sec HGT data by using the external_dem
parameter. The output raster map will be named after the input scene
plus a suffix for backscattering coefficient, polarization, and scaling
to dB, for example:
*S1A_IW_GRDH_1SDV_20220106T054218_20220106T054243_041336_04E9FD_F9DE_Sigma0_VH_log*

## EXAMPLE

Sentinel-1 processing example:

```sh
i.sentinel_1.import -s input=${DATAPATH} outpath=${OUTPATH} bandname=Sigma0_VV
```

## REQUIREMENTS

ESA's [SNAP](https://step.esa.int/main/download/snap-download/) needs to
be installed and the SNAP-Python (snappy) interface needs to be
configured
([instruction](https://senbox.atlassian.net/wiki/spaces/SNAP/pages/50855941/Configure+Python+to+use+the+SNAP-Python+snappy+interface))

## SEE ALSO

*[r.import](https://grass.osgeo.org/grass-stable/manuals/r.import.html)*

## AUTHORS

Hajar Benelcadi and Guido Riembauer,
[mundialis](https://www.mundialis.de/), Germany
