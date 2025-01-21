from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np

from imgtools.logging import logger

from .abstract_base_writer import AbstractBaseWriter


class NumpyWriterError(Exception):
    """Base exception for NumpyWriter errors."""

    pass


class NumpyWriterValidationError(NumpyWriterError):
    """Raised when validation of writer configuration fails."""

    pass


@dataclass
class NumPyWriter(AbstractBaseWriter):
    """Class for managing NumPy file writing."""

    # Make extensions immutable
    VALID_EXTENSIONS: ClassVar[list[str]] = [
        ".npy",
        ".npz",
    ]

    def __post_init__(self) -> None:
        if not any(self.filename_format.endswith(ext) for ext in self.VALID_EXTENSIONS):
            msg = (
                f"Invalid filename format {self.filename_format}. "
                f"Must end with one of {self.VALID_EXTENSIONS}."
            )
            raise NumpyWriterValidationError(msg)

    def save(self, data: Any, **kwargs) -> None:  # noqa
        """Save data to NumPy file.

        Parameters
        ----------
            data: Data to save.
        """

        # logger.debug("Saving.", kwargs=kwargs)

        # out_path = self.resolve_path(**kwargs)
        # _save_to_index = True
        # TODO: research about numpy saving and figure out if this logic is correct
        # TODO: maybe validate the type before this?
        
        pass