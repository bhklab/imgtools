from __future__ import annotations

from typing import Dict, Optional, TypeVar, Union

import numpy as np
import SimpleITK as sitk
from matplotlib import pyplot as plt
from pydicom import Dataset, dcmread

from imgtools.logging import logger

from .utils import read_image

T = TypeVar("T")


class Dose(sitk.Image):
    def __init__(
        self,
        img_dose: sitk.Image,
        df: Dataset,
        metadata: Optional[Dict[str, T]] = None,
    ) -> None:
        super().__init__(img_dose)
        self.img_dose = img_dose
        self.df = df
        if metadata:
            self.metadata = metadata
        else:
            self.metadata = {}

    @classmethod
    def from_dicom(cls, path: str) -> Dose:
        """
        Reads the data and returns the data frame and the image dosage in SITK format
        """
        dose = sitk.ReadImage(path) if ".dcm" in path else read_image(path)

        # if 4D, make 3D
        if dose.GetDimension() == 4:
            dose = dose[:, :, :, 0]

        # Get the metadata
        df = dcmread(path)

        # Convert to SUV
        factor = float(df.DoseGridScaling)
        img_dose = sitk.Cast(dose, sitk.sitkFloat32)
        img_dose = img_dose * factor

        metadata = {}

        return cls(img_dose, df, metadata)

    def resample_dose(self, ct_scan: sitk.Image) -> sitk.Image:
        """
        Resamples the RTDOSE information so that it can be overlayed with CT scan. The beginning and end slices of the
        resampled RTDOSE scan might be empty due to the interpolation
        """
        resampled_dose = sitk.Resample(
            self.img_dose, ct_scan
        )  # , interpolator=sitk.sitkNearestNeighbor)
        return resampled_dose

    def show_overlay(
        self, ct_scan: sitk.Image, slice_number: int
    ) -> plt.Figure:
        """
        For a given slice number, the function resamples RTDOSE scan and overlays on top of the CT scan and returns the figure of the
        overlay
        """
        resampled_dose = self.resample_dose(ct_scan)
        fig = plt.figure("Overlayed RTdose image", figsize=[15, 10])
        dose_arr = sitk.GetArrayFromImage(resampled_dose)
        plt.subplot(1, 3, 1)
        plt.imshow(dose_arr[slice_number, :, :])
        plt.subplot(1, 3, 2)
        ct_arr = sitk.GetArrayFromImage(ct_scan)
        plt.imshow(ct_arr[slice_number, :, :])
        plt.subplot(1, 3, 3)
        plt.imshow(ct_arr[slice_number, :, :], cmap=plt.cm.gray)
        plt.imshow(dose_arr[slice_number, :, :], cmap=plt.cm.hot, alpha=0.4)
        return fig

    def get_metadata(
        self,
    ) -> Dict[
        Union[str, int], Union[str, float, Dict[str, Union[str, float, list]]]
    ]:
        """
        Forms Dose-Value Histogram (DVH) from DICOM metadata
        {
            dvh_type
            dose_type
            dose_units
            vol_units
            ROI_ID: {
                vol: different volume values for different dosage bins
                dose_bins: different dose bins
                max_dose: max dose value
                mean_dose : mean dose value
                min_dose: min dose value
                total_vol: total volume of the ROI
            }
        }
        """
        try:
            num_roi = len(self.df.DVHSequence)
            self.dvh = {}
            # These properties are uniform across all the ROIs
            self.dvh["dvh_type"] = self.df.DVHSequence[0].DVHType
            self.dvh["dose_units"] = self.df.DVHSequence[0].DoseUnits
            self.dvh["dose_type"] = self.df.DVHSequence[0].DoseType
            self.dvh["vol_units"] = self.df.DVHSequence[0].DVHVolumeUnits
            # ROI specific properties
            for i in range(num_roi):
                raw_data = np.array(self.df.DVHSequence[i].DVHData)
                n = len(raw_data)

                # ROI ID
                roi_reference = (
                    self.df.DVHSequence[i]
                    .DVHReferencedROISequence[0]
                    .ReferencedROINumber
                )

                # Make dictionary for each ROI ID
                self.dvh[roi_reference] = {}

                # DVH specifc properties
                doses_bin = np.cumsum(raw_data[0:n:2])
                vol = raw_data[1:n:2]
                self.dvh[roi_reference]["dose_bins"] = doses_bin.tolist()
                self.dvh[roi_reference]["vol"] = vol.tolist()

                # ROI specific properties
                tot_vol = np.sum(vol)
                non_zero_index = np.where(vol != 0)[0]
                min_dose = doses_bin[non_zero_index[0]]
                max_dose = doses_bin[non_zero_index[-1]]
                mean_dose = np.sum(doses_bin * (vol / np.sum(vol)))
                self.dvh[roi_reference]["max_dose"] = max_dose
                self.dvh[roi_reference]["mean_dose"] = mean_dose
                self.dvh[roi_reference]["min_dose"] = min_dose
                self.dvh[roi_reference]["total_vol"] = tot_vol
        except AttributeError:
            logger.warning(
                "No DVH information present in the DICOM. Returning empty dictionary"
            )
            self.dvh = {}

        return self.dvh
