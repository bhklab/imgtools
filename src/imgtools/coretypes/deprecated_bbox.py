"""
OLD BBOX CODE TO GET INSPIRATION FROM
"""

from __future__ import annotations

from dataclasses import dataclass, field

import SimpleITK as sitk

from imgtools.logging import logger


@dataclass
class Point3D:
    """Represent a point in 3D space."""

    x: int
    y: int
    z: int

    @property
    def as_tuple(self) -> tuple[int, int, int]:
        return self.x, self.y, self.z

    def __add__(self, other: Point3D) -> Point3D:
        return Point3D(
            x=self.x + other.x, y=self.y + other.y, z=self.z + other.z
        )

    def __sub__(self, other: Point3D) -> Point3D:
        return Point3D(
            x=self.x - other.x, y=self.y - other.y, z=self.z - other.z
        )


@dataclass
class Size3D(Point3D):
    """Represent the size of a 3D object using its width, height, and depth."""

    pass


@dataclass
class Coordinate(Point3D):
    """Represent a coordinate in 3D space."""

    pass


@dataclass
class Centroid(Coordinate):
    """Represent the centroid of a region in 3D space.

    A centroid is simply a coordinate in 3D space that represents
    the center of mass of a region in an image. It is represented
    by its x, y, and z coordinates.

    Attributes
    ----------
    x : int
    y : int
    z : int
    """

    pass


class BoundingBoxError(Exception):
    pass


def calculate_image_boundaries(image: sitk.Image) -> BoundingBox:
    """
    Calculate the physical coordinate boundaries of a SimpleITK image.

    Parameters
    ----------
    image : sitk.Image
            The input SimpleITK image.

    Returns
    -------
    BoundingBox

    Examples
    --------
    >>> calculate_image_boundaries(image)
    BoundingBox(min=Coordinate(x=0, y=0, z=0), max=Coordinate(x=512, y=512, z=512))
    """

    size = image.GetSize()
    origin = image.GetOrigin()

    min_coord = Coordinate(
        x=origin[0],
        y=origin[1],
        z=origin[2],
    )
    max_coord = Coordinate(
        x=origin[0] + size[0],
        y=origin[1] + size[1],
        z=origin[2] + size[2],
    )

    return BoundingBox(min=min_coord, max=max_coord)


@dataclass
class BoundingBox:
    """
    Represents a rectangular region in a coordinate space.

    Attributes
    ----------
    min : Coordinate
        The minimum coordinate (bottom-left corner) of the bounding box.
    max : Coordinate
        The maximum coordinate (top-right corner) of the bounding box.
    """

    min: Coordinate
    max: Coordinate
    size: Size3D = field(init=False)

    def __post_init__(self):
        if (
            self.min.x > self.max.x
            or self.min.y > self.max.y
            or self.min.z > self.max.z
        ):
            msg = "The minimum coordinate must be less than the maximum coordinate."
            msg += f" Got: min={self.min.as_tuple}, max={self.max.as_tuple}"
            raise ValueError(msg)

        self.size = Size3D(
            x=self.max.x - self.min.x,
            y=self.max.y - self.min.y,
            z=self.max.z - self.min.z,
        )

    def __repr__(self):
        """
        prints out like this:

        BoundingBox(
            min=Coordinate(x=223, y=229, z=57),
            max=Coordinate(x=303, y=299, z=87)
            size=(80, 70, 30)
        )
        """
        return (
            f"{self.__class__.__name__}(\n"
            f"\tmin={self.min},\n"
            f"\tmax={self.max}\n"
            f"\tsize={self.size}\n"
            f")"
        )

    @classmethod
    def from_centroid(
        cls, mask: sitk.Image, size: Size3D, label: int | None = None
    ) -> BoundingBox:
        """Create a bounding box around the centroid of a mask with a given size.

        Parameters
        ----------
        mask : sitk.Image
            The binary mask image.
        size : Size3D
            The size of the bounding box.
        label : int | None
            The label of the region to find the bounding box for.
            if None, the label is determined automatically. Default is None.

        Returns
        -------
        BoundingBox
            The bounding box coordinates as a BoundingBox object.

        Examples
        --------
        >>> size = Size3D(x=5, y=5, z=5)
        >>> find_bbox_from_centroid(mask, size, label=1)
        BoundingBox(min=Coordinate(x=7, y=7, z=7), max=Coordinate(x=12, y=12, z=12))
        """
        if isinstance(size, Size3D):
            pass
        elif isinstance(size, tuple):
            size = Size3D(*size)
        else:
            msg = "Size must be a Size3D object or a tuple of (x, y, z) integers."
            raise ValueError(msg)

        # label = label or getROIVoxelLabel(mask)

        mask_uint = sitk.Cast(mask, sitk.sitkUInt8)
        stats = sitk.LabelShapeStatisticsImageFilter()
        stats.Execute(mask_uint)

        if not stats.HasLabel(label):
            raise ValueError(
                f"The mask does not contain any labeled regions with label {label}."
            )

        centroid_coords = stats.GetCentroid(label)
        centroid_idx = mask.TransformPhysicalPointToIndex(centroid_coords)
        centroid = Centroid(
            x=centroid_idx[0], y=centroid_idx[1], z=centroid_idx[2]
        )

        min_coord = Coordinate(
            x=centroid.x - size.x // 2,
            y=centroid.y - size.y // 2,
            z=centroid.z - size.z // 2,
        )
        max_coord = Coordinate(
            x=centroid.x + size.x // 2,
            y=centroid.y + size.y // 2,
            z=centroid.z + size.z // 2,
        )
        return cls(min_coord, max_coord)

    @classmethod
    def from_mask(
        cls, mask: sitk.Image, min_dim_size: int = 4, pad: int = 0
    ) -> BoundingBox:
        """Find the bounding box of a given mask image.

        Parameters
        ----------
        mask : sitk.Image
            The input mask image.
        min_dim_size : int
            Minimum size of bounding box along each dimension. Default is 4.

        Returns
        -------
        BoundingBox
            The bounding box coordinates as a BoundingBox object.

        Examples
        --------
        >>> find_bbox(mask, min_dim_size=4)
        BoundingBox(min=Coordinate(x=0, y=0, z=0), max=Coordinate(x=4, y=4, z=4))
        """

        mask_uint = sitk.Cast(mask, sitk.sitkUInt8)
        stats = sitk.LabelShapeStatisticsImageFilter()
        stats.Execute(mask_uint)
        xstart, ystart, zstart, xsize, ysize, zsize = stats.GetBoundingBox(1)

        # Ensure minimum size of 4 pixels along each dimension
        xsize = max(xsize, min_dim_size)
        ysize = max(ysize, min_dim_size)
        zsize = max(zsize, min_dim_size)

        min_coord = Coordinate(x=xstart, y=ystart, z=zstart)
        max_coord = Coordinate(
            x=xstart + xsize, y=ystart + ysize, z=zstart + zsize
        )

        if pad == 0:
            return cls(min_coord, max_coord)

        return cls(min_coord, max_coord).pad(padding=pad)

    def crop_image(self, image: sitk.Image) -> sitk.Image:
        """Crop the input image to the bounding box.

        Parameters
        ----------
        image : sitk.Image
            The input image to crop.

        Returns
        -------
        sitk.Image
            The cropped image.
        """
        try:
            cropped_image = sitk.RegionOfInterest(
                image,
                self.size.as_tuple,
                self.min.as_tuple,
            )
        except RuntimeError:
            # this is probably due to the bounding box being outside the image
            # try to crop the image to the largest possible region
            msg = f"The bounding box {self} is outside the image size {calculate_image_boundaries(image)} "
            msg += "Chances are, one of the max values are outside the image size. "
            msg += f"max={self.max.as_tuple} and image={image.GetSize()}"
            logger.warning(msg)

            new_max_coord = Coordinate(
                x=min(self.max.x, image.GetSize()[0]),
                y=min(self.max.y, image.GetSize()[1]),
                z=min(self.max.z, image.GetSize()[2]),
            )
            # bbox = BoundingBox(min=self.min, max=new_max_coord)
            # not a fan of mutating the object, but this adjustment
            # would be required for every use of the bounding box
            # so its better just to mutate this instance and let the fixed version be used everytime
            self.max = new_max_coord

            # re-run post_init to validate & update the size
            self.__post_init__()

            try:
                cropped_image = sitk.RegionOfInterest(
                    image,
                    self.size.as_tuple,
                    self.min.as_tuple,
                )
            except RuntimeError as e:
                msg = "Failed to crop the image to the bounding box.\n"
                msg += f"Image size: {image.GetSize()}. \n"
                msg += f"Bounding box: {self}\n"
                msg += "Failed retry crop to the largest possible region."
                msg += f" New bounding box: {self}"
                logger.error(msg)
                raise BoundingBoxError(msg) from e
        return cropped_image

    def crop_image_and_mask(
        self,
        image: sitk.Image,
        mask: sitk.Image,
    ) -> tuple[sitk.Image, sitk.Image]:
        """Crop the input image and mask to the bounding box.

        Parameters
        ----------
        image : sitk.Image
            The input image to crop.
        mask : sitk.Image
            The input mask to crop. Assumes they are aligned with the image.

        Returns
        -------
        tuple[sitk.Image, sitk.Image]
            The cropped image and mask.
        """
        return self.crop_image(image), self.crop_image(mask)

    def pad(self, padding: int) -> BoundingBox:
        """
        Expand the bounding box by a specified padding value in all directions.

        Parameters
        ----------
        padding : int
            The padding value to expand the bounding box.

        Returns
        -------
        BoundingBox
            The expanded bounding box.
        """
        if padding == 0:
            return self

        padded_min = Coordinate(
            x=self.min.x - padding,
            y=self.min.y - padding,
            z=self.min.z - padding,
        )
        padded_max = Coordinate(
            x=self.max.x + padding,
            y=self.max.y + padding,
            z=self.max.z + padding,
        )
        return BoundingBox(min=padded_min, max=padded_max)

    def expand_to_cube(self) -> BoundingBox:
        """Convert the bounding box to a cube by making the size equal along all dimensions.

        This is done by finding which dimension is the largest and then expanding the
        bounding box in the other dimensions to make it a cube.

        Returns
        -------
        BoundingBox
            The bounding box converted to a cube.
        """
        max_size = max(self.size.as_tuple)

        extra_x_half = (max_size - self.size.x) // 2
        extra_y_half = (max_size - self.size.y) // 2
        extra_z_half = (max_size - self.size.z) // 2

        min_coord = Coordinate(
            x=self.min.x - extra_x_half,
            y=self.min.y - extra_y_half,
            z=self.min.z - extra_z_half,
        )

        max_coord = Coordinate(
            x=self.max.x + extra_x_half,
            y=self.max.y + extra_y_half,
            z=self.max.z + extra_z_half,
        )

        # if any of the min values are negative, set them to 0, and add the difference to the max values
        if min_coord.x < 0:
            diff = abs(min_coord.x)
            min_coord.x = 0
            max_coord.x += diff

        if min_coord.y < 0:
            diff = abs(min_coord.y)
            min_coord.y = 0
            max_coord.y += diff

        if min_coord.z < 0:
            diff = abs(min_coord.z)
            min_coord.z = 0
            max_coord.z += diff

        return BoundingBox(min=min_coord, max=max_coord)


if __name__ == "__main__":
    from rich import print

    # Load example images
    seg_image = sitk.ReadImage(
        "/home/bioinf/bhklab/radiomics/readii-negative-controls/rawdata/HEAD-NECK-RADIOMICS-HN1/images/niftis/SubjectID-100_HN1339/RTSTRUCT_11267_GTV.nii.gz"
    )
    ct_image = sitk.ReadImage(
        "/home/bioinf/bhklab/radiomics/readii-negative-controls/rawdata/HEAD-NECK-RADIOMICS-HN1/images/niftis/SubjectID-100_HN1339/CT_82918_original.nii.gz"
    )
    stats = sitk.LabelShapeStatisticsImageFilter()
    stats.Execute(ct_image)

    print(f"{ct_image.GetSize()=}")
    print(f"{ct_image.GetDirection()=}")
    print(f"{ct_image.GetSpacing()=}\n")

    print(f"{ct_image.GetOrigin()=}")
    print(f"{ct_image.TransformPhysicalPointToContinuousIndex(ct_image.GetOrigin())=}")
    print(f"{ct_image.TransformPhysicalPointToIndex(ct_image.GetOrigin())=}\n")

    print(f"{stats.GetBoundingBox(1)=}")
    print(f"{stats.GetCentroid(1)=}")
    print(f"{ct_image.TransformPhysicalPointToContinuousIndex(stats.GetCentroid(1))=}")
    print(f"{ct_image.TransformPhysicalPointToIndex(stats.GetCentroid(1))=}")

    # bbox = BoundingBox.bbox_from_mask(mask=seg_image)

    # print(bbox)

    # cropped_ct_image, cropped_seg_image = bbox.crop_image_and_mask(ct_image, seg_image)

    # cropped_ct_image, cropped_seg_image = (
    #     BoundingBox.bbox_from_mask(mask=seg_image)
    #     .pad(padding=5)
    #     .crop_image_and_mask(ct_image, seg_image)
    # )
