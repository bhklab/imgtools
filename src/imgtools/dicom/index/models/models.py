from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

from pydicom import dcmread
from sqlalchemy import JSON, Column, ForeignKey, String, Table
from sqlalchemy.orm import relationship
from sqlalchemy.orm.decl_api import registry

from imgtools.logging import logger

if TYPE_CHECKING:
    from pathlib import Path

mapper_registry = registry()


def repr_mixin(cls) -> type:  # type: ignore  # noqa: ANN001
    """
    A decorator to add a customizable __repr__ method to SQLAlchemy ORM models.

    Includes scalar fields (e.g., columns) and prints the length of lists for relationships.
    """

    def __repr_method__(self) -> str:  # type: ignore  # noqa: N807, ANN001
        # Fetch attributes and handle lists separately
        attrs = {
            key: (len(value) if isinstance(value, list) else value)
            for key, value in vars(self).items()
            if not key.startswith("_")
            and isinstance(value, (str, int, float, list))
        }
        class_name = self.__class__.__name__
        fields = ",\n  ".join(f"{key}={value}" for key, value in attrs.items())
        return f"<{class_name}(\n  {fields}\n)>"

    cls.__repr__ = __repr_method__
    return cls


####################################################################################################
# PATIENT
####################################################################################################


# Patient Table
@repr_mixin
@mapper_registry.mapped
@dataclass
class Patient:
    __table__ = Table(
        "patients",
        mapper_registry.metadata,
        Column(
            "PatientID", String, primary_key=True, index=True
        ),  # PRIMARY KEY
    )

    # Metadata from DICOM
    PatientID: str = field(init=True)

    # Relationships
    studies: List[Study] = field(default_factory=list)

    __mapper_args__ = {  # type: ignore
        "properties": {
            "studies": relationship("Study", back_populates="patient"),
        }
    }

    @classmethod
    def from_metadata(cls, metadata: Dict[str, str]) -> Patient:
        """
        Create a Patient instance from metadata.

        Parameters
        ----------
        metadata : Dict[str, Optional[str]]
                        Patient metadata.

        Returns
        -------
        Patient
                        A Patient instance.
        """
        return cls(
            PatientID=metadata["PatientID"],
        )

    @property
    def num_studies(self) -> int:
        """
        Get the number of studies for the patient.

        Returns
        -------
        int
                        The number of studies.
        """
        return len(self.studies)

    @property
    def num_series(self) -> int:
        """
        Get the number of series for the patient.

        Returns
        -------
        int
                        The number of series.
        """
        return sum(len(study.series) for study in self.studies)

    @property
    def modalities(self) -> Dict[str, int]:
        """
        Get the list of modalities for the patient.

        Returns
        -------
        List[str]
                        The list of modalities.
        """
        modalities = [
            modality for study in self.studies for modality in study.modalities
        ]
        return dict(Counter(modalities))

    @property
    def series(self) -> List[Series]:
        """
        Get the series for the patient.

        Returns
        -------
        List[Series]
                        The series.
        """
        return [series for study in self.studies for series in study.series]

    @property
    def rtstructs(self) -> List[Series]:
        """
        Get the RTSTRUCT series for the patient.

        Returns
        -------
        List[Series]
                        The RTSTRUCT series.
        """
        return [
            series for series in self.series if series.Modality == "RTSTRUCT"
        ]


####################################################################################################
# STUDY
####################################################################################################


# Study Table
@repr_mixin
@mapper_registry.mapped
@dataclass
class Study:
    __table__ = Table(
        "studies",
        mapper_registry.metadata,
        Column(
            "StudyInstanceUID", String, primary_key=True, index=True
        ),  # PRIMARY KEY
        Column(
            "PatientID",
            String,
            ForeignKey("patients.PatientID"),
            nullable=False,
        ),
    )

    # Metadata from DICOM
    StudyInstanceUID: str = field(init=True)  # PRIMARY KEY
    PatientID: str = field(init=True)  # FOREIGN KEY

    # Relationships
    patient: Patient = field(init=False)
    series: List[Series] = field(default_factory=list)

    __mapper_args__ = {  # type: ignore
        "properties": {
            "patient": relationship("Patient", back_populates="studies"),
            "series": relationship("Series", back_populates="study"),
        }
    }

    @classmethod
    def from_metadata(cls, metadata: Dict[str, str]) -> Study:
        """
        Create a Study instance from metadata.

        Parameters
        ----------
        metadata : Dict[str, Optional[str]]
                        Study metadata.

        Returns
        -------
        Study
                        A Study instance.
        """
        return cls(
            StudyInstanceUID=metadata["StudyInstanceUID"],
            PatientID=metadata["PatientID"],
        )

    @property
    def num_files(self) -> int:
        """
        Get the number of files in the study.

        Returns
        -------
        int
                        The number of files.
        """
        return sum(series.num_files for series in self.series)

    @property
    def modalities(self) -> Dict[str, int]:
        """
        Get the list of modalities in the study.

        Returns
        -------
        List[str]
                        The list of modalities.
        """

        modalities = [series.Modality for series in self.series]
        return dict(Counter(modalities))

    @property
    def unique_modalities(self) -> List[str]:
        """
        Get the unique modalities in the study.

        Returns
        -------
        List[str]
                        The unique modalities.
        """
        return list(self.modalities.keys())


####################################################################################################
# SERIES, RTSTRUCTSERIES, ...
####################################################################################################


@repr_mixin
@mapper_registry.mapped
@dataclass
class Series:
    __table__ = Table(
        "series",
        mapper_registry.metadata,
        Column(
            "SeriesInstanceUID", String, primary_key=True, index=True
        ),  # PRIMARY KEY
        Column(
            "StudyInstanceUID",
            String,
            ForeignKey("studies.StudyInstanceUID"),
            nullable=False,
        ),
        Column("Modality", String, nullable=False),
        Column("_RTSTRUCT", JSON, nullable=True),
        Column("_MR", JSON, nullable=True),
    )

    # Metadata from DICOM
    SeriesInstanceUID: str = field(init=True)  # PRIMARY KEY
    StudyInstanceUID: str = field(init=True)  # FOREIGN KEY
    Modality: str = field(init=True)
    _RTSTRUCT: Optional[Dict[str, str]] = field(default_factory=dict)
    _MR: Optional[Dict[str, str]] = field(default_factory=dict)

    # Relationships
    study: Study = field(init=False)
    images: List[Image] = field(default_factory=list)

    __mapper_args__ = {  # type: ignore
        "properties": {
            "study": relationship("Study", back_populates="series"),
            "images": relationship("Image", back_populates="series"),
        },
    }

    @classmethod
    def from_metadata(
        cls, metadata: Dict[str, str], file_path: Path
    ) -> Series:
        base_cls = cls(
            SeriesInstanceUID=metadata["SeriesInstanceUID"],
            StudyInstanceUID=metadata["StudyInstanceUID"],
            Modality=metadata["Modality"],
        )

        match metadata["Modality"]:
            case "RTSTRUCT":
                try:
                    ds = dcmread(file_path, stop_before_pixels=True)
                    logger.info(f"Reading RTSTRUCT file: {file_path}")
                    roi_names = [
                        roi.ROIName for roi in ds.StructureSetROISequence
                    ]
                    rfrs = ds.ReferencedFrameOfReferenceSequence[0]
                    ref_series_seq = (
                        rfrs.RTReferencedStudySequence[0]
                        .RTReferencedSeriesSequence[0]
                        .SeriesInstanceUID
                    )
                    frame_of_reference = rfrs.FrameOfReferenceUID
                    base_cls._RTSTRUCT = {
                        "ROINames": ",".join(roi_names),
                        "RTReferencedSeriesUID": ref_series_seq,
                        "FrameOfReferenceUID": frame_of_reference,
                    }
                except Exception as e:
                    logger.exception(
                        f"Error reading RTSTRUCT file: {file_path}",
                        error=str(e),
                    )
                    raise e
            case "MR":
                try:
                    ds = dcmread(file_path, stop_before_pixels=True)
                    logger.info(f"Reading MR file: {file_path}")
                    _mr = {
                        "RepetitionTime": ds.RepetitionTime,
                        "EchoTime": ds.EchoTime,
                        "SliceThickness": ds.SliceThickness,
                        "ScanningSequence": ds.ScanningSequence,
                        "MagneticFieldStrength": ds.MagneticFieldStrength,
                        "ImagedNucleus": ds.ImagedNucleus,
                    }

                    base_cls._MR = {k: str(v) for k, v in _mr.items()}
                except Exception as e:
                    logger.exception(
                        f"Error reading MR file: {file_path}", error=str(e)
                    )
                    raise e
            case _:
                pass

        return base_cls

    @property
    def num_files(self) -> int:
        return len(self.images)

    @property
    def RTReferencedSeriesUID(self) -> Optional[str]:  # noqa: N802
        return (
            self._RTSTRUCT.get("RTReferencedSeriesUID", None)
            if self._RTSTRUCT
            else None
        )

    @property
    def ROINames(self) -> Optional[str]:  # noqa: N802
        return self._RTSTRUCT.get("ROINames", None) if self._RTSTRUCT else None


####################################################################################################
# IMAGE
####################################################################################################


# Image Table
@repr_mixin
@mapper_registry.mapped
@dataclass
class Image:
    __table__ = Table(
        "images",
        mapper_registry.metadata,
        Column(
            "FilePath", String, primary_key=True, index=True
        ),  # PRIMARY KEY
        Column("SOPInstanceUID", String, nullable=False),
        Column(
            "SeriesInstanceUID",
            String,
            ForeignKey("series.SeriesInstanceUID"),
            nullable=False,
        ),
    )

    # Metadata from DICOM
    FilePath: str = field(init=True)
    SOPInstanceUID: str = field(init=True)
    SeriesInstanceUID: str = field(init=True)

    # Relationships
    series: Series = field(init=False)

    __mapper_args__ = {  # type: ignore
        "properties": {
            "series": relationship("Series", back_populates="images"),
        }
    }

    @classmethod
    def from_metadata(cls, metadata: Dict[str, str], file_path: Path) -> Image:
        """
        Create a Image instance from metadata.

        Parameters
        ----------
        metadata : Dict[str, Optional[str]]
                        Image metadata.

        Returns
        -------
        Image
                        A Image instance.
        """
        return cls(
            SOPInstanceUID=metadata["SOPInstanceUID"],
            SeriesInstanceUID=metadata["SeriesInstanceUID"],
            FilePath=file_path.as_posix(),
        )
