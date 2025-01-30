from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Iterator, List, Sequence

import numpy as np


@dataclass
class RTSTRUCTMetadata:
    """Dataclass for RTSTRUCT metadata.

    New keys can be added as needed.
    """

    PatientID: str
    StudyInstanceUID: str
    SeriesInstanceUID: str
    Modality: str
    ReferencedSeriesInstanceUID: str
    OriginalROINames: Sequence[str]
    OriginalNumberOfROIs: int

    def keys(self) -> List[str]:
        return [attr_field.name for attr_field in fields(self)]

    def items(self) -> List[tuple[str, str]]:
        return [
            (attr_field.name, getattr(self, attr_field.name))
            for attr_field in fields(self)
        ]

    def to_dict(self) -> dict:
        return asdict(self)

    def __getitem__(self, key: str) -> str:
        return getattr(self, key)

    def __rich_repr__(self) -> Iterator[tuple[str, str | Sequence[str]]]:
        # for each key-value pair, 'yield key, value'
        for attr_field in fields(self):
            if attr_field.name == "OriginalROINames":
                continue  # skip OriginalROINames for brevity
            elif attr_field.name.endswith("UID"):
                yield (
                    attr_field.name,
                    f"...{getattr(self, attr_field.name)[-10:]}",
                )
            else:
                yield attr_field.name, getattr(self, attr_field.name)

    # or 'key in RTSTRUCTMetadata' to check if a key exists
    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    # implement dict-like 'update' method
    def update(self, **kwargs: str) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class ContourSlice(np.ndarray):
    """Represents the contour points for a single slice.
    Simply a NumPy array with shape (n_points, 3) where the last dimension
    represents the x, y, and z coordinates of each point.
    """

    def __new__(cls, input_array: np.ndarray) -> ContourSlice:
        obj = np.asarray(input_array).view(cls)
        return obj

    def __array_finalize__(self, obj: np.ndarray | None) -> None:
        if obj is None:
            return
        assert self.ndim == 2
        assert self.shape[1] == 3

    def __repr__(self) -> str:
        return f"ContourSlice<points.shape={self.shape}>"


@dataclass
class ROI:
    """Represents a region of interest (ROI), containing slices of contours."""

    name: str
    referenced_roi_number: int
    num_points: int
    slices: List[ContourSlice]

    def __str__(self) -> str:
        return (
            f"{self.name} (ROI#={self.referenced_roi_number}) "
            f"{self.NumSlices} slices & {self.NumberOfContourPoints} points"
        )

    def __repr__(self) -> str:
        return (
            f"ROI<name={self.name}, ReferencedROINumber={self.referenced_roi_number}, "
            f"num_slices={self.NumSlices}, num_points={self.NumberOfContourPoints}>"
        )

    def __len__(self) -> int:
        return len(self.slices)

    def __iter__(self) -> Iterator:
        return iter(self.slices)

    @property
    def ReferencedROINumber(self) -> int:  # noqa N802
        return self.referenced_roi_number

    @property
    def NumSlices(self) -> int:  # noqa N802
        return len(self.slices)

    @property
    def NumberOfContourPoints(self) -> int:  # noqa N802
        return self.num_points

    def to_dict(self) -> dict:
        return asdict(self)
