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
class NIFTIWriter(AbstractBaseWriter[sitk.Image | np.ndarray]):
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

        if not any(
            self.filename_format.endswith(ext) for ext in self.VALID_EXTENSIONS
        ):
            msg = (
                f"Invalid filename format {self.filename_format}. "
                f"Must end with one of {self.VALID_EXTENSIONS}."
            )
            raise NiftiWriterValidationError(msg)

    def save(self, data: sitk.Image | np.ndarray, **kwargs: object) -> Path:
        """Write the SimpleITK image to a NIFTI file.

        Parameters
        ----------
        data : sitk.Image | np.ndarray
            The SimpleITK image to save
        PatientID : str
            Required patient identifier
        **kwargs : object
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
        match data:
            case sitk.Image():
                image = data
            case np.ndarray():
                logger.debug("Converting numpy array to SimpleITK image.")
                image = sitk.GetImageFromArray(data)
            case _:
                msg = "Input must be a SimpleITK Image or a numpy array"
                raise NiftiWriterValidationError(msg)

        if (
            (
                out_path := self.resolve_path(**kwargs)
            ).exists()  # check if it exists
            # This will only be true if SKIP OR WARNING
            # OVERWRITE would have deleted the file
            and self.existing_file_mode == ExistingFileMode.SKIP
        ):
            logger.debug(
                "File exists, skipping.", kwargs=kwargs, out_path=out_path
            )
            return out_path

        try:
            logger.debug(
                f"Saving image to {out_path}.",
                kwargs=kwargs,
                out_path=out_path,
                compression_level=self.compression_level,
            )
            sitk.WriteImage(
                image,
                out_path.as_posix(),
                useCompression=True,
                compressionLevel=self.compression_level,
            )
        except Exception as e:
            msg = f"Error writing image to file {out_path}: {e}"
            raise NiftiWriterIOError(msg) from e
        else:
            logger.info("Image saved successfully.", out_path=out_path)

        # Log and dump metadata to CSV
        logger.debug(f"Image saved successfully: {out_path}")

        self.add_to_index(
            out_path,
            filepath_column="filepath",
            replace_existing=out_path.exists(),
        )
        return out_path
