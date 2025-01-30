from io import BytesIO
from pathlib import Path
from typing import TypeAlias

from pydicom import dcmread
from pydicom.dataset import FileDataset

from imgtools.exceptions import InvalidDicomError, NotRTSTRUCTError, RTSTRUCTAttributeError

from .custom_types import RTSTRUCTMetadata

# Define a type alias for DICOM input types
DicomInput: TypeAlias = FileDataset | str | Path | bytes


def load_rtstruct_dcm(
    rtstruct_input: DicomInput,
    force: bool = True,
    stop_before_pixels: bool = True,
) -> FileDataset:
    """Load an RTSTRUCT DICOM file or bytes data and return the FileDataset object.

    Parameters
    ----------
    rtstruct_input : str | Path | bytes
        Path to the RTSTRUCT file or its content as bytes.
    force: bool (default = True)
        ignore dicoms that are missing their *File Meta Information* header.
    stop_before_pixels : bool
        If True, stop reading the DICOM file before the pixel data, by default True

    Returns
    -------
    FileDataset
        Parsed RTSTRUCT DICOM object.

    Raises
    ------
    InvalidDicomError
        If the input type is unsupported or the file is not an RTSTRUCT.
    NotRTSTRUCTError
        if the Modality field in the dicom is not `RTSTRUCT`
    """
    match rtstruct_input:
        case FileDataset():
            dicom = rtstruct_input
        case str() | Path():
            dicom = dcmread(rtstruct_input, force=force, stop_before_pixels=stop_before_pixels)
        case bytes():
            dicom = dcmread(
                BytesIO(rtstruct_input), force=force, stop_before_pixels=stop_before_pixels
            )
        case _:
            raise InvalidDicomError(
                f"Invalid input type for 'rtstruct_input': {type(rtstruct_input)}. "
                "Must be a str, Path, or bytes object."
            )

    if dicom.Modality != "RTSTRUCT":
        raise NotRTSTRUCTError(
            f"The provided DICOM is not an RTSTRUCT file. Found Modality: {dicom.Modality}"
        )

    return dicom


# Example usage of the decorator with refactored functions
def extract_roi_names(rtstruct: DicomInput) -> list[str]:
    """Extract ROI names from a FileDataset."""
    dcm_rtstruct: FileDataset = load_rtstruct_dcm(rtstruct)
    try:
        return [roi.ROIName for roi in dcm_rtstruct.StructureSetROISequence]
    except (AttributeError, IndexError) as e:
        errmsg = "Failed to extract ROI names from the RTSTRUCT file."
        raise RTSTRUCTAttributeError(errmsg) from e


def rtstruct_reference_seriesuid(rtstruct: DicomInput) -> str:
    """Return the Referenced SeriesInstanceUID from an RTSTRUCT."""
    dcm_rtstruct: FileDataset = load_rtstruct_dcm(rtstruct)
    try:
        return str(
            dcm_rtstruct.ReferencedFrameOfReferenceSequence[0]
            .RTReferencedStudySequence[0]
            .RTReferencedSeriesSequence[0]
            .SeriesInstanceUID
        )
    except (AttributeError, IndexError) as e:
        errmsg = "Failed to extract Referenced SeriesInstanceUID from the RTSTRUCT file."
        raise RTSTRUCTAttributeError(errmsg) from e


def extract_rtstruct_metadata(rtstruct: DicomInput) -> RTSTRUCTMetadata:
    """Extract metadata from the RTSTRUCT file."""
    dcm_rtstruct: FileDataset = load_rtstruct_dcm(rtstruct)
    roi_names = extract_roi_names(dcm_rtstruct)

    return RTSTRUCTMetadata(
        PatientID=dcm_rtstruct.PatientID,
        StudyInstanceUID=dcm_rtstruct.StudyInstanceUID,
        SeriesInstanceUID=dcm_rtstruct.SeriesInstanceUID,
        Modality=dcm_rtstruct.Modality,
        ReferencedSeriesInstanceUID=rtstruct_reference_seriesuid(dcm_rtstruct),
        OriginalROINames=roi_names,
        OriginalNumberOfROIs=len(roi_names),
    )


if __name__ == "__main__":
    import timeit

    # Load an RTSTRUCT file and extract metadata

    # Benchmark the metadata extraction 100 times
    def benchmark() -> None:
        rtstruct_path = Path(
            "/home/bioinf/bhklab/radiomics/readii-negative-controls/rawdata/RADCURE/images/dicoms/RADCURE-0006/StudyUID-46105/RTSTRUCT_SeriesUID-32605/00000001.dcm"
        )
        extract_rtstruct_metadata(rtstruct_path)

    # config
    REPEAT = 5
    NUMBER = 10

    print(f"Benchmark times for {REPEAT} repeats of {NUMBER} iterations:")

    times = timeit.repeat(benchmark, repeat=REPEAT, number=NUMBER)
    print(f"Average time per {NUMBER} iterations: {sum(times) / len(times):.6f} seconds")
