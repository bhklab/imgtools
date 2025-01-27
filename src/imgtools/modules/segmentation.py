"""Manage and manipulate segmentation masks with multi-label support.

This module provides the `Segmentation` class and associated utilities for working
with medical image segmentation masks.
It extends the functionality of `SimpleITK.Image` to include ROI-specific operations,
label management, and metadata tracking.

Classes
-------
Segmentation
    A specialized class for handling multi-label segmentation masks. Includes
    functionality for extracting individual labels, resolving overlaps, and
    integrating with DICOM SEG metadata.

Functions
---------
accepts_segmentations(f)
    A decorator to ensure functions working on images handle `Segmentation` objects
    correctly by preserving metadata and ROI labels.

map_over_labels(segmentation, f, include_background=False, return_segmentation=True, **kwargs)
    Applies a function to each label in a segmentation mask and combines the results,
    optionally returning a new `Segmentation` object.

Notes
-----
- The `Segmentation` class tracks metadata and ROI names, enabling easier management
  of multi-label segmentation masks.
- The `generate_sparse_mask` method resolves overlapping contours by taking the
  maximum label value for each voxel, ensuring a consistent sparse representation.
- Integration with DICOM SEG metadata is supported through the `from_dicom`
  class method, which creates `Segmentation` objects from DICOM SEG files.

Examples
--------
# Creating a Segmentation object from a SimpleITK.Image
>>> seg = Segmentation(
...     image,
...     roi_indices={
...         "GTV": 1,
...         "PTV": 2,
...     },
... )

# Extracting an individual label
>>> gtv_mask = seg.get_label(name="GTV")

# Generating a sparse mask
>>> sparse_mask = seg.generate_sparse_mask(
...     verbose=True
... )

# Applying a function to each label in the segmentation
>>> def compute_statistics(label_image):
>>>     return sitk.LabelStatisticsImageFilter().Execute(label_image)

>>> stats = map_over_labels(
...     segmentation=seg,
...     f=compute_statistics,
... )
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, List, Optional, Set, Tuple, Union

import numpy as np
import SimpleITK as sitk

from imgtools.logging import logger
from imgtools.utils import array_to_image, image_to_array

from .sparsemask import SparseMask


def accepts_segmentations(f: Callable) -> Callable:
    """A decorator that ensures functions can handle `Segmentation` objects correctly.

    If the input image is an instance of `Segmentation`, the decorator preserves
    the ROI indices and raw ROI names in the output.

    This is useful when using functions that process images without losing metadata
    for the Segmentation class.

    Parameters
    ----------
    f : Callable
        The function to wrap, which processes an image.

    Returns
    -------
    Callable
        A wrapped function that preserves `Segmentation` metadata if the input
        is a `Segmentation` object.

    Examples
    --------

    Define a function that processes an image and is decorated with `@accepts_segmentations`:
    >>> @accepts_segmentations
    ... def some_processing_function(
    ...     img,
    ...     *args,
    ...     **kwargs,
    ... ) -> sitk.Image:
            # Perform some operation on the image
    ...     return img
    >>> segmentation = Segmentation(
    ...     image,
    ...     roi_indices={
    ...         "ROI1": 1,
    ...         "ROI2": 2,
    ...     },
    ... )
    >>> result = some_processing_function(segmentation)
    >>> isinstance(
    ...     result,
    ...     Segmentation,
    ... )
    True
    >>> print(result.roi_indices)
    {"ROI1": 1, "ROI2": 2}
    """

    @wraps(f)
    def wrapper(
        img: Union[sitk.Image, Segmentation],
        *args: Any,  # noqa
        **kwargs: Any,  # noqa
    ) -> Union[sitk.Image, Segmentation]:
        result = f(img, *args, **kwargs)
        if isinstance(img, Segmentation):
            result = sitk.Cast(result, sitk.sitkVectorUInt8)
            return Segmentation(
                result,
                roi_indices=img.roi_indices,
                raw_roi_names=img.raw_roi_names,
            )
        return result

    return wrapper


def map_over_labels(
    segmentation: Segmentation,
    f: Callable[[sitk.Image], sitk.Image],
    include_background: bool = False,
    return_segmentation: bool = True,
    **kwargs: Any,  # noqa
) -> Union[List[sitk.Image], Segmentation]:
    """
    Applies a function to each label in a segmentation mask.

    This function iterates over all labels in the segmentation mask, applies
    the provided function to each label individually, and optionally combines
    the results into a new `Segmentation` object.

    Parameters
    ----------
    segmentation : Segmentation
        The segmentation object containing multiple ROI labels.
    f : Callable[[sitk.Image], sitk.Image]
        A function to apply to each label in the segmentation.
    include_background : bool, optional
        If True, includes the background label (label 0) in the operation.
        Default is False.
    return_segmentation : bool, optional
        If True, combines the results into a new `Segmentation` object.
        If False, returns a list of processed labels as `sitk.Image`. Default is True.
    **kwargs : Any
        Additional keyword arguments passed to the function `f`.

    Returns
    -------
    Union[List[sitk.Image], Segmentation]
        A new `Segmentation` object if `return_segmentation` is True,
        otherwise a list of `sitk.Image` objects for each label.

    Examples
    --------
    >>> def threshold(
    ...     label_img,
    ...     threshold=0.5,
    ... ):
    ...     return sitk.BinaryThreshold(
    ...         label_img,
    ...         lowerThreshold=threshold,
    ...     )
    >>> segmentation = Segmentation(
    ...     image,
    ...     roi_indices={
    ...         "ROI1": 1,
    ...         "ROI2": 2,
    ...     },
    ... )
    >>> result = map_over_labels(
    ...     segmentation,
    ...     threshold,
    ...     threshold=0.5,
    ... )
    >>> isinstance(
    ...     result,
    ...     Segmentation,
    ... )
    True
    """
    if include_background:
        labels = range(segmentation.num_labels + 1)
    else:
        labels = range(1, segmentation.num_labels + 1)

    res = [
        f(segmentation.get_label(label=label), **kwargs) for label in labels
    ]

    if return_segmentation and isinstance(res[0], sitk.Image):
        res = [sitk.Cast(r, sitk.sitkUInt8) for r in res]
        return Segmentation(
            sitk.Compose(*res),
            roi_indices=segmentation.roi_indices,
            raw_roi_names=segmentation.raw_roi_names,
        )
    return res


class Segmentation(sitk.Image):
    def __init__(
        self,
        segmentation: sitk.Image,
        metadata: Optional[dict] = None,
        roi_indices: Optional[dict[str, int]] = None,
        existing_roi_indices: Optional[dict[str, int]] = None,
        raw_roi_names: Optional[dict[str, int]] = None,
        frame_groups: Optional[Any] = None,  # noqa
    ) -> None:
        """Initializes the Segmentation class

        Parameters
        ----------
        roi_indices
            Dictionary of {"ROI": label number}

        existing_roi_indices
            Dictionary of {"ROI": label number} of the existing ROIs

        raw_roi_names
            Dictionary of {"ROI": original contour names}

        frame_groups
            PerFrameFunctionalGroupsSequence (5200, 9230) DICOM metadata
        """
        if raw_roi_names is None:
            raw_roi_names = {}
        if metadata is None:
            metadata = {}
        super().__init__(segmentation)
        self.num_labels = self.GetNumberOfComponentsPerPixel()
        self.raw_roi_names = raw_roi_names
        self.metadata = metadata
        self.frame_groups = frame_groups

        if not roi_indices:
            self.roi_indices = {
                f"label_{i}": i for i in range(1, self.num_labels + 1)
            }
        else:
            self.roi_indices = roi_indices
            if 0 in self.roi_indices.values():
                self.roi_indices = {
                    k: v + 1 for k, v in self.roi_indices.items()
                }

        if len(self.roi_indices) != self.num_labels:
            for i in range(1, self.num_labels + 1):
                if i not in self.roi_indices.values():
                    self.roi_indices[f"label_{i}"] = i

        self.existing_roi_indices = existing_roi_indices

    # jjjermiah: this is literally NOT "from_dicom" lmao...
    # TODO: rename this to something more appropriate and add a proper from_dicom method
    @classmethod
    def from_dicom(cls, mask: sitk.Image, meta: Any) -> Segmentation:  # noqa
        # get duplicates
        label_counters = {i.SegmentLabel: 1 for i in meta.SegmentSequence}
        raw_roi_names = {}  # {i.SegmentLabel: i.SegmentNumber for n, i in meta.SegmentSequence}
        for _n, i in enumerate(meta.SegmentSequence):
            label = i.SegmentLabel
            num = i.SegmentNumber

            if label not in raw_roi_names:
                raw_roi_names[label] = num
            else:
                raw_roi_names[f"{label}_{label_counters[label]}"] = num
                label_counters[label] += 1

        frame_groups = meta.PerFrameFunctionalGroupsSequence
        return cls(
            mask, raw_roi_names=raw_roi_names, frame_groups=frame_groups
        )

    @classmethod
    def from_dicom_seg(cls, mask: sitk.Image, meta: Any) -> Segmentation:  # noqa
        """Alias for `from_dicom`."""
        return cls.from_dicom(mask=mask, meta=meta)

    def get_label(
        self,
        label: Optional[int] = None,
        name: Optional[str] = None,
        relabel: bool = False,
    ) -> sitk.Image:
        """
        Get the label image for a given label or name.

        Parameters
        ----------
        label : Optional[int]
            The label index to retrieve. If None, the name parameter must be provided.
        name : Optional[str]
            The name of the region of interest to retrieve. If None, the label parameter must be provided.
        relabel : bool
            If True, relabel the output image with the given label.

        Returns
        -------
        sitk.Image
            The label image corresponding to the given label or name.

        Raises
        ------
        ValueError
            If both label and name are None.
        """
        if label is None and name is None:
            raise ValueError("Must pass either label or name.")

        if label is None:
            # Retrieve the label index from the name
            label = self.roi_indices[name]

        if label == 0:
            # Background is stored implicitly and needs to be computed
            label_arr = sitk.GetArrayViewFromImage(self)
            # Create a binary image where background is 1 and other regions are 0
            label_img = sitk.GetImageFromArray(
                (label_arr.sum(-1) == 0).astype(np.uint8)
            )
        else:
            # Retrieve the label image for the given label index
            label_img = sitk.VectorIndexSelectionCast(self, label - 1)
            if relabel:
                # Relabel the output image with the given label
                label_img *= label

        return label_img

    def to_label_image(self) -> sitk.Image:
        """
        Convert the segmentation object to a label image.

        This method handles overlapping labels by taking the argmax of all overlaps.

        Returns
        -------
        sitk.Image
            The label image with each voxel assigned the label of the ROI with the highest value.
        """
        arr, *_ = image_to_array(self)
        label_arr = np.where(arr.sum(-1) != 0, arr.argmax(-1) + 1, 0)
        label_img = array_to_image(label_arr, reference_image=self)
        return label_img

    def __getitem__(self, idx) -> Segmentation | any:  # noqa
        res = super().__getitem__(idx)
        match res:
            case sitk.Image:
                res = Segmentation(
                    res,
                    roi_indices=self.roi_indices,
                    raw_roi_names=self.raw_roi_names,
                )
            case _:
                pass

        return res

    def __repr__(self) -> str:
        return f"<Segmentation with ROIs: {self.roi_indices!r}>"

    def generate_sparse_mask(self, verbose: bool = False) -> SparseMask:
        """
        Generate a sparse mask from the contours, taking the argmax of all overlaps

        Parameters
        ----------
        mask
            Segmentation object to build sparse mask from

        Returns
        -------
        SparseMask
            The sparse mask object.
        """
        mask_arr = np.transpose(sitk.GetArrayFromImage(self))
        for name in self.roi_indices:
            self.roi_indices[name] = self.existing_roi_indices[name]

        sparsemask_arr = np.zeros(mask_arr.shape[1:])

        if verbose:
            voxels_with_overlap = set()

        if len(mask_arr.shape) == 4:
            for i in range(mask_arr.shape[0]):
                slc = mask_arr[i, :, :, :]
                slc *= list(
                    self.roi_indices.values()
                )[
                    i
                ]  # everything is 0 or 1, so this is fine to convert filled voxels to label indices
                if verbose:
                    res = self._max_adder(sparsemask_arr, slc)
                    sparsemask_arr = res[0]
                    for e in res[1]:
                        voxels_with_overlap.add(e)
                else:
                    sparsemask_arr = np.fmax(
                        sparsemask_arr, slc
                    )  # elementwise maximum
        else:
            sparsemask_arr = mask_arr

        sparsemask = SparseMask(sparsemask_arr, self.roi_indices)

        if verbose and len(voxels_with_overlap) != 0:
            msg = (
                f"{len(voxels_with_overlap)} voxels have overlapping contours."
            )
            logger.warning(msg)
        return sparsemask

    def _max_adder(
        self, arr_1: np.ndarray, arr_2: np.ndarray
    ) -> Tuple[np.ndarray, Set[Tuple[int, int, int]]]:
        """
        Takes the maximum of two 3D arrays elementwise and returns the resulting array and a list of voxels that have overlapping contours in a set

        Parameters
        ----------
        arr_1
            First array to take maximum of
        arr_2
            Second array to take maximum of

        Returns
        -------
        Tuple[np.ndarray, Set[Tuple[int, int, int]]]
            The resulting array and a list of voxels that have overlapping contours in a set
        """
        res = np.zeros(arr_1.shape)
        overlaps = {}  # set of tuples of the coords that have overlap
        for i in range(arr_1.shape[0]):
            for j in range(arr_1.shape[1]):
                for k in range(arr_1.shape[2]):
                    if arr_1[i, j, k] != 0 and arr_2[i, j, k] != 0:
                        overlaps.add((i, j, k))
                    res[i, j, k] = max(arr_1[i, j, k], arr_2[i, j, k])
        return res, overlaps
