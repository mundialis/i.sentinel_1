## DESCRIPTION

*i.sentinel_1.forest.mask* creates a forest mask using a combination of
image segmentation and a rule-based classificaton. Therefore [Sentinel-1
monthly
mosaics](https://dataspace.copernicus.eu/news/2024-7-23-sentinel-1-monthly-mosaics-added-copernicus-data-space-ecosystem)
should be used as input SAR images, which can be downloaded in the
[Copernicus Browser](https://browser.dataspace.copernicus.eu). For
classifying segments as forest VH backscatter, the VV/VH ratio and the
Radar Vegetation Index is used. Due to local vegetation conditions and
the SAR acquisition time the resulting forest mask can be incomplete.
Check and may modify used thresholds!

## EXAMPLES

### Create Forest Mask

```sh
i.sentinel_1.forest.mask aoi=aoi_ireland sar_img_vv=vv_ireland sar_img_vh=vh_ireland forest_mask=forest_ireland
```

## AUTHORS

Johannes Halbauer, [mundialis GmbH & Co.
KG](https://www.mundialis.de/)  
