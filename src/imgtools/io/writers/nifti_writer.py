from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import SimpleITK as sitk

from imgtools.io.writers.base_classes import AbstractBaseWriter
from imgtools.logging import logger


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
class NiftiWriter(AbstractBaseWriter):
    compression_level: int = field(
        default=9,
        metadata={
            "help": "Compression level (0-9). Higher values mean better compression but slower writing."
        },
    )

    truncate_uid: int = field(
        default=0,
        metadata={"help": "Truncate any key that ends in UID from the end of the UID"},
    )

    # Make extensions immutable
    VALID_EXTENSIONS: ClassVar[list[str]] = [
        ".nii",
        ".nii.gz",
    ]
    MIN_COMPRESSION_LEVEL: ClassVar[int] = 0
    MAX_COMPRESSION_LEVEL: ClassVar[int] = 9

    def __post_init__(self) -> None:
        """Validate writer configuration."""
        super().__post_init__()

        if (
            not self.MIN_COMPRESSION_LEVEL
            <= self.compression_level
            <= self.MAX_COMPRESSION_LEVEL
        ):
            msg = f"Invalid compression level {self.compression_level}. "
            msg += f"Must be between {self.MIN_COMPRESSION_LEVEL} and {self.MAX_COMPRESSION_LEVEL}."
            raise NiftiWriterValidationError(msg)

    def resolve_path(self, **kwargs: Any) -> Path:  # noqa
        """Adjust UID keywords args, then let AbstractBaseWriter handle normally."""
        updated_kwargs = dict()

        for key, value in kwargs.items():
            if key.endswith("UID") and self.truncate_uid > 0:
                updated_kwargs[key] = str(value)[-self.truncate_uid :]
            else:
                updated_kwargs[key] = value
        return super().resolve_path(**updated_kwargs)

    def save(self, image: sitk.Image | np.ndarray, **kwargs: str | int) -> Path:
        """Write the SimpleITK image to a NIFTI file."""
        match image:
            case sitk.Image():
                pass
            case np.ndarray():
                image = sitk.GetImageFromArray(image)
            case _:
                msg = "Input must be a SimpleITK Image or a numpy array" # type: ignore
                raise NiftiWriterValidationError(msg)

        out_path = self.resolve_path(**kwargs)

        logger.debug(
            "writing image to file",
            path=out_path,
        )

        try:
            sitk.WriteImage(
                image,
                str(out_path),
                useCompression=True,
                compressionLevel=self.compression_level,
            )
        except Exception as e:
            msg = f"Error writing image to file {out_path}: {e}"
            raise NiftiWriterIOError(msg) from e
        else:
            logger.debug("Image saved successfully.", out_path=out_path, params=kwargs)
            return out_path
