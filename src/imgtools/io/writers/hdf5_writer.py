from pathlib import Path
from typing import Any

from .abstract_base_writer import AbstractBaseWriter


class HDF5WriterError(Exception):
    """Base exception for HDF5Writer errors."""

    pass


class HDF5Writer(AbstractBaseWriter):
    """Class for managing HDF5 file writing."""

    def __post_init__(self) -> None:
        self._validate_h5py()
        self.super().__post_init__()

    def save(self, data: Any, path: Path) -> None:
        """Save data to HDF5 file.
         
        TODO: see PyTables for more advanced HDF5 writing options.

        Args:
            data: Data to save.
        """
        pass
