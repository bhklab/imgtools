from pathlib import Path
from typing import TypeAlias

import numpy as np
import SimpleITK as sitk

from .abstract_base_writer import AbstractBaseWriter

# a type to represent data that can be saved to HDF5
# for now, we consider 'np.ndarray', sitk.Image
HDF5Data: TypeAlias = np.ndarray | sitk.Image


class HDF5WriterError(Exception):
    """Base exception for HDF5Writer errors."""

    pass


class HDF5Writer(AbstractBaseWriter[np.ndarray | sitk.Image]):
    """Class for managing HDF5 file writing."""

    def __post_init__(self) -> None:
        super().__post_init__()

    def save(self, data: np.ndarray | sitk.Image, **kwargs: object) -> Path:
        """Save data to HDF5 file.

        TODO: see PyTables for more advanced HDF5 writing options.

        Args:
            data: Data to save.
        """

        raise NotImplementedError
