from typing import List, Tuple

import numpy as np
import SimpleITK as sitk

# Define type aliases for better readability
Array3D = Tuple[float, float, float]
ImageArrayMetadata = Tuple[np.ndarray, Array3D, Array3D, Array3D]


def array_to_image(
    array: np.ndarray,
    origin: Array3D = (0.0, 0.0, 0.0),
    direction: Tuple[float, ...] = (
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ),
    spacing: Array3D = (1.0, 1.0, 1.0),
    reference_image: sitk.Image = None,
) -> sitk.Image:
    """Convert a numpy array to a SimpleITK image with optional metadata.

    Parameters
    ----------
    array : np.ndarray
        The numpy array to convert.
    origin : Array3D, optional
        The origin of the image (default is (0.0, 0.0, 0.0)).
    direction : Tuple[float, ...], optional
        The direction cosines of the image (default is identity matrix).
    spacing : Array3D, optional
        The pixel spacing of the image (default is (1.0, 1.0, 1.0)).
    reference_image : sitk.Image, optional
        A reference SimpleITK image to copy metadata from (default is None).

    Returns
    -------
    sitk.Image
        The resulting SimpleITK image.
    """
    image = sitk.GetImageFromArray(array)
    if reference_image is not None:
        image.CopyInformation(reference_image)
    else:
        image.SetOrigin(origin)
        image.SetDirection(direction)
        image.SetSpacing(spacing)

    return image


def image_to_array(image: sitk.Image) -> ImageArrayMetadata:
    """Convert a SimpleITK image to a numpy array along with its metadata.

    Parameters
    ----------
    image : sitk.Image
        The SimpleITK image to convert.

    Returns
    -------
    ImageArrayMetadata
        A tuple containing:
        - The image as a numpy array.
        - The origin of the image (tuple of floats).
        - The direction cosines of the image (tuple of floats).
        - The pixel spacing of the image (tuple of floats).
    """
    origin: Array3D = image.GetOrigin()
    direction: Array3D = image.GetDirection()
    spacing: Array3D = image.GetSpacing()
    array: np.ndarray = sitk.GetArrayFromImage(image)
    return array, origin, direction, spacing


def physical_points_to_idxs(
    image: sitk.Image,
    points: List[np.ndarray],
    continuous: bool = False,
) -> List[np.ndarray]:
    """Convert physical points to image indices based on the reference image's
    geometry.

    This function uses the geometry of a SimpleITK image (origin, spacing,
    direction) to convert real-world physical coordinates into indices in the
    image grid. It optionally supports continuous indices for sub-pixel
    precision.

    Parameters
    ----------
    image : sitk.Image
        The reference SimpleITK image.
    points : List[np.ndarray]
        List of 3D physical points to transform.
    continuous : bool, optional
        If True, returns continuous indices; otherwise, returns integer indices.
        Default is False.

    Returns
    -------
    List[np.ndarray]
        A list of transformed points in image index space, reversed to match
        library conventions.

    Notes
    -----
    The following steps occur within the function:
    1. A `numpy.vectorize` function is defined to apply the transformation
       method (physical to index) to each 3D point in the input array.
    2. The transformation is applied to each set of points in the list,
       reversing the coordinate order to match the library's indexing
       convention.
    """
    # Select the appropriate transformation function based on the `continuous` parameter.
    transform = (
        image.TransformPhysicalPointToContinuousIndex
        if continuous
        else image.TransformPhysicalPointToIndex
    )

    # Step 1: Define a vectorized transformation function
    # The lambda function takes a single 3D point `x` and:
    # - Applies the selected transformation (`transform(x)`) to convert it from physical space to index space.
    # - Wraps the result into a numpy array for further processing.
    # `np.vectorize` creates a vectorized function that can process arrays of points in one call.
    # The `signature="(3)->(3)"` ensures the transformation operates on 3D points, returning 3D results.
    vectorized_transform = np.vectorize(
        lambda x: np.array(transform(x)), signature="(3)->(3)"
    )

    # Step 2: Apply the vectorized transformation to all slices of points.
    # For each 2D array `slc` in the `points` list:
    # - `vectorized_transform(slc)` applies the transformation to all points in `slc`.
    # - `[:, ::-1]` reverses the coordinate order (from (x, y, z) to (z, y, x)) to match the library's convention.
    # The result is stored as a list of numpy arrays (`t_points`), each corresponding to a transformed slice.
    t_points: List[np.ndarray] = [
        vectorized_transform(slc)[:, ::-1] for slc in points
    ]

    # Return the list of transformed points.
    return t_points


def idxs_to_physical_points(image: sitk.Image, idxs: np.ndarray) -> np.ndarray:
    """
    Converts image indices to physical points based on the reference image's
    geometry.

    Parameters
    ----------
    image : sitk.Image
        The reference SimpleITK image.
    idxs : np.ndarray
        Array of 3D indices (continuous or discrete).

    Returns
    -------
    np.ndarray
        Physical coordinates corresponding to the given indices.
    """
    continuous = np.issubdtype(idxs.dtype, np.floating)
    transform = (
        image.TransformContinuousIndexToPhysicalPoint
        if continuous
        else image.TransformIndexToPhysicalPoint
    )
    vectorized_transform = np.vectorize(
        lambda x: np.array(transform(x)), signature="(3)->(3)"
    )
    return vectorized_transform(idxs)
