from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import numpy as np
import SimpleITK as sitk

from .abstract_base_writer import AbstractBaseWriter


class NumpyWriterError(Exception):
    """Base exception for NumpyWriter errors."""

    pass


class NumpyWriterValidationError(NumpyWriterError):
    """Raised when validation of writer configuration fails."""

    pass


@dataclass
class NumPyWriter(
    AbstractBaseWriter[
        np.ndarray | sitk.Image | dict[str, np.ndarray | sitk.Image]
    ]
):
    """Write data to NumPy files with metadata support for SimpleITK images.

    This writer supports saving:
    - A single NumPy array or SimpleITK image with metadata.
    - Multiple arrays or images as a dictionary of key-value pairs.
    """

    compressed: bool = field(
        default=True,
        metadata={
            "help": "If True, saves multiple images in a compressed `.npz` format."
        },
    )

    VALID_EXTENSIONS: ClassVar[list[str]] = [".npy", ".npz"]

    def __post_init__(self) -> None:
        if not any(
            self.filename_format.endswith(ext) for ext in self.VALID_EXTENSIONS
        ):
            msg = (
                f"Invalid filename format {self.filename_format}. "
                f"Must end with one of {self.VALID_EXTENSIONS}."
            )
            raise NumpyWriterValidationError(msg)

    def _to_numpy(
        self, data: np.ndarray | sitk.Image
    ) -> tuple[np.ndarray, dict]:
        """Convert input data to NumPy array and extract metadata if it's a SimpleITK image."""
        if isinstance(data, sitk.Image):
            return (
                sitk.GetArrayFromImage(data),
                {
                    "spacing": data.GetSpacing(),
                    "origin": data.GetOrigin(),
                    "direction": data.GetDirection(),
                },
            )
        elif isinstance(data, np.ndarray):
            return data, {}
        else:
            msg = f"Unsupported data type: {type(data)}"
            raise NumpyWriterValidationError(msg)

    def save(
        self,
        data: np.ndarray | sitk.Image | dict[str, np.ndarray | sitk.Image],
        **kwargs: object,
    ) -> Path:
        """Save data to a NumPy file with optional metadata.

        Parameters
        ----------
        data : np.ndarray | sitk.Image | dict[str, np.ndarray | sitk.Image]
            The data to save. Can be a single image or a dictionary of images.

        Returns
        -------
        Path
            The path to the saved file.

        Raises
        ------
        NumpyWriterValidationError
            If the input data is invalid or unsupported.
        """
        out_path = self.resolve_path(**kwargs)

        if isinstance(data, (np.ndarray, sitk.Image)):
            # Single image or array
            array, metadata = self._to_numpy(data)
            np.savez_compressed(out_path, image_array=array, **metadata)
        elif isinstance(data, dict):
            # Multiple images or arrays
            arrays = {}
            metadata = {}
            for key, value in data.items():
                array, meta = self._to_numpy(value)
                arrays[key] = array
                for meta_key, meta_value in meta.items():
                    metadata[f"{key}_{meta_key}"] = meta_value
            if self.compressed:
                np.savez_compressed(
                    out_path, allow_pickle=False, **arrays, **metadata
                )
            else:
                np.savez(out_path, allow_pickle=False, **arrays, **metadata)
        else:
            raise NumpyWriterValidationError(
                "Data must be a NumPy array, SimpleITK image, or a dictionary of these types."
            )

        self.add_to_index(
            out_path,
            include_all_context=True,
            filepath_column="path",
            replace_existing=True,
            **kwargs,
        )
        return out_path

    @staticmethod
    def load(filepath: Path) -> sitk.Image | dict[str, sitk.Image]:
        """Load data from a `.npz` file and reconstruct SimpleITK images if metadata is present.

        Parameters
        ----------
        filepath : Path
            Path to the `.npz` file.

        Returns
        -------
        sitk.Image | dict[str, sitk.Image]
            Reconstructed SimpleITK image(s) with metadata.

        Raises
        ------
        NumpyWriterError
            If the file is invalid or missing required metadata.
        """
        try:
            with np.load(filepath, allow_pickle=True) as data:
                arrays = {}
                for key in data.files:
                    if key == "image_array":
                        # Single image case
                        image = sitk.GetImageFromArray(data["image_array"])
                        metadata_keys = [
                            "spacing",
                            "origin",
                            "direction",
                        ]
                        if all(k in data for k in metadata_keys):
                            image.SetSpacing(data["spacing"])
                            image.SetOrigin(data["origin"])
                            image.SetDirection(data["direction"])
                        return image
                    elif key.endswith("_array"):
                        # Multi-image case
                        array_key = key.replace("_array", "")
                        arrays[array_key] = data[key]
                    elif "_" not in key:
                        continue
                # If it's a multi-image case, reassemble all images with their metadata
                images = {}
                for key, array in arrays.items():
                    image = sitk.GetImageFromArray(array)
                    for meta_key in ["spacing", "origin", "direction"]:
                        if f"{key}_{meta_key}" in data:
                            setattr(
                                image,
                                f"Set{meta_key.capitalize()}",
                                data[f"{key}_{meta_key}"],
                            )
                    images[key] = image
                return images
        except Exception as e:
            msg = f"Failed to load data from {filepath}: {e}"
            raise NumpyWriterError(msg) from e
