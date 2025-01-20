from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import numpy as np
import SimpleITK as sitk

from imgtools.logging import logger

from .abstract_base_writer import AbstractBaseWriter, ExistingFileMode


class NiftiWriterError(Exception):
    """Base exception for NiftiWriter errors."""

    pass


class NiftiWriterValidationError(NiftiWriterError):
    """Raised when validation of writer configuration fails."""

    pass


class NiftiWriterIOError(NiftiWriterError):
    """Raised when I/O operations fail."""

    pass


@dataclass
class NIFTIWriter(AbstractBaseWriter):
    """Class for managing file writing with customizable paths and filenames for NIFTI files."""

    compression_level: int = field(
        default=9,
        metadata={
            "help": "Compression level (0-9). Higher mean better compression but slower writing."
        },
    )

    # Make extensions immutable
    VALID_EXTENSIONS: ClassVar[list[str]] = [
        ".nii",
        ".nii.gz",
    ]
    MAX_COMPRESSION_LEVEL: ClassVar[int] = 9
    MIN_COMPRESSION_LEVEL: ClassVar[int] = 0

    def __post_init__(self) -> None:
        """Validate writer.

        Parent class will create the output directory, validate filename pattern, and update
        ExtingFileMode if necessary.
        """
        super().__post_init__()

        if (
            not self.MIN_COMPRESSION_LEVEL
            <= self.compression_level
            <= self.MAX_COMPRESSION_LEVEL
        ):
            msg = (
                f"Invalid compression level {self.compression_level}. "
                f"Must be between {self.MIN_COMPRESSION_LEVEL} and "
                f"{self.MAX_COMPRESSION_LEVEL}."
            )
            raise NiftiWriterValidationError(msg)

        if not any(self.filename_format.endswith(ext) for ext in self.VALID_EXTENSIONS):
            msg = (
                f"Invalid filename format {self.filename_format}. "
                f"Must end with one of {self.VALID_EXTENSIONS}."
            )
            raise NiftiWriterValidationError(msg)

    def save(self, image: sitk.Image | np.ndarray, **kwargs: str | int) -> Path:
        """Write the SimpleITK image to a NIFTI file.

        Parameters
        ----------
        image : sitk.Image | np.ndarray
            The SimpleITK image to save
        PatientID : str
            Required patient identifier
        **kwargs : str | int
            Additional formatting parameters for the output path

        Returns
        -------
        Path
            Path to the saved file

        Raises
        ------
        NiftiWriterIOError
            If file exists and overwrite=False or if writing fails
        NiftiWriterValidationError
            If image is invalid
        """
        match image:
            case sitk.Image():
                pass
            case np.ndarray():
                logger.debug("Converting numpy array to SimpleITK image.")
                image = sitk.GetImageFromArray(image)
            case _:
                msg = "Input must be a SimpleITK Image or a numpy array"
                raise NiftiWriterValidationError(msg)

        logger.debug("Saving.", kwargs=kwargs)

        out_path = self.resolve_path(**kwargs)
        _save_to_index = True

        if out_path.exists():
            match self.existing_file_mode:
                case ExistingFileMode.SKIP:
                    logger.info("File exists, skipping.", out_path=out_path)
                    return out_path
                case _:
                    # This is assuming that it already exists in the index?
                    # perhaps we can add a check here to see if it exists in the index
                    _save_to_index = False

        try:
            logger.debug(
                f"Saving image to {out_path}.", compression_level=self.compression_level
            )
            sitk.WriteImage(
                image,
                str(out_path),
                useCompression=True,
                compressionLevel=self.compression_level,
            )
        except Exception as e:
            raise NiftiWriterIOError(
                f"Error writing image to file {out_path}: {e}"
            ) from e
        else:
            logger.info("Image saved successfully.", out_path=out_path)

        # Log and dump metadata to CSV
        logger.debug(f"Image saved successfully: {out_path}")

        if _save_to_index:
            self.add_to_index(out_path, **kwargs)
        return out_path
