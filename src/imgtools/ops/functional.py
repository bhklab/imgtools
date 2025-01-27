from collections import namedtuple
from typing import Optional, Sequence, Tuple, Union

import numpy as np
import SimpleITK as sitk

from imgtools.modules import Segmentation

INTERPOLATORS = {
    "linear": sitk.sitkLinear,
    "nearest": sitk.sitkNearestNeighbor,
    "bspline": sitk.sitkBSpline,
}


def resample(
    image: sitk.Image,
    spacing: Union[float, Sequence[float], np.ndarray],
    interpolation: str = "linear",
    anti_alias: bool = True,
    anti_alias_sigma: Optional[float] = None,
    transform: Optional[sitk.Transform] = None,
    output_size: Optional[Sequence[float]] = None,
) -> sitk.Image:
    """Resample image to a given spacing, optionally applying a transformation.

    Parameters
    ----------
    image
        The image to be resampled.

    spacing
        The new image spacing. If float, assumes the same spacing in all
        directions. Alternatively, a sequence of floats can be passed to
        specify spacing along each dimension. Passing 0 at any position will
        keep the original spacing along that dimension (useful for in-plane
        resampling).

    interpolation, optional
        The interpolation method to use. Valid options are:
        - "linear" for bi/trilinear interpolation (default)
        - "nearest" for nearest neighbour interpolation
        - "bspline" for order-3 b-spline interpolation

    anti_alias, optional
        Whether to smooth the image with a Gaussian kernel before resampling.
        Only used when downsampling, i.e. when `spacing < image.GetSpacing()`.
        This should be used to avoid aliasing artifacts.

    anti_alias_sigma, optional
        The standard deviation of the Gaussian kernel used for anti-aliasing.

    transform, optional
        Transform to apply to input coordinates when resampling. If None,
        defaults to identity transformation.

    output_size, optional
        Size of the output image. If None, it is computed to preserve the
        whole extent of the input image.

    Returns
    -------
    sitk.Image
        The resampled image.
    """

    try:
        interpolator = INTERPOLATORS[interpolation]
    except KeyError as ke:
        msg = f"interpolator must be one of {list(INTERPOLATORS.keys())}, got {interpolation}."
        raise ValueError(msg) from ke

    original_spacing = np.array(image.GetSpacing())
    original_size = np.array(image.GetSize())

    if isinstance(spacing, (float, int)):
        new_spacing = np.repeat(spacing, len(original_spacing)).astype(
            np.float64
        )
    else:
        spacing = np.asarray(spacing)
        new_spacing = np.where(spacing == 0, original_spacing, spacing)

    if output_size is None:
        new_size = np.round(
            original_size * original_spacing / new_spacing, decimals=0
        ).astype(int)
    else:
        new_size = np.asarray(output_size)

    rif = sitk.ResampleImageFilter()
    rif.SetOutputOrigin(image.GetOrigin())
    rif.SetOutputSpacing(new_spacing)
    rif.SetOutputDirection(image.GetDirection())
    rif.SetSize(new_size.tolist())

    if transform is not None:
        rif.SetTransform(transform)

    downsample = new_spacing > original_spacing
    if downsample.any() and anti_alias:
        if not anti_alias_sigma:
            # sigma computation adapted from scikit-image
            # https://github.com/scikit-image/scikit-image/blob/master/skimage/transform/_warps.py
            anti_alias_sigma = np.maximum(
                1e-11, (original_spacing / new_spacing - 1) / 2
            )
        sigma = np.where(downsample, anti_alias_sigma, 1e-11)
        image = sitk.SmoothingRecursiveGaussian(image, sigma)

    rif.SetInterpolator(interpolator)
    resampled_image = rif.Execute(image)

    return resampled_image


def resize(
    image: sitk.Image,
    size: Union[int, Sequence[int], np.ndarray],
    interpolation: str = "linear",
    anti_alias: bool = True,
    anti_alias_sigma: Optional[float] = None,
) -> sitk.Image:
    """Resize image to a given size by resampling coordinates.

    Parameters
    ----------
    image
        The image to be resize.

    size
        The new image size. If float, assumes the same size in all directions.
        Alternatively, a sequence of floats can be passed to specify size along
        each dimension. Passing 0 at any position will keep the original
        size along that dimension.

    interpolation, optional
        The interpolation method to use. Valid options are:
        - "linear" for bi/trilinear interpolation (default)
        - "nearest" for nearest neighbour interpolation
        - "bspline" for order-3 b-spline interpolation

    anti_alias, optional
        Whether to smooth the image with a Gaussian kernel before resampling.
        Only used when downsampling, i.e. when `size < image.GetSize()`.
        This should be used to avoid aliasing artifacts.

    anti_alias_sigma, optional
        The standard deviation of the Gaussian kernel used for anti-aliasing.

    Returns
    -------
    sitk.Image
        The resized image.
    """

    original_size = np.array(image.GetSize())
    original_spacing = np.array(image.GetSpacing())

    if isinstance(size, (float, int)):
        new_size = np.repeat(size, len(original_size)).astype(np.float64)
    else:
        size = np.asarray(size)
        new_size = np.where(size == 0, original_size, size)

    new_spacing = original_spacing * original_size / new_size

    return resample(
        image,
        new_spacing,
        anti_alias=anti_alias,
        anti_alias_sigma=anti_alias_sigma,
        interpolation=interpolation,
        output_size=new_size.astype(int),
    )


def zoom(
    image: sitk.Image,
    scale_factor: Union[float, Sequence[float]],
    interpolation: str = "linear",
    anti_alias: bool = True,
    anti_alias_sigma: Optional[float] = None,
) -> sitk.Image:
    """Rescale image, preserving its spatial extent.

    The rescaled image will have the same spatial extent (size) but will be
    rescaled by `scale_factor` in each dimension. Alternatively, a separate
    scale factor for each dimension can be specified by passing a sequence
    of floats.

    Parameters
    ----------
    image
        The image to rescale.

    scale_factor
        If float, each dimension will be scaled by that factor. If tuple, each
        dimension will be scaled by the corresponding element.

    interpolation, optional
        The interpolation method to use. Valid options are:
        - "linear" for bi/trilinear interpolation (default)
        - "nearest" for nearest neighbour interpolation
        - "bspline" for order-3 b-spline interpolation

    anti_alias, optional
        Whether to smooth the image with a Gaussian kernel before resampling.
        Only used when downsampling, i.e. when `size < image.GetSize()`.
        This should be used to avoid aliasing artifacts.

    anti_alias_sigma, optional
        The standard deviation of the Gaussian kernel used for anti-aliasing.

    Returns
    -------
    sitk.Image
        The rescaled image.
    """
    dimension = image.GetDimension()

    if isinstance(scale_factor, float):
        scale_factor = (scale_factor,) * dimension

    centre_idx = np.array(image.GetSize()) / 2
    centre = image.TransformContinuousIndexToPhysicalPoint(centre_idx)

    transform = sitk.ScaleTransform(dimension, scale_factor)
    transform.SetCenter(centre)

    return resample(
        image,
        spacing=image.GetSpacing(),
        interpolation=interpolation,
        anti_alias=anti_alias,
        anti_alias_sigma=anti_alias_sigma,
        transform=transform,
        output_size=image.GetSize(),
    )


def rotate(
    image: sitk.Image,
    rotation_centre: Sequence[float],
    angles: Union[float, Sequence[float]],
    interpolation: str = "linear",
) -> sitk.Image:
    """Rotate an image around a given centre.

    Parameters
    ----------
    image
        The image to rotate.

    rotation_centre
        The centre of rotation in image coordinates.

    angles
        The angles of rotation around x, y and z axes.

    Returns
    -------
    sitk.Image
        The rotated image.
    """
    if isinstance(rotation_centre, np.ndarray):
        rotation_centre = rotation_centre.tolist()

    rotation_centre = image.TransformIndexToPhysicalPoint(rotation_centre)

    if image.GetDimension() == 2:
        rotation = sitk.Euler2DTransform(
            rotation_centre,
            angles,
            (0.0, 0.0),  # no translation
        )
    elif image.GetDimension() == 3:
        x_angle, y_angle, z_angle = angles

        rotation = sitk.Euler3DTransform(
            rotation_centre,
            x_angle,  # the angle of rotation around the x-axis, in radians -> coronal rotation
            y_angle,  # the angle of rotation around the y-axis, in radians -> saggittal rotation
            z_angle,  # the angle of rotation around the z-axis, in radians -> axial rotation
            (0.0, 0.0, 0.0),  # no translation
        )
    return resample(
        image,
        spacing=image.GetSpacing(),
        interpolation=interpolation,
        transform=rotation,
    )


def crop(
    image: sitk.Image,
    crop_centre: Sequence[float],
    size: Union[int, Sequence[int], np.ndarray],
) -> sitk.Image:
    """Crop an image to the desired size around a given centre.

    Note that the cropped image might be smaller than size in a particular
    direction if the cropping window exceeds image boundaries.

    Parameters
    ----------
    image
        The image to crop.

    crop_centre
        The centre of the cropping window in image coordinates.

    size
        The size of the cropping window along each dimension in pixels. If
        float, assumes the same size in all directions. Alternatively, a
        sequence of floats can be passed to specify size along x, y and z
        dimensions. Passing 0 at any position will keep the original size along
        that dimension.

    Returns
    -------
    sitk.Image
        The cropped image.
    """
    crop_centre = np.asarray(crop_centre, dtype=np.float64)
    original_size = np.asarray(image.GetSize())

    size = (
        np.array([size for _ in image.GetSize()])
        if isinstance(size, int)
        else np.asarray(size)
    )

    if (crop_centre < 0).any() or (crop_centre > original_size).any():
        msg = f"Crop centre outside image boundaries. Image size = {original_size}, crop centre = {crop_centre}"
        raise ValueError(msg)

    min_coords = np.clip(
        np.floor(crop_centre - size / 2).astype(np.int64), 0, original_size
    )
    min_coords = np.where(size == 0, 0, min_coords)

    max_coords = np.clip(
        np.floor(crop_centre + size / 2).astype(np.int64), 0, original_size
    )
    max_coords = np.where(size == 0, original_size, max_coords)

    min_x, min_y, min_z = min_coords
    max_x, max_y, max_z = max_coords

    return image[min_x:max_x, min_y:max_y, min_z:max_z]


# def constant_pad(image, size, cval=0.):
#     if isinstance(size, int):
#         size_lower = size_upper = [size for _ in image.GetSize()]
#     elif isinstance(size, (tuple, list, np.ndarray)):
#         if isinstance(size[0], int):
#             size_lower = size_upper = size
#         elif isinstance(size[0], (tuple, list, np.ndarray)):
#             size_lower = [s[0] for s in size]
#             size_upper = [s[1] for s in size]
#     else:
#         raise ValueError(
#             f"Size must be either int, sequence of int or sequence of sequences of ints, got {size}."
#         )
#     return sitk.ConstantPad(image, size_lower, size_upper, cval)

# def centre_on_point(image, centre):
#     pass

# def resize_by_cropping_or_padding(image, size, centre=None, cval=0.):
#     original_size = np.array(image.GetSize())
#     size = np.asarray(size)
#     centre = np.asarray(centre) if centre is not None else original_size / 2 # XXX is there any benefit to not using floor div here?

#     crop_dims = np.where(size < original_size)


def bounding_box(mask: sitk.Image, label: int = 1) -> Tuple[Tuple, Tuple]:
    """Find the axis-aligned bounding box of a region descriibed by a
    segmentation mask.

    Parameters
    ----------
    mask
        Segmentation mask describing the region of interest. Can be an image of
        type unsigned int representing a label map or `segmentation.Segmentation`.

    label, optional
        Label to use when computing bounding box if segmentation mask contains
        more than 1 labelled region.

    Returns
    -------
    tuple of tuples
        The bounding box location and size. The first tuple gives the
        coordinates of the corner closest to the origin and the second
        gives the size in pixels along each dimension.
    """

    if isinstance(mask, Segmentation):
        seg = Segmentation(mask)
        mask = seg.get_label(label=label, relabel=True)

    filter_ = sitk.LabelShapeStatisticsImageFilter()
    filter_.Execute(mask)
    bbox = filter_.GetBoundingBox(label)
    location = bbox[: len(bbox) // 2]
    size = bbox[len(bbox) // 2 :]
    return location, size


def centroid(
    mask: sitk.Image, label: int = 1, world_coordinates: bool = False
) -> tuple:
    """Find the centroid of a labelled region specified by a segmentation mask.

    Parameters
    ----------
    mask
        Segmentation mask describing the region of interest. Can be an image of
        type unsigned int representing a label map or `segmentation.Segmentation`.

    label, optional
        Label to use when computing the centroid if segmentation mask contains
        more than 1 labelled region.

    world_coordinates, optional
        If True, return centroid in world coordinates, otherwise in image
        (voxel) coordinates (default).

    Returns
    -------
    tuple
        The centroid coordinates.
    """

    if isinstance(mask, Segmentation):
        seg = Segmentation(mask)
        mask = seg.get_label(label=label, relabel=True)

    filter_ = sitk.LabelShapeStatisticsImageFilter()
    filter_.Execute(mask)
    centroid_coords = filter_.GetCentroid(label)
    if not world_coordinates:
        centroid_coords = mask.TransformPhysicalPointToIndex(centroid_coords)
    return centroid_coords


def crop_to_mask_bounding_box(
    image: sitk.Image,
    mask: sitk.Image,
    margin: Union[int, Sequence[int], np.ndarray] = 0,
    label: int = 1,
) -> Tuple[sitk.Image]:
    """Crop the image using the bounding box of a region of interest specified
    by a segmentation mask.

    Parameters
    ----------
    image
        The image to crop.

    mask
        Segmentation mask describing the region of interest. Can be an image of
        type unsigned int representing a label map or `segmentation.Segmentation`.

    margin, optional
        A margin that will be added to each dimension when cropping. If int,
        add the same margin to each dimension. A sequence of ints can also be
        passed to specify the margin separately along each dimension.

    label, optional
        Label to use when computing the centroid if segmentation mask contains
        more than 1 labelled region.

    Returns
    -------
    tuple of sitk.Image
        The cropped image and mask.
    """

    if isinstance(mask, Segmentation):
        seg = Segmentation(mask)
        mask = seg.get_label(label=label, relabel=True)

    if isinstance(margin, Sequence):
        margin = np.asarray(margin)

    bbox_location, bbox_size = bounding_box(mask, label=label)
    bbox_location, bbox_size = np.array(bbox_location), np.array(bbox_size)
    crop_size = bbox_size + margin * 2
    crop_centre = bbox_location - margin + crop_size / 2

    image = crop(image, crop_centre, crop_size)
    mask = crop(mask, crop_centre, crop_size)

    return image, mask, crop_centre


def clip_intensity(
    image: sitk.Image, lower: float, upper: float
) -> sitk.Image:
    """Clip image grey level intensities to specified range.

    The grey level intensities in the resulting image will fall in the range
    [lower, upper].

    Parameters
    ----------
    image
        The intensity image to clip.

    lower
        The lower bound on grey level intensity. Voxels with lower intensity
        will be set to this value.

    upper
        The upper bound on grey level intensity. Voxels with higer intensity
        will be set to this value.

    Returns
    -------
    sitk.Image
        The clipped intensity image.
    """
    return sitk.Clamp(image, image.GetPixelID(), lower, upper)


def window_intensity(
    image: sitk.Image, window: float, level: float
) -> sitk.Image:
    """Restrict image grey level intensities to a given window and level.

    The grey level intensities in the resulting image will fall in the range
    [level - window / 2, level + window / 2].

    Parameters
    ----------
    image
        The intensity image to window.

    window
        The width of the intensity window.

    level
        The mid-point of the intensity window.

    Returns
    -------
    sitk.Image
        The windowed intensity image.
    """
    lower = level - window / 2
    upper = level + window / 2
    return clip_intensity(image, lower, upper)


def image_statistics(
    image: sitk.Image, mask: Optional[sitk.Image] = None, label: int = 1
) -> float:
    """Compute the intensity statistics of an image.

    Returns the minimum, maximum, sum, mean, variance and standard deviation
    of image intensities.
    This function also supports computing the statistics in a specific
    region of interest if `mask` and `label` are passed.

    Parameters
    ----------
    image
        The image used to compute the statistics.

    mask, optional
        Segmentation mask specifying a region of interest used in computation.
        Can be an image of type unsigned int representing a label map or
        `segmentation.Segmentation`. Only voxels falling within the ROI will
        be considered. If None, use the whole image.

    label, optional
        Label to use when computing the statistics if segmentation mask contains
        more than 1 labelled region.

    Returns
    -------
    collections.namedtuple
        The computed intensity statistics in the image or region.
    """

    ImageStatistics = namedtuple(
        "ImageStatistics",
        [
            "minimum",
            "maximum",
            "sum",
            "mean",
            "variance",
            "standard_deviation",
        ],
    )

    if mask is not None:
        if isinstance(mask, Segmentation):
            seg = Segmentation(mask)
            mask = seg.get_label(label=label, relabel=True)

        filter_ = sitk.LabelStatisticsImageFilter()
        filter_.Execute(image, mask)
        result = ImageStatistics(
            minimum=filter_.GetMinimum(label),
            maximum=filter_.GetMaximum(label),
            sum=filter_.GetSum(label),
            mean=filter_.GetMean(label),
            variance=filter_.GetVariance(label),
            standard_deviation=filter_.GetSigma(label),
        )
    else:
        filter_ = sitk.StatisticsImageFilter()
        filter_.Execute(image)
        result = ImageStatistics(
            minimum=filter_.GetMinimum(),
            maximum=filter_.GetMaximum(),
            sum=filter_.GetSum(),
            mean=filter_.GetMean(),
            variance=filter_.GetVariance(),
            standard_deviation=filter_.GetSigma(),
        )

    return result


def standard_scale(
    image: sitk.Image,
    mask: Optional[sitk.Image] = None,
    rescale_mean: Optional[float] = None,
    rescale_std: Optional[float] = None,
    label: int = 1,
) -> sitk.Image:
    """Rescale image intensities by subtracting the mean and dividing by
       standard deviation.

    If `rescale_mean` and `rescale_std` are None, image mean and standard
    deviation will be used, i.e. the resulting image intensities will have
    0 mean and unit variance. Alternatively, a specific mean and standard
    deviation can be passed to e.g. standardize a whole dataset of images.
    If a segmentation mask is passed, only the voxels falling within the mask
    will be considered when computing the statistics. However, the whole image
    will still be normalized using the computed values.

    Parameters
    ----------
    image
        The image to rescale.

    mask, optional
        Segmentation mask specifying a region of interest used in computation.
        Can be an image of type unsigned int representing a label map or
        `segmentation.Segmentation`. Only voxels falling within the ROI will
        be considered. If None, use the whole image.

    rescale_mean, optional
        The mean intensity used in rescaling. If None, image mean will be used.

    rescale_std, optional
        The standard deviation used in rescaling. If None, image standard
        deviation will be used.

    label, optional
        Label to use when computing the mean and standard deviation if
        segmentation mask contains more than 1 labelled region.

    Returns
    -------
    sitk.Image
        The rescaled image.
    """
    if not rescale_mean or not rescale_std:
        statistics = image_statistics(image, mask, label)
        rescale_mean = statistics.mean
        rescale_std = statistics.standard_deviation
    return (image - rescale_mean) / rescale_std


def min_max_scale(
    image: sitk.Image, minimum: float = 0.0, maximum: float = 1.0
) -> sitk.Image:
    """Rescale image intensities to a given minimum and maximum.

    Applies a linear transformation to image intensities such that the minimum
    and maximum intensity values in the resulting image are equal to minimum
    (default 0) and maximum (default 1) respectively.

    Parameters
    ----------
    image
        The image to rescale.

    minimum, optional
        The minimum intensity in the rescaled image.

    maximum, optional
        The maximum intensity in the rescaled image.

    Returns
    -------
    sitk.Image
        The rescaled image.
    """
    return sitk.RescaleIntensity(image, minimum, maximum)
