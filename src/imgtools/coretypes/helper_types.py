"""
helper_types.py: Intuitive and reusable types for 3D spatial operations.

This module defines foundational types to represent and manipulate 3D spatial
concepts intuitively, focusing on clarity, usability, and alignment with
medical imaging workflows. These types aim to simplify operations like
spatial transformations, bounding box calculations, and metadata representation.

## Goals:
- **Intuitive Design:** Variable names and methods should be easy to understand
  and reflect their real-world meaning.
- **Reusability:** Types should be generic enough to apply to various spatial
  operations across domains, especially medical imaging.

## Types:
1. **Vector3D**
   - Represents a vector in 3D space with x, y, z components.
   - Includes methods for basic vector arithmetic (addition, subtraction).

2. **Size3D**
   - Represents the dimensions of a 3D object (width, height, depth).
   - Includes methods to calculate volume.

3. **Coordinate3D**
   - Represents a specific coordinate in 3D space.
   - Inherits from `Vector3D` and includes methods for addition and subtraction
     with other `Coordinate3D` or `Size3D` objects.

4. **Spacing3D**
   - Represents the spacing in 3D space.
   - Inherits from `Vector3D`.
"""

from __future__ import annotations

from dataclasses import dataclass

from typing import Iterator
import numpy as np

from typing import Generic, TypeVar, Iterator

# Define a generic type (int or float)
FloatOrInt = TypeVar("FloatOrInt", int, float)


# fmt: off
@dataclass
class Vector3D(Generic[FloatOrInt]):
    """
    Represent a vector in 3D space.

    FloatOrInt is a generic type that can be either int or float.

    Subclasses are expected to define a specific type. 

    Attributes
    ----------
    x : FloatOrInt
        X-component of the vector.
    y : FloatOrInt
        Y-component of the vector.
    z : FloatOrInt
        Z-component of the vector.

    Methods
    -------
    __add__(other):
        Add another Vector3D to this vector.
    __sub__(other):
        Subtract another Vector3D from this vector.
    __iter__():
        Iterate over the components (x, y, z).
    __getitem__(index):
        Access components via index.
    """

    x: FloatOrInt
    y: FloatOrInt
    z: FloatOrInt

    def __init__(
        self, *args: FloatOrInt | tuple[FloatOrInt, FloatOrInt, FloatOrInt]
    ) -> None:
        match args:
            case [(x, y, z)]:
                self.x, self.y, self.z = x, y, z
            case [
                int() | float() as x,
                int() | float() as y,
                int() | float() as z,
            ]:
                self.x, self.y, self.z = x, y, z
            case _:
                errmsg = (
                    f"{self.__class__.__name__} expects 3 values for x, y, z."
                    f" Got {len(args)} values for {args}."
                )
                raise ValueError(errmsg)

    def __iter__(self) -> Iterator[FloatOrInt]:
        """Allow iteration over the components."""
        return iter((self.x, self.y, self.z))

    def __getitem__(self, idx: int | str) -> FloatOrInt:
        """Access components via indexing."""
        match idx:
            case int() as index:
                return (self.x, self.y, self.z)[index]
            case str() if idx in vars(self):
                return getattr(self, idx)
            case _:
                errmsg = f"Invalid index: {idx}."
                raise IndexError(errmsg)

    def __repr__(self) -> str:
        """Return a string representation of the Vector3D."""
        cls = self.__class__.__name__
        return f"{cls}(x={self.x}, y={self.y}, z={self.z})"


class Spacing3D(Vector3D[float]):
    """Represent spacing in 3D space (float values)."""

    pass

    # No exta attributes or methods needed (yet),
    # inherits everything from Vector3D


class Coordinate3D(Vector3D[int]):
    """Represent a coordinate in 3D space (integer values)."""

    def __add__(
        self, other: Coordinate3D | Size3D | tuple
    ) -> Coordinate3D:
        """Add another Coordinate3D, Size3D, or tuple."""
        match other:
            case Coordinate3D(x, y, z):
                return Coordinate3D(self.x + x, self.y + y, self.z + z)
            case Size3D(width, height, depth):
                return Coordinate3D(self.x + width, self.y + height, self.z + depth)
            case tuple() if len(other) == 3:
                return Coordinate3D(self.x + other[0], self.y + other[1], self.z + other[2])
            case _:
                errmsg = (
                    f"Unsupported type for addition: {type(other)}."
                    " Expected Coordinate3D or Size3D."
                )
                raise TypeError(errmsg)

    def __sub__(
        self, other: Coordinate3D | Size3D | tuple
    ) -> Coordinate3D:
        """Subtract another Coordinate3D, Size3D, or tuple."""
        match other:
            case Coordinate3D(x, y, z):
                return Coordinate3D(self.x - x, self.y - y, self.z - z)
            case Size3D(width, height, depth):
                return Coordinate3D(self.x - width, self.y - height, self.z - depth)
            case tuple() if len(other) == 3:
                return Coordinate3D(self.x - other[0], self.y - other[1], self.z - other[2])
            case _:
                errmsg = (
                    f"Unsupported type for subtraction: {type(other)}."
                    " Expected Coordinate3D or Size3D."
                )
                raise TypeError(errmsg)


@dataclass
class Size3D:
    """Represent the size (width, height, depth) of a 3D object.

    Attributes
    ----------
    width :int
        The width of the 3D object.
    height :int
        The height of the 3D object.
    depth : float
        The depth of the 3D object.

    Methods
    -------
    volume:
        Calculate the volume of the 3D object.
    """

    width: int
    height: int
    depth: int

    def __init__(self, *args: int | tuple) -> None:
        match args:
            case [(width, height, depth)]:
                self.width, self.height, self.depth = width, height, depth
            case [int() as width, int() as height, int() as depth]:
                self.width, self.height, self.depth = width, height, depth
            case _:
                errmsg = (
                    f"{self.__class__.__name__} expects 3 INT values for width, height, depth."
                    f" Got {len(args)} values for {args}."
                )
                raise ValueError(errmsg)

    @property
    def volume(self) -> float:
        """Calculate the volume of the 3D object."""
        return self.width * self.height * self.depth

    def __iter__(self) -> Iterator[float]:
        """Allow iteration over the dimensions."""
        return iter((self.width, self.height, self.depth))

    def __repr__(self) -> str:
        """Return a string representation of the Size3D."""
        return f"Size3D(w={self.width}, h={self.height}, d={self.depth})"


if __name__ == "__main__":  # pragma: no cover
    # ruff : noqa
    from pathlib import Path
    from rich import print

    ########################################
    # Vector3D
    ########################################

    vector1 = Vector3D(1.0, 2.0, 3.0)

    # as tuple input
    vector2 = Vector3D((1, 2, 3))
    assert all((attr1 == attr2) for attr1, attr2 in zip(vector1, vector2))

    # iterate over the objects' attributes
    for attr in vector1:
        print(attr)

    print(vector1)

    # access object attributes via [ ]
    print(f"{vector1[0]}")
    print(f"{vector1['y']}")

    ########################################
    # Coordinate3D
    ########################################

    point = Coordinate3D(10, 20, 30)
    point2 = Coordinate3D((15, 25, 35))

    print(point)
    print(point2)

    size_tuple = (50, 60, 70)
    size = Size3D(size_tuple)
    # size2 = Size3D(10.0, 20.0, 30.0)
    # print(size, size2)
    point_plus_size = point + size_tuple

    print(f"Adding {point=} and {size_tuple=} = {point_plus_size}")
    print(f"Adding {point=} and {size=} = {point + size}")
