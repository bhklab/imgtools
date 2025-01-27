from __future__ import annotations

import contextlib
import datetime
import os
import pathlib
from enum import Enum
from typing import TYPE_CHECKING, Dict, Optional, Union

import numpy as np
import SimpleITK as sitk
from matplotlib import pyplot as plt
from pydicom import dcmread

from imgtools.logging import logger

from .utils import read_image

if TYPE_CHECKING:
    from pydicom.dataset import FileDataset


# alternative to StrEnum for python 3.10 compatibility
class PETImageType(str, Enum):
    """
    Enumeration for PET image types used in DICOM processing.

    This enumeration defines the two primary types of PET image representations:
    - `SUV` (Standardized Uptake Value): Represents pixel values as SUV,
      calculated using the formula:
      `SUV = Activity Concentration / (Injected Dose Quantity / Body Weight)`.
    - `ACT` (Activity Concentration): Represents pixel values as raw
      activity concentrations.

    Attributes
    ----------
    SUV : str
        Indicates the SUV image type.
    ACT : str
        Indicates the activity concentration image type.

    Examples
    --------
    >>> image_type = PETImageType.SUV  # SUV image type
    >>> print(image_type)
    'SUV'
    >>> isinstance(image_type, str)
    True
    >>> repr(PetImageType("SUV"))
    <PETImageType.SUV: 'SUV'>
    """

    SUV = "SUV"
    ACT = "ACT"


class PET(sitk.Image):
    def __init__(
        self,
        img_pet: sitk.Image,
        df: FileDataset,
        factor: float,
        values_assumed: bool,
        metadata: Optional[Dict[str, Union[str, float, bool]]] = None,
        image_type: PETImageType = PETImageType.SUV,
    ) -> None:
        super().__init__(img_pet)
        self.img_pet: sitk.Image = img_pet
        self.df: FileDataset = df
        self.factor: float = factor
        self.values_assumed: bool = values_assumed
        self.metadata: Dict[str, Union[str, float, bool]] = (
            metadata if metadata else {}
        )
        self.image_type = PETImageType(image_type)

    @classmethod
    def from_dicom(
        cls,
        path: str,
        series_id: Optional[str] = None,
        pet_image_type: PETImageType = PETImageType.SUV,
    ) -> PET:
        """Read the PET scan and returns the data frame and the image dosage in SITK format

        There are two types of existing formats which has to be mentioned in the type
        type:
            SUV: gets the image with each pixel value having SUV value
            ACT: gets the image with each pixel value having activity concentration
        SUV = Activity concenteration/(Injected dose quantity/Body weight)

        Please refer to the pseudocode: https://qibawiki.rsna.org/index.php/Standardized_Uptake_Value_(SUV)
        If there is no data on SUV/ACT then backup calculation is done based on the formula in the documentation, although, it may
        have some error.
        """
        pet: sitk.Image = read_image(path, series_id)
        img_pet: sitk.Image = sitk.Cast(pet, sitk.sitkFloat32)
        path_one: str = pathlib.Path(path, os.listdir(path)[0]).as_posix()
        df: FileDataset = dcmread(path_one)
        values_assumed: bool = False
        pet_type: PETImageType = PETImageType(pet_image_type)
        try:
            if pet_type == PETImageType.SUV:
                factor: float = df.to_json_dict()["70531000"]["Value"][0]
            else:
                factor = df.to_json_dict()["70531009"]["Value"][0]
        except KeyError:
            logger.warning(
                "Scale factor not available in DICOMs. Calculating based on metadata, may contain errors"
            )
            factor = cls.calc_factor(df, pet_type)
            values_assumed = True

        # SimpleITK reads some pixel values as negative but with correct value
        img_pet = sitk.Abs(img_pet * factor)

        metadata: Dict[str, Union[str, float, bool]] = {}
        return cls(
            img_pet=img_pet,
            df=df,
            factor=factor,
            values_assumed=values_assumed,
            metadata=metadata,
            image_type=pet_type,
        )

    def get_metadata(self) -> Dict[str, Union[str, float, bool]]:
        # Developer note: This method does similar work to the below `calc_factor` method.
        # we can extract the common code to a separate method and call it in both places.
        self.metadata = {}
        with contextlib.suppress(Exception):
            self.metadata["weight"] = float(self.df.PatientWeight)
        try:
            self.metadata["scan_time"] = datetime.datetime.strptime(
                self.df.AcquisitionTime, "%H%M%S.%f"
            )
            self.metadata["injection_time"] = datetime.datetime.strptime(
                self.df.RadiopharmaceuticalInformationSequence[
                    0
                ].RadiopharmaceuticalStartTime,
                "%H%M%S.%f",
            )
            self.metadata["half_life"] = float(
                self.df.RadiopharmaceuticalInformationSequence[
                    0
                ].RadionuclideHalfLife
            )
            self.metadata["injected_dose"] = float(
                self.df.RadiopharmaceuticalInformationSequence[
                    0
                ].RadionuclideTotalDose
            )
        except KeyError:
            pass
        self.metadata["factor"] = self.factor
        self.metadata["Values_Assumed"] = self.calc
        return self.metadata

    def resample_pet(self, ct_scan: sitk.Image) -> sitk.Image:
        resampled_pt: sitk.Image = sitk.Resample(self.img_pet, ct_scan)
        return resampled_pt

    def show_overlay(
        self, ct_scan: sitk.Image, slice_number: int
    ) -> plt.figure:
        resampled_pt: sitk.Image = self.resample_pet(ct_scan)
        fig: plt.figure = plt.figure("Overlayed image", figsize=[15, 10])
        pt_arr: np.ndarray = sitk.GetArrayFromImage(resampled_pt)
        plt.subplot(1, 3, 1)
        plt.imshow(pt_arr[slice_number, :, :])
        plt.subplot(1, 3, 2)
        ct_arr: np.ndarray = sitk.GetArrayFromImage(ct_scan)
        plt.imshow(ct_arr[slice_number, :, :])
        plt.subplot(1, 3, 3)
        plt.imshow(ct_arr[slice_number, :, :], cmap=plt.cm.gray)
        plt.imshow(pt_arr[slice_number, :, :], cmap=plt.cm.hot, alpha=0.4)
        return fig

    @staticmethod
    def calc_factor(df: FileDataset, pet_image_type: str) -> float:
        try:
            weight: float = float(df.PatientWeight) * 1_000
        except KeyError:
            logger.warning("Patient Weight Not Present. Taking 75Kg")
            weight = 75_000
        try:
            scan_time: datetime.datetime = datetime.datetime.strptime(
                df.AcquisitionTime, "%H%M%S.%f"
            )
            injection_time: datetime.datetime = datetime.datetime.strptime(
                df.RadiopharmaceuticalInformationSequence[
                    0
                ].RadiopharmaceuticalStartTime,
                "%H%M%S.%f",
            )
            half_life: float = float(
                df.RadiopharmaceuticalInformationSequence[
                    0
                ].RadionuclideHalfLife
            )
            injected_dose: float = float(
                df.RadiopharmaceuticalInformationSequence[
                    0
                ].RadionuclideTotalDose
            )

            a: float = np.exp(
                -np.log(2) * ((scan_time - injection_time).seconds / half_life)
            )

            injected_dose_decay: float = a * injected_dose
        except Exception:
            logger.warning("Not enough data available, taking average values")
            a = np.exp(-np.log(2) * (1.75 * 3600) / 6588)
            injected_dose_decay = 420000000 * a

        suv: float = weight / injected_dose_decay
        if pet_image_type == "SUV":
            return suv
        else:
            return 1 / a
