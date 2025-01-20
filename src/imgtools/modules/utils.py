from typing import Optional

import SimpleITK as sitk


def read_image(path: str, series_id: Optional[str] = None) -> sitk.Image:
    reader = sitk.ImageSeriesReader()
    dicom_names = reader.GetGDCMSeriesFileNames(
        path, seriesID=series_id if series_id else ""
    )
    reader.SetFileNames(dicom_names)
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()

    return reader.Execute()
