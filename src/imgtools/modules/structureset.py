"""Module for handling and converting DICOM RTSTRUCT contour data to segmentations.

This module provides classes and methods for processing DICOM RTSTRUCT files,
which store contour data for regions of interest (ROIs). The main class,
`StructureSet`, facilitates the extraction, manipulation, and conversion of
contour data into 3D masks or segmentations compatible with other imaging
pipelines.

Classes
-------
StructureSet
    Represents a DICOM RTSTRUCT file, allowing operations such as loading
        ROI contours, converting physical points to masks, and exporting to
        segmentation objects.

Functions
---------
rtstruct_reference_seriesuid(rtstruct: FileDataset) -> str
    Given an RTSTRUCT file, return the Referenced SeriesInstanceUID.

Notes
-----
The `StructureSet` class provides utility methods for handling complex ROI
labeling schemes, such as those based on regular expressions, and supports
multiple output formats for segmentation masks. It also integrates robust
error handling and logging to handle malformed or incomplete DICOM files.
"""

from __future__ import annotations

import re
from io import BytesIO
from itertools import groupby
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, TypedDict, Union

import numpy as np
import SimpleITK as sitk
from pydicom import dcmread
from skimage.draw import polygon2mask

from imgtools.logging import logger
from imgtools.modules.segmentation import Segmentation
from imgtools.utils import physical_points_to_idxs

if TYPE_CHECKING:
    from pydicom.dataset import FileDataset


def roi_names_from_dicom(
    rtstruct_or_path: Union[str, Path, FileDataset],
) -> list[str]:
    """Extract ROI names from DICOM file or loaded RTSTRUCT."""
    try:
        if isinstance(rtstruct_or_path, (str, Path)):
            rtstruct = dcmread(
                rtstruct_or_path,
                force=True,
                stop_before_pixels=True,
                specific_tags=["StructureSetROISequence"],
            )
        else:
            rtstruct = rtstruct_or_path
        return [roi.ROIName for roi in rtstruct.StructureSetROISequence]
    except (AttributeError, IndexError) as e:
        msg = "Error extracting ROI names from DICOM file."
        raise ValueError(msg) from e


def rtstruct_reference_seriesuid(
    rtstruct_or_path: Union[str, Path, FileDataset],
) -> str:
    """Given an RTSTRUCT file or loaded RTSTRUCT, return the Referenced SeriesInstanceUID."""
    try:
        if isinstance(rtstruct_or_path, (str, Path)):
            rtstruct = dcmread(
                rtstruct_or_path,
                force=True,
                stop_before_pixels=True,
                specific_tags=["ReferencedFrameOfReferenceSequence"],
            )
        else:
            rtstruct = rtstruct_or_path

        return str(
            rtstruct.ReferencedFrameOfReferenceSequence[0]
            .RTReferencedStudySequence[0]
            .RTReferencedSeriesSequence[0]
            .SeriesInstanceUID
        )
    except (AttributeError, IndexError) as e:
        raise ValueError(
            "Referenced SeriesInstanceUID not found in RTSTRUCT"
        ) from e


class RTSTRUCTMetadata(TypedDict):
    PatientID: str
    StudyInstanceUID: str
    SeriesInstanceUID: str
    Modality: str
    ReferencedSeriesInstanceUID: str
    OriginalNumberOfROIs: int


def extract_metadata(rtstruct: FileDataset) -> RTSTRUCTMetadata:
    """Extract metadata from the RTSTRUCT file."""
    return {
        "PatientID": rtstruct.PatientID,
        "StudyInstanceUID": rtstruct.StudyInstanceUID,
        "SeriesInstanceUID": rtstruct.SeriesInstanceUID,
        "Modality": rtstruct.Modality,
        "ReferencedSeriesInstanceUID": rtstruct_reference_seriesuid(rtstruct),
        "OriginalNumberOfROIs": len(rtstruct.StructureSetROISequence),
    }


class StructureSet:
    """Class for handling DICOM RTSTRUCT contour data.

    Provides methods for loading, processing, and converting contour data
    into segmentation masks or other formats for further analysis.

    Attributes
    ----------

    roi_points : Dict[str, List[np.ndarray]]
        A dictionary mapping ROI (Region of Interest) names to a list of 2D arrays.
        Each array contains the 3D physical coordinates of the contour points for a slice.
    metadata : RTSTRUCTMetadata
        A dictionary containing additional metadata from the DICOM RTSTRUCT file.

    Properties
    ----------
    roi_names : List[str]
        List of all ROI (Region of Interest) names.

    Methods
    -------
    has_roi(pattern: str, ignore_case: bool = False) -> bool
        Search for an ROI name based on a regular expression pattern.

    from_dicom_rtstruct(rtstruct_path: str | Path | bytes, suppress_warnings: bool = False) -> StructureSet
        Create a StructureSet instance from a DICOM RTSTRUCT file.

    from_dicom(rtstruct_path: str | Path | bytes, suppress_warnings: bool = False) -> StructureSet
        Create a StructureSet instance from a DICOM RTSTRUCT file.

    to_segmentation(
        reference_image: sitk.Image,
        roi_names: Dict[str, str] = None,
        continuous: bool = True,
        existing_roi_indices: Dict[str, int] = None,
        ignore_missing_regex: bool = False,
        roi_select_first: bool = False,
        roi_separate: bool = False,
    ) -> Segmentation
        Convert the structure set to a imgtools.Segmentation object.

    Examples
    --------
    >>> roi_points = {
    ...     "GTV": [np.array([[0, 0, 0], [1, 1, 1]])]
    ... }
    >>> metadata = {"PatientName": "John Doe"}
    >>> structure_set = StructureSet(
    ...     roi_points, metadata
    ... )
    """

    roi_points: Dict[str, List[np.ndarray]]
    metadata: RTSTRUCTMetadata

    def __init__(
        self,
        roi_points: Dict[str, List[np.ndarray]],
        metadata: Optional[RTSTRUCTMetadata] = None,
    ) -> None:
        self.roi_points: Dict[str, List[np.ndarray]] = roi_points
        self.metadata: RTSTRUCTMetadata = metadata or {}

    @classmethod
    def from_dicom(
        cls,
        rtstruct_path: str | Path | bytes,
        suppress_warnings: bool = False,
        roi_name_pattern: str | None = None,
    ) -> StructureSet:
        """Create a StructureSet instance from a DICOM RTSTRUCT file.

        Alias for the 'from_dicom_rtstruct' method (>=v1.16.0).

        Parameters
        ----------
        rtstruct_path : str, Path, or bytes
            Path to the DICOM RTSTRUCT file, or the file data itself.
        suppress_warnings : bool, optional
            If True, suppresses warnings for missing or invalid ROI data. Default is False.
        roi_name_pattern : str, optional
            A regex pattern to filter ROI names. Only ROIs matching the pattern will be included.
            This will help to save time when loading, and prevent error messages for ROIs we
            dont care about anyways.

        Returns
        -------
        StructureSet
            An instance of the StructureSet class containing the ROI data and metadata.

        Examples
        --------
        >>> structure_set = StructureSet.from_dicom(
        ...     "path/to/rtstruct.dcm",
        ...     roi_name_pattern="^GTV|PTV",
        ... )
        """

        return cls.from_dicom_rtstruct(
            rtstruct_path, suppress_warnings, roi_name_pattern
        )

    @classmethod
    def from_dicom_rtstruct(
        cls,
        rtstruct_path: str | Path | bytes,
        suppress_warnings: bool = False,
        roi_name_pattern: str | None = None,
    ) -> StructureSet:
        """Create a StructureSet instance from a DICOM RTSTRUCT file."""

        dcm = cls._load_rtstruct_data(rtstruct_path)

        # Extract ROI names and points
        roi_names = roi_names_from_dicom(dcm)

        # Initialize dictionary to store ROI points
        roi_points: Dict[str, List[np.ndarray]] = {}

        for i, name in enumerate(roi_names):
            if roi_name_pattern and not re.match(roi_name_pattern, name):
                continue
            try:
                roi_points[name] = cls._get_roi_points(dcm, i)
            except AttributeError as ae:
                if not suppress_warnings:
                    logger.warning(
                        f"Could not get points for ROI `{name}`.",
                        rtstruct_series=dcm.SeriesInstanceUID,
                        error=ae,
                    )

        # sort the dictionary by the keys
        roi_points = dict(sorted(roi_points.items()))

        # Initialize metadata (can be extended later to extract more useful fields)
        metadata = extract_metadata(dcm)

        # Some of the ROIs wont have been extracted.
        # We can add a metadata field to indicate the number of ROIs that were extracted
        metadata["ExtractedNumberOfROIs"] = len(roi_points)

        # Return the StructureSet instance
        return cls(roi_points, metadata)

    @property
    def roi_names(self) -> List[str]:
        """List of all ROI (Region of Interest) names."""
        return list(self.roi_points.keys())

    def has_roi(self, pattern: str, ignore_case: bool = False) -> bool:
        """Search for an ROI name in self.roi_names based on a regular expression pattern.

        Parameters
        ----------
        pattern : str
            The regular expression pattern to search for.
        flags : int, optional
            Flags to modify the regular expression matching behavior. Default is re.IGNORECASE.

        Returns
        -------
        bool
            True if the pattern matches any ROI name, False otherwise.

        Examples
        --------
        Assume the following rt has the roi names: ['GTV1', 'GTV2', 'PTV', 'CTV_0', 'CTV_1']
        >>> structure_set = StructureSet.from_dicom(
        ...     "path/to/rtstruct.dcm"
        ... )
        >>> structure_set.has_roi("GTV.*")
        True
        >>> structure_set.has_roi("ctv.*")
        True
        """
        _flags = re.IGNORECASE if ignore_case else 0
        return any(
            re.fullmatch(pattern, name, flags=_flags)
            for name in self.roi_names
        )

    @staticmethod
    def _extract_metadata(
        rtstruct: FileDataset,
    ) -> Dict[str, Union[str, int, float]]:
        """Extract metadata from the RTSTRUCT file."""
        return {
            "PatientID": rtstruct.PatientID,
            "StudyInstanceUID": rtstruct.StudyInstanceUID,
            "SeriesInstanceUID": rtstruct.SeriesInstanceUID,
            "Modality": rtstruct.Modality,
            "ReferencedSeriesInstanceUID": rtstruct_reference_seriesuid(
                rtstruct
            ),
            "OriginalNumberOfROIs": len(rtstruct.StructureSetROISequence),
        }

    @staticmethod
    def _get_roi_points(
        rtstruct: FileDataset, roi_index: int
    ) -> List[np.ndarray]:
        """Extract and reshapes contour points for a specific ROI in an RTSTRUCT file.

        Parameters
        ----------
        rtstruct : FileDataset
            The loaded DICOM RTSTRUCT file.
        roi_index : int
            The index of the ROI in the ROIContourSequence.

        Returns
        -------
        List[np.ndarray]
            A list of numpy arrays where each array contains the 3D physical coordinates
            of the contour points for a specific slice.

        Raises
        ------
        AttributeError
            If the ROIContourSequence, ContourSequence, or ContourData is missing or malformed.

        Examples
        --------
        >>> rtstruct = dcmread(
        ...     "path/to/rtstruct.dcm", force=True
        ... )
        >>> StructureSet._get_roi_points(rtstruct, 0)

        Notes
        -----
        The structure of the contour data in the DICOM RTSTRUCT file is as follows:
        > ROIContourSequence (3006, 0039)
        >> ReferencedROINumber (3006, 0084)
        >> ContourSequence (3006, 0040)
        >>> ContourData (3006, 0050)
        >>> ContourGeometricType (3006, 0042)
        >>> NumberOfContourPoints (3006, 0046)
        """
        # Check for ROIContourSequence
        if not hasattr(rtstruct, "ROIContourSequence"):
            raise AttributeError(
                "The DICOM RTSTRUCT file is missing 'ROIContourSequence'."
            )

        # Check if ROI index exists in the sequence
        if roi_index >= len(rtstruct.ROIContourSequence) or roi_index < 0:
            msg = (
                f"ROI index {roi_index} is out of bounds for the "
                f" 'ROIContourSequence' with length {len(rtstruct.ROIContourSequence)}."
            )
            raise AttributeError(msg)

        roi_contour = rtstruct.ROIContourSequence[roi_index]

        # Check for ContourSequence in the specified ROI
        if not hasattr(roi_contour, "ContourSequence"):
            msg = f"ROI at index {roi_index} is missing 'ContourSequence'."
            raise AttributeError(msg)

        contour_sequence = roi_contour.ContourSequence

        # Check for ContourData in each contour
        contour_points = []
        for i, slc in enumerate(contour_sequence):
            if not hasattr(slc, "ContourData"):
                msg = f"Contour {i} in ROI at index {roi_index} is missing 'ContourData'."
                raise AttributeError(msg)
            contour_points.append(np.array(slc.ContourData).reshape(-1, 3))

        return contour_points

    def _assign_labels(  # noqa
        self,
        names: List[Union[str, List[str]]],
        roi_select_first: bool = False,
        roi_separate: bool = False,
    ) -> Dict[str, int]:
        """Assigns integer labels to ROIs (Regions of Interest) based on their names or regex patterns.

        This method supports flexible and configurable labeling of ROIs using exact matches or regular
        expressions. It also allows for advanced configurations such as selecting only the first match
        or treating each match as a separate mask.

        Parameters
        ----------
        names : List[Union[str, List[str]]]
            A list of ROI names or regex patterns. Can be:
                - A list of strings representing exact matches or regex patterns.
                - A nested list of regex patterns, where all matching ROIs within the same sublist
                are assigned the same label.
        roi_select_first : bool, optional
            If True, selects only the first matching ROI for each regex pattern or name.
            Default is False.
        roi_separate : bool, optional
            If True, assigns separate labels to each matching ROI within a regex pattern, appending
            a numerical suffix to the ROI name (e.g., "CTV_0", "CTV_1"). Default is False.

        Returns
        -------
        Dict[str, int]
            A dictionary mapping ROI names to their assigned integer labels.

        Raises
        ------
        ValueError
            If `names` is empty or does not match any ROIs.

        Examples
        --------
        Lets say we have the following ROI names:
        >>> self.roi_names = ["GTV", "PTV", "CTV_0", "CTV_1"]

        Case 1: Default behavior
        All matching ROIs for each pattern are assigned the same label(number).
        note how the CTV ROIs are assigned the same label: 1
        >>> self._assign_labels(["GTV", "CTV.*"])
        {'GTV': 0, 'CTV_0': 1, 'CTV_1': 1}

        Case 2: Select only the first match for each pattern
        Subsequent matches are ignored.
        >>> self._assign_labels(
        ...     ["GTV", "CTV.*"], roi_select_first=True
        ... )
        {'GTV': 0, 'CTV_0': 1}

        Case 3: Separate labels for each match
        Even if a pattern matches multiple ROIs, each ROI gets a separate label.
        note how now the CTV ROIs are assigned different labels: 1 and 2
        >>> self._assign_labels(
        ...     ["GTV", "CTV.*"], roi_separate=True
        ... )
        {'GTV': 0, 'CTV_0': 1, 'CTV_1': 2}

        # Case 4: Grouped patterns
        >>> self._assign_labels([["GTV", "PTV"], "CTV.*"])
        {'GTV': 0, 'PTV': 0, 'CTV_0': 1, 'CTV_1': 1}
        """
        if not names:
            raise ValueError("The 'names' list cannot be empty.")
        if roi_select_first and roi_separate:
            raise ValueError(
                "The options 'roi_select_first' and 'roi_separate' cannot both be True. "
                "'roi_select_first' stops after the first match,"
                " while 'roi_separate' processes all matches individually."
            )

        labels: Dict[str, int] = {}
        cur_label = 0

        # Case 1: If `names` is exactly `self.roi_names`, assign sequential labels directly.
        if names == self.roi_names:
            return {name: i for i, name in enumerate(self.roi_names)}

        # Case 2: Iterate over `names` (could contain regex patterns or sublists)
        for pattern in names:
            # TODO: refactor this to use a generator function for better readability
            # and to avoid code duplication

            # Single pattern: string or regex
            if isinstance(pattern, str):
                matched = False
                for _, roi_name in enumerate(self.roi_names):
                    if re.fullmatch(pattern, roi_name, flags=re.IGNORECASE):
                        matched = True
                        # Group all matches under the same label
                        labels[roi_name] = cur_label
                        if roi_select_first:
                            break
                # Increment label counter only if at least one match occurred
                if matched:
                    cur_label += 1

            # Nested patterns: list of strings or regexes
            elif isinstance(pattern, list):
                matched = False
                for subpattern in pattern:
                    if roi_select_first and matched:
                        break
                    for i, roi_name in enumerate(self.roi_names):
                        if re.fullmatch(
                            subpattern, roi_name, flags=re.IGNORECASE
                        ):
                            matched = True
                            if roi_separate:
                                labels[f"{roi_name}_{i}"] = cur_label
                            else:
                                labels[roi_name] = cur_label
                cur_label += 1
            else:
                msg = f"Invalid pattern type: {type(pattern)}, expected str or list."
                raise ValueError(msg)

        # Validate output
        if not labels:
            msg = f"No matching ROIs found for the provided patterns: {names}"
            raise ValueError(msg)

        return labels

    def get_mask(
        self,
        reference_image: sitk.Image,
        mask: np.ndarray,
        label: str,
        idx: int,
        continuous: bool,
    ) -> None:
        size = reference_image.GetSize()[::-1]
        physical_points = self.roi_points.get(label, np.array([]))
        mask_points = physical_points_to_idxs(
            reference_image, physical_points, continuous=continuous
        )
        for contour in mask_points:
            try:
                z, slice_points = np.unique(contour[:, 0]), contour[:, 1:]
                if (
                    len(z) == 1
                ):  # assert len(z) == 1, f"This contour ({name}) spreads across more than 1 slice."
                    slice_mask = polygon2mask(size[1:], slice_points)
                    mask[z[0], :, :, idx] += slice_mask
            except (
                Exception
            ) as e:  # rounding errors for points on the boundary
                if z == mask.shape[0]:
                    z -= 1
                elif z == -1:  # ?
                    z += 1
                elif z > mask.shape[0] or z < -1:
                    msg = f"{z} index is out of bounds for image sized {mask.shape}."
                    raise IndexError(msg) from e

                # if the contour spans only 1 z-slice
                if len(z) == 1:
                    z_idx = int(np.floor(z[0]))
                    slice_mask = polygon2mask(size[1:], slice_points)
                    mask[z_idx, :, :, idx] += slice_mask
                else:
                    raise ValueError(
                        "This contour is corrupted and spans across 2 or more slices."
                    ) from e

    def to_segmentation(  # noqa
        self,
        reference_image: sitk.Image,
        roi_names: str
        | List[str]
        | Dict[str, Union[str, List[str]]]
        | None = None,
        continuous: bool = True,
        existing_roi_indices: Dict[str, int] | None = None,
        ignore_missing_regex: bool = False,
        roi_select_first: bool = False,
        roi_separate: bool = False,
    ) -> Segmentation | None:
        """Convert the structure set to a Segmentation object.

        Parameters
        ----------
        roi_names : Union[str, List[str], Dict[str, Union[str, List[str]]], None]
            ROI names or patterns to convert to segmentation:
            - `None` (default): All ROIs will be loaded
            - `str`: A single pattern (regex) to match ROI names.
            - `List[str]`: A list of patterns where each matches ROI names.
            - `Dict[str, str | List[str]]`: A dictionary where each key maps to a
            pattern (or list of patterns). The matched names are grouped under
            the same label.
            Both full names and case-insensitive regular expressions are allowed.
        continuous : bool, default=True
            Flag passed to 'physical_points_to_idxs' in 'StructureSet.to_segmentation'.
            Resolves errors caused by ContinuousIndex > Index.
        roi_select_first : bool, optional
            If True, selects only the first matching ROI for each regex pattern or name.
            Default is False.
        roi_separate : bool, optional
            If True, assigns separate labels to each matching ROI within a regex pattern, appending
            a numerical suffix to the ROI name (e.g., "CTV_0", "CTV_1"). Default is False.

        Returns
        -------
        Segmentation | None
            The segmentation object containing the masks for the selected ROIs.
            If no ROIs match the provided patterns, returns None if `ignore_missing_regex` is True.

        Notes
        -----
        If `roi_names` contains lists of strings, each matching
        name within a sublist will be assigned the same label. This means
        that `roi_names=['pat']` and `roi_names=[['pat']]` can lead
        to different label assignments, depending on how many ROI names
        match the pattern. E.g. if `self.roi_names = ['fooa', 'foob']`,
        passing `roi_names=['foo(a|b)']` will result in a segmentation with
        two labels, but passing `roi_names=[['foo(a|b)']]` will result in
        one label for both `'fooa'` and `'foob'`.

        In general, the exact ordering of the returned labels cannot be
        guaranteed (unless all patterns in `roi_names` can only match
        a single name or are lists of strings).
        """
        labels: dict[str, list] = {}
        if not roi_names:
            labels = self._assign_labels(
                list(self.roi_names), roi_select_first, roi_separate
            )  # only the ones that match the regex
        elif isinstance(roi_names, list):
            labels = self._assign_labels(list(roi_names), roi_select_first)
        elif isinstance(roi_names, dict):
            for name, pattern in roi_names.items():
                if isinstance(pattern, str):
                    matching_names = list(
                        self._assign_labels([pattern], roi_select_first).keys()
                    )
                    if matching_names:
                        # {"GTV": ["GTV1", "GTV2"]} is the result of _assign_labels()
                        labels[name] = matching_names
                elif isinstance(
                    pattern, list
                ):  # for inputs that have multiple patterns for the input, e.g. {"GTV": ["GTV.*", "HTVI.*"]}
                    extracted_labels = []
                    for pattern_one in pattern:
                        matching_names = list(
                            self._assign_labels(
                                [pattern_one], roi_select_first
                            ).keys()
                        )
                        if matching_names:
                            extracted_labels.extend(
                                matching_names
                            )  # {"GTV": ["GTV1", "GTV2"]}
                    labels[name] = extracted_labels
        if isinstance(roi_names, str):
            roi_names = [roi_names]

        logger.debug(f"Found {len(labels)} labels", labels=labels)

        labels = {k: v for (k, v) in labels.items() if v != []}
        if not labels:
            if not ignore_missing_regex:
                msg = (
                    f"No ROIs matching {roi_names} found in {self.roi_names}."
                )
                raise ValueError(msg)
            else:
                return None

        size = reference_image.GetSize()[::-1] + (len(labels),)
        mask = np.zeros(size, dtype=np.uint8)

        seg_roi_indices = {}
        if not roi_names:
            for name, label in labels.items():
                self.get_mask(reference_image, mask, name, label, continuous)
            seg_roi_indices = {
                "_".join(k): v
                for v, k in groupby(labels, key=lambda x: labels[x])
            }
        elif isinstance(roi_names, dict):
            for i, (name, label_list) in enumerate(labels.items()):
                for label in label_list:
                    self.get_mask(reference_image, mask, label, i, continuous)
                seg_roi_indices[name] = i

        mask[mask > 1] = 1
        mask = sitk.GetImageFromArray(mask, isVector=True)
        mask.CopyInformation(reference_image)

        mask = Segmentation(
            mask,
            roi_indices=seg_roi_indices,
            existing_roi_indices=existing_roi_indices,
            raw_roi_names=labels,
            metadata=self.metadata,
        )  # in the segmentation, pass all the existing roi names and then process is in the segmentation class

        return mask

    def __repr__(self) -> str:
        """Return a string representation of the StructureSet object."""
        sorted_rois = sorted(self.roi_names)
        metadata_str_parts = []

        # Truncate the UID values for better readability
        for k, v in self.metadata.items():
            if k.endswith("UID"):
                metadata_str_parts.append(f"\t{k}: {v[-5:]} (truncated)")
            else:
                metadata_str_parts.append(f"\t{k}: {v}")
        metadata_str = "\n\t".join(metadata_str_parts)
        repr_string = f"\n<StructureSet\n\tROIs: {sorted_rois}\n\tMetadata:\n\t{metadata_str}\n>"
        return repr_string

    @classmethod
    def _load_rtstruct_data(
        cls,
        rtstruct_path: str | Path | bytes,
    ) -> FileDataset:
        """Load the DICOM RTSTRUCT file and return the FileDataset object."""
        match rtstruct_path:
            case str() | Path():
                dcm = dcmread(rtstruct_path, force=True)
            case bytes():
                rt_bytes = BytesIO(rtstruct_path)
                dcm = dcmread(rt_bytes, force=True)
            case _:
                msg = "Invalid type for 'rtstruct_path'. Must be str, Path, or bytes object."
                msg += f" Received: {type(rtstruct_path)}"
                raise ValueError(msg)

        assert dcm.Modality == "RTSTRUCT", (
            f"The dicom provided is not an RTSTRUCT file {dcm.Modality=}"
        )

        return dcm
