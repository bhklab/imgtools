import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import SimpleITK as sitk
from SimpleITK import Image

from imgtools.io.writers import (
    ExistingFileMode,
    NIFTIWriter,
    NiftiWriterIOError,
    NiftiWriterValidationError,
)


class TestImage(Image):
    """A convenience class to store metadata information related to the image.

    Attributes
    ----------
    metadata : dict
        A dictionary to store metadata information related to the image.
    """

    metadata: dict

    pass


@pytest.fixture(scope="module")
def temp_nifti_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Fixture for creating a temporary directory for NIFTI files."""
    return tmp_path_factory.mktemp("nifti_files")


@pytest.fixture(
    params=[
        {
            "size": [32, 32],
            "pixel_type": sitk.sitkUInt8,
            "desc": "Small 2D image (32x32) with unsigned 8-bit integers",
            "PatientID": "patient1",
            "identifier": "small_2d_uint8",
            "random_info": "info1",
            "StudyInstanceUID": str(uuid.uuid4()),
        },
        {
            "size": [64, 64, 64],
            "pixel_type": sitk.sitkFloat32,
            "desc": "Medium 3D image (64x64x64) with 32-bit floating point values",
            "PatientID": "patient2",
            "identifier": "medium_3d_float32",
            "random_info": "info2",
            "StudyInstanceUID": str(uuid.uuid4()),
        },
        {
            "size": [256, 256, 128],
            "pixel_type": sitk.sitkFloat32,
            "desc": "Large 3D image (256x256x128) with 32-bit floating point values",
            "PatientID": "patient3",
            "identifier": "large_3d_float32",
            "random_info": "info3",
            "StudyInstanceUID": str(uuid.uuid4()),
        },
        {
            "size": [128, 128, 64],
            "pixel_type": sitk.sitkVectorFloat32,
            "desc": "Vector 3D image (128x128x64) with vectorized 32-bit floating point values",
            "PatientID": "patient4",
            "identifier": "vector_3d_float32",
            "random_info": "info4",
            "StudyInstanceUID": str(uuid.uuid4()),
        },
    ]
)
def parameterized_image(request: pytest.FixtureRequest) -> TestImage:
    """Parameterized fixture to generate SimpleITK images of varying sizes and types."""
    params = request.param

    if params["pixel_type"] == sitk.sitkVectorFloat32:
        image = sitk.VectorIndexSelectionCast(
            sitk.PhysicalPointSource(params["pixel_type"], size=params["size"]),
            0,
        )
    else:
        image = sitk.GaussianSource(
            params["pixel_type"],
            size=params["size"],
            mean=[16] * len(params["size"]),
            sigma=[8] * len(params["size"]),
        )

    test_image = TestImage(image)
    test_image.metadata = {
        k: v for k, v in params.items() if k not in ["size", "pixel_type"]
    }
    return test_image


@pytest.fixture(params=list(ExistingFileMode))
def nifti_writer(temp_nifti_dir: Path, request: pytest.FixtureRequest) -> NIFTIWriter:
    """Fixture for creating a parameterized NIFTIWriter instance."""

    mode = request.param
    mode_dir = temp_nifti_dir / f"EXISTINGFILEMODE-{mode.name}"
    return NIFTIWriter(
        root_directory=mode_dir,
        filename_format="{PatientID}/{identifier}_VERSION-{version}.nii.gz",
        existing_file_mode=mode,
        create_dirs=True,
        sanitize_filenames=True,
        compression_level=9,
        overwrite_index=False,
    )


@pytest.mark.xdist_group("nifti_writer")
def test_parameterized_image_save(
    nifti_writer: NIFTIWriter, parameterized_image: Image
):
    """Test saving parameterized images with NIFTIWriter."""

    for version_suffix in range(10):
        saved_path = nifti_writer.save(
            parameterized_image,
            **parameterized_image.metadata,
            version=version_suffix,
        )
    assert saved_path.exists()
    assert saved_path.suffix == ".gz"

    match nifti_writer.existing_file_mode:
        case ExistingFileMode.FAIL:
            with pytest.raises(FileExistsError):
                nifti_writer.save(
                    parameterized_image,
                    **parameterized_image.metadata,
                )
        case ExistingFileMode.OVERWRITE:
            # doing a `preview_path` should log a debug message
            # and then delete the file
            nifti_writer.preview_path(
                **parameterized_image.metadata,
            )

            assert not saved_path.exists(), "File should have been deleted..."

            saved_path = nifti_writer.save(
                parameterized_image,
                **parameterized_image.metadata,
            )
            assert saved_path.exists()
        case ExistingFileMode.SKIP:
            # this should not re-write the file
            # lets get the time of saving and hash, then save again
            saved_time = saved_path.stat().st_mtime
            saved_hash = saved_path.stat().st_size
            saved_path = nifti_writer.save(
                parameterized_image,
                **parameterized_image.metadata,
            )
            assert saved_path.exists()
            assert saved_path.stat().st_mtime == saved_time
            assert saved_path.stat().st_size == saved_hash
        case ExistingFileMode.RAISE_WARNING:
            saved_path = nifti_writer.save(
                parameterized_image,
                **parameterized_image.metadata,
            )
            assert saved_path.exists()


# some simpler tests


def test_invalid_compression():
    with pytest.raises(NiftiWriterValidationError):
        NIFTIWriter(
            root_directory=Path("."),
            filename_format="{filename}.nii.gz",
            existing_file_mode=ExistingFileMode.SKIP,
            create_dirs=True,
            sanitize_filenames=True,
            compression_level=10,
            overwrite_index=False,
        )


def test_invalid_extension():
    with pytest.raises(NiftiWriterValidationError):
        NIFTIWriter(
            root_directory=Path("."),
            filename_format="{filename}.nii.gz.invalid",
            existing_file_mode=ExistingFileMode.SKIP,
            create_dirs=True,
            sanitize_filenames=True,
            compression_level=9,
            overwrite_index=False,
        )


def test_save_numpy_array_image(temp_nifti_dir: Path):
    """Test saving a numpy array image with NIFTIWriter."""
    nifti_writer = NIFTIWriter(
        root_directory=temp_nifti_dir,
        filename_format="{PatientID}/{identifier}.nii.gz",
        existing_file_mode=ExistingFileMode.OVERWRITE,
        create_dirs=True,
        sanitize_filenames=True,
        compression_level=9,
        overwrite_index=False,
    )

    # Create a numpy array image
    np_image = np.random.rand(64, 64, 64).astype(np.float32)

    metadata = {
        "PatientID": "numpy_patient",
        "identifier": "numpy_image",
        "StudyInstanceUID": str(uuid.uuid4()),
    }

    saved_path = nifti_writer.save(np_image, **metadata)
    assert saved_path.exists()
    assert saved_path.suffix == ".gz"


def test_save_bad_image(temp_nifti_dir: Path):
    """Test saving a bad image with NIFTIWriter and expect NiftiWriterIOError."""
    nifti_writer = NIFTIWriter(
        root_directory=temp_nifti_dir,
        filename_format="{PatientID}/{identifier}.nii.gz",
        existing_file_mode=ExistingFileMode.OVERWRITE,
        create_dirs=True,
        sanitize_filenames=True,
        compression_level=9,
        overwrite_index=False,
    )

    # Create a bad image (e.g., an empty image)
    bad_image = sitk.Image()

    # create a bad image thats not sitk
    bad_not_sitk_image = pd.DataFrame()

    metadata = {
        "PatientID": "bad_patient",
        "identifier": "bad_image",
        "StudyInstanceUID": str(uuid.uuid4()),
    }

    with pytest.raises(NiftiWriterIOError):
        nifti_writer.save(bad_image, **metadata)

    with pytest.raises(NiftiWriterValidationError):
        nifti_writer.save(bad_not_sitk_image, **metadata)
