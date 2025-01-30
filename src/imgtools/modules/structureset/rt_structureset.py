from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, List, TypeAlias

import numpy as np

from imgtools.exceptions import MissingROIError, ROIContourError
from imgtools.logging import logger
from imgtools.modules.structureset import (
    ROI,
    ContourSlice,
    DicomInput,
    RTSTRUCTMetadata,
    extract_rtstruct_metadata,
    load_rtstruct_dcm,
)

if TYPE_CHECKING:
    from pydicom.dataset import FileDataset

# Define type aliases
SelectionPattern: TypeAlias = str | list[str]
"""Alias for a string or a list of strings used to represent selection patterns."""

ROINamePatterns: TypeAlias = (
    SelectionPattern | dict[str, SelectionPattern] | None
)
"""Alias for ROI names, which can be:
- A single string pattern.
- A list of string patterns.
- A dictionary mapping strings to patterns or lists of patterns.
- None, to represent the absence of any selection.
"""


class ROIExtractionErrorMsg(str):
    pass


@dataclass
class RTStructureSet:
    """Represents the entire structure set, containing multiple ROIs."""

    # these are the EXTRACTED ROI names, not the original ones in the RTSTRUCT
    # since some will fail to extract
    # missing_rois = set(self.rois.keys()) - set(self.roi_names)
    roi_names: List[str]
    metadata: RTSTRUCTMetadata

    roi_map: dict[str, ROI] = field(repr=False)

    roi_map_errors: dict[str, ROIExtractionErrorMsg] = field(
        repr=False, default_factory=dict
    )

    @property
    def rois(self) -> dict[str, ROI]:
        return {
            roi_name: roi
            for roi_name, roi in self.roi_map.items()
            if isinstance(roi, ROI)
        }

    @classmethod
    def from_dicom(
        cls,
        dicom: DicomInput,
        suppress_warnings: bool = False,
        roi_name_pattern: str | None = None,
        ignore_case: bool = True,
    ) -> RTStructureSet:
        """Create a RTStructureSet object from an RTSTRUCT DICOM file.

        Parameters
        ----------
        dicom : str | Path | bytes | FileDataset
            The RTSTRUCT DICOM object.
        suppress_warnings : bool, optional
            Whether to suppress warnings when extracting ROI points.
            Default is False.
        roi_name_pattern : str, optional
            A regular expression pattern to match ROI names. Default is None.
        ignore_case : bool, optional
            If True, ignore case when matching ROI names. Default is True.

        Returns
        -------
        RTStructureSet
            The structure set data extracted from the RTSTRUCT.
        """
        logger.debug("Loading RTSTRUCT DICOM file.", dicom=dicom)
        dicom_rt = load_rtstruct_dcm(dicom)
        metadata = extract_rtstruct_metadata(dicom_rt)

        case_ignore = (
            re.IGNORECASE if ignore_case else 0
        )  # for pattern matching

        # Create a dictionary to store the ROI objects
        roi_dict: dict[str, ROI] = {}
        roi_errors: dict[str, ROIExtractionErrorMsg] = {}
        extracted_rois = []  # only track successfully extracted ROIs

        # Extract ROI contour points for each ROI and
        for roi_index, roi_name in enumerate(metadata["OriginalROINames"]):
            if roi_name_pattern and not re.match(
                roi_name_pattern, roi_name, flags=case_ignore
            ):
                continue
            try:
                extracted_roi = cls._get_roi_points(
                    dicom_rt, roi_index=roi_index, roi_name=roi_name
                )
            except ROIContourError as ae:
                if not suppress_warnings:
                    logger.warning(
                        f"Could not get points for ROI `{roi_name}`.",
                        rtstruct_series=metadata["SeriesInstanceUID"],
                        error=ae,
                    )
                error_string = f"Error extracting ROI '{roi_name}': {ae}"
                roi_errors[roi_name] = ROIExtractionErrorMsg(error_string)
            else:
                roi_dict[roi_name] = extracted_roi
                extracted_rois.append(roi_name)
        logger.debug(
            "Finished extracting ROI points.",
            extracted_rois=extracted_rois,
            failed_rois=list(roi_errors.keys()),
        )
        # Create a new RTStructureSet object
        structure_set = cls(
            roi_map=roi_dict,
            roi_names=extracted_rois,
            roi_map_errors=roi_errors,
            metadata=metadata,
        )

        return structure_set

    def match_roi(
        self, pattern: str, ignore_case: bool = True
    ) -> List[str] | None:
        """Search for ROI names in self.roi_names based on a regular expression pattern.

        Parameters
        ----------
        pattern : str
            The regular expression pattern to search for.
        ignore_case : bool, optional
            Whether to ignore case in the regular expression matching. Default is False.

        Returns
        -------
        List[str] | None
            A list of matching ROI names if any match, None otherwise.

        Examples
        --------
        Assume the following rt has the roi names: ['GTV1', 'GTV2', 'PTV', 'CTV_0', 'CTV_1']
        >>> structure_set = RTStructureSet.from_dicom(
        ...     "path/to/rtstruct.dcm"
        ... )
        >>> structure_set.match_roi("GTV.*")
        ['GTV1', 'GTV2']
        >>> structure_set.match_roi(
        ...     "ctv.*", ignore_case=True
        ... )
        ['CTV_0', 'CTV_1']
        """
        _flags = re.IGNORECASE if ignore_case else 0
        matches = [
            name
            for name in self.roi_names
            if re.fullmatch(pattern, name, flags=_flags)
        ]
        return matches if matches else None

    def __getitem__(self, name: str) -> list[ROI] | str:
        """Extend slice based access to the data in the RTStructureSet

        rtss = RTStructureSet.from_dicom(...)

        1. rtss['GTV']
            if key exists EXACTLY as 'GTV' in the self.rois dict, return the `ROI` instance
            representing the contour points (returned as a LIST of only 1 element)
        2. rtss['gtv.*']
            when trying to index using a key that is a regex pattern,
            match the roi names to a pattern that starts with 'gtv' (case-insensitive),
            and if there exists any matched rois, return a `LIST` of `ROI` instances reprensenting
            their contour points.
        3. rtss['PatientID'], or any other attribute of structureset.custom_types.RTSTRUCTMetadata
            if the key is also an attribute of the RTSTRUCTMetadata class, return the value
            of the attribute in the metadata.

        See Also
        --------
        imgtools.modules.structureset.custom_types.ROI
        """
        if name in self.roi_map:
            return [self.roi_map[name]]
        # Check if name is a pattern and match against ROI names
        elif matched_rois := self.match_roi(name, ignore_case=True):
            return [self.roi_map[roi] for roi in matched_rois]
        elif self.metadata:
            if name in self.metadata:
                return getattr(self.metadata, name)
            else:
                msg = f"{name} not found in ROI names OR metadata."
                msg += f" Available ROIs: {self.roi_names}"
                msg += f" Available metadata: {self.metadata.keys()}"
                raise MissingROIError(msg)
        else:
            errmsg = f"Key `{name}` not found in structure set's ROI names or metadata."
            raise MissingROIError(errmsg)

    def _ipython_key_completions_(self) -> list[str]:
        """IPython/Jupyter tab completion when indexing rtstruct[...]"""
        return list(self.metadata.keys()) + self.roi_names

    def __rich_repr__(self) -> Iterator:
        yield "rois", len(self)  # len(self.roi_names)
        yield "roi_names", ", ".join(self.roi_names)  # self.roi_names
        if self.roi_map_errors:
            yield (
                "failed_roi_extractions",
                ", ".join(self.roi_map_errors.keys()),
            )
        yield "Metadata", self.metadata

    def __len__(self) -> int:
        return len(self.roi_names)

    def __iter__(self) -> Iterator[tuple[str, ROI]]:
        # iterate through self.rois.items if key is in self.roi_names
        for name in self.roi_names:
            yield name, self.roi_map[name]

    def items(self) -> List[tuple[str, ROI]]:
        return list(iter(self))

    @staticmethod
    def _get_roi_points(
        rtstruct: FileDataset, roi_index: int, roi_name: str
    ) -> ROI:
        """Extract and reshapes contour points for a specific ROI in an RTSTRUCT file.

        The passed in roi_index is what is used to index the ROIContourSequence,
        whereas the roi_name is mainly used for debugging, and saved in the returned `ROI`
        instance.

        This method assumes that the order of the rois in dcm.StructureSetROISequence is
        the same order that you will find their corresponding contour data in
        dcm.ROIContourSequence.

        Parameters
        ----------
        rtstruct : FileDataset
            The loaded DICOM RTSTRUCT file.
        roi_index : int
            The index of the ROI in the ROIContourSequence.
        roi_name : str
            The name of the ROI to extract points for.

        Returns
        -------
        imgtools.modules.structureset.ROI (which is a container for List[np.ndarray])
            A list of numpy arrays where each array contains the 3D physical coordinates
            of the contour points for a specific slice.

        Raises
        ------
        ROIContourError
            If the ROIContourSequence, ContourSequence, or ContourData is missing or malformed.

        Examples
        --------
        >>> rtstruct = dcmread(
        ...     "path/to/rtstruct.dcm", force=True
        ... )
        >>> StructureSet._get_roi_points(rtstruct, 0, "GTV")
        """
        # Notes
        # -----
        # The structure of the contour data in the DICOM RTSTRUCT file is as follows:
        # > ROIContourSequence (3006, 0039)
        # >> ReferencedROINumber (3006, 0084)
        # >> ContourSequence (3006, 0040)
        # >>> ContourData (3006, 0050)
        # >>> ContourGeometricType (3006, 0042)
        # >>> NumberOfContourPoints (3006, 0046)

        # Check for ROIContourSequence
        if not hasattr(rtstruct, "ROIContourSequence"):
            raise ROIContourError(
                "The DICOM RTSTRUCT file is missing 'ROIContourSequence'."
            )

        # Check if ROI index exists in the sequence
        if roi_index >= len(rtstruct.ROIContourSequence) or roi_index < 0:
            msg = (
                f"ROI index {roi_index} is out of bounds for the "
                f" 'ROIContourSequence' with length {len(rtstruct.ROIContourSequence)}."
            )
            raise ROIContourError(msg)

        roi_contour = rtstruct.ROIContourSequence[roi_index]

        # Check for ContourSequence in the specified ROI
        if not hasattr(roi_contour, "ContourSequence"):
            msg = (
                f"ROI at index {roi_index}, (ReferencedROINumber={roi_index + 1}) "
                "is missing 'ContourSequence';"
            )
            raise ROIContourError(msg)

        contour_sequence = roi_contour.ContourSequence

        # Check for ContourData in each contour
        contour_points = []
        for i, slc in enumerate(contour_sequence):
            if not hasattr(slc, "ContourData"):
                msg = f"Contour {i} in ROI at index {roi_index} is missing 'ContourData'. "
                raise ROIContourError(msg)
            roi_points = np.array(slc.ContourData).reshape(-1, 3)
            contour_slice = ContourSlice(roi_points)
            contour_points.append(contour_slice)
            num_points = slc.get("NumberOfContourPoints", 0)

        return ROI(
            roi_name,
            roi_contour.ReferencedROINumber,
            num_points,
            contour_points,
        )

    def summary_dict(self, exclude_errors: bool = False) -> dict:
        """Return a dictionary of summary information for the RTStructureSet."""

        roi_info = {}

        for name, roi in self.roi_map.items():
            if exclude_errors and not isinstance(roi, ROI):
                continue
            roi_info[name] = str(roi)

        return {
            "SuccessfullyExtractedROIs": len(self.roi_names),
            "ROIInfo": roi_info,
            "Metadata": self.metadata.to_dict(),
        }

    def _handle_roi_names(self, roi_names: ROINamePatterns = None) -> None:
        """Handle the ROI names extracted from the RTSTRUCT file."""
        match roi_names:
            case None | []:
                return None
            case str() as single_pattern_str:  # roi_names is a single string
                pass
            case [*roi_patterns]:  # when roi_names is a non-empty list
                pass
            case dict() as roi_map:  # roi_names is a dictionary
                for name, pattern in roi_map.items():
                    match pattern:
                        case str() as pattern_str:
                            # Handle when a dictionary value is a string
                            pass
                        case []:
                            # Handle when a dictionary value is an empty list
                            pass
                        case [*patterns]:
                            # Handle when a dictionary value is a non-empty list
                            pass
            case _:
                # Handle unexpected cases or raise an error if needed
                pass


##############################################
# Benchmarking functions


def load_new_rtstruct(file_path: Path) -> RTStructureSet:
    rtstruct = RTStructureSet.from_dicom(file_path)
    return rtstruct


def load_old_rtstruct(file_path: Path) -> StructureSet:
    rtstruct = StructureSet.from_dicom(rtstruct_path=file_path)
    return rtstruct


if __name__ == "__main__":
    import time
    from pathlib import Path

    import pandas as pd
    from rich import print  # noqa

    from imgtools.modules.structureset.structure_set import StructureSet

    index = Path(".imgtools/imgtools_data.csv")
    full_index = pd.read_csv(index, index_col=0)

    df = full_index[full_index["modality"] == "RTSTRUCT"]

    collections = set(df["folder"].apply(lambda x: x.split("/")[1]).tolist())
    print(
        f"There are a total of {len(df)} RTSTRUCT files in the index for {collections} collections."
    )

    # store the metadata for each rtstruct in a dictionary

    paths = df["file_path"].tolist()
    logger.setLevel("WARNING")  # type: ignore
    start_new = time.time()
    for _i in range(10):
        for path in paths:
            _ = load_new_rtstruct(path)

    end_new = time.time()

    start_old = time.time()
    for _i in range(10):
        for path in paths:
            __ = load_old_rtstruct(path)
    end_old = time.time()

    ##############################
    # use rich table print to display the results

    from rich import table as rich_table

    rtable = rich_table.Table()
    rtable.add_column("Method", justify="right")
    rtable.add_column("Time", justify="right")
    rtable.add_row("New", f"{end_new - start_new:.2f} seconds")
    rtable.add_row("Old", f"{end_old - start_old:.2f} seconds")

    print(rtable)
    # for idx, row in df.iterrows():
    #     file_path = row["file_path"]

    #     start = time.time()
    #     rtstruct = RTStructureSet.from_dicom(
    #         file_path,
    #         suppress_warnings=True,
    #     )
    #     print(f"Time taken: {time.time() - start:.2f} seconds")

    #     start = time.time()
    #     rtstruct_old = StructureSet.from_dicom(rtstruct_path=file_path)
    #     print(f"Time taken: {time.time() - start:.2f} seconds")

    #     rt_metadata[file_path] = rtstruct.summary_dict(exclude_errors=False)

    #     print(rtstruct)

    #     break
    # rt_metadata = {}

    # # # vizualize the profiling stats with snakeviz
    # import json

    # rt_metadata_json_path = index.parent / "rt_metadata.json"
    # with rt_metadata_json_path.open("w") as f:
    #     json.dump(rt_metadata, f, indent=4, sort_keys=True)
