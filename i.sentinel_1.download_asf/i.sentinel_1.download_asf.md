## DESCRIPTION

*i.sentinel_1.download_asf* searches and downloads SAR data from the
Alaska Satellite Facility (ASF) using the
[ASF-API](https://asf.alaska.edu/api/). The current GRASS GIS region is
used to define the search area. Currently, *i.sentinel_1.download_asf*
only allows the search and download of Sentinel-1 data. The benefit of
this addon compared to [i.sentinel.download](i.sentinel.download.md) is
that the latter uses the Copernicus Open Access Hub, where Sentinel-1
data is consecutively moved into a long-term archive. Users need to
trigger the re-upload of the data which can take up to 24 hours. ASF's
Distributed Active Archive Center does not have these restrictions.

## REQUIREMENTS

- The download utility [aria2](https://aria2.github.io/) has to be
  installed on the system.

- Login-credentials for [NASA
  Earthdata](https://urs.earthdata.nasa.gov/) have to be saved in a file
  in the format

  ```sh
        http-user=username
        http-passwd=password
      
  ```

- Define a (thematic) study area in your [NASA
  Earthdata](https://urs.earthdata.nasa.gov/) profile settings.

- Add *Alaska Satellite Facility Data Access* to your list of authorized
  applications in your [NASA Earthdata](https://urs.earthdata.nasa.gov/)
  profile settings.

## EXAMPLE

```sh
# List all Sentinel-1 SLC data from June 2016 that intersect with the current region
i.sentinel_1.download_asf -l credentials=credentials start=2016-06-01 end=2016-06-30 processinglevel=SLC

# Download the first 5 Sentinel-1 GRD datasets from an ASCENDING orbit from June 2016
# that intersects with the current region
i.sentinel_1.download_asf output=output_folder credentials=credentials start=2016-06-01 end=2016-06-30 processinglevel=GRD flight_dir=ASCENDING limit=5

# Download a specific Sentinel-1 granule regardless of computational region
i.sentinel_1.download_asf output=output_folder credentials=credentials granules=S1A_IW_GRDH_1SDV_20201010T135633_20201010T135658_034735_040BF5_B2E9
```

## SEE ALSO

*[i.sentinel.download](i.sentinel.download.md) (addon)*

## AUTHOR

Guido Riembauer, [mundialis](https://www.mundialis.de/), Germany
