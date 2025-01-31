from __future__ import annotations

from dataclasses import dataclass, field

import SimpleITK as sitk

from imgtools.logging import logger

from .helper_types import Coordinate3D, Size3D


@dataclass
class Box:
    """Represents a box in 3D space.

    Attributes
    ----------
    origin : Tuple[float, float, float]
        The origin of the box.
    size : Tuple[float, float, float]
        The size of the box.
    """

    min: Coordinate3D
    max: Coordinate3D
    size: Size3D = field(init=False)

    @classmethod
    def from_tuple(
        cls, coordmin: tuple[int, int, int], coordmax: tuple[int, int, int]
    ) -> Box:
        """Creates a Box from a tuple of min and max coordinates."""
        return cls(Coordinate3D(*coordmin), Coordinate3D(*coordmax))

    def __post_init__(self) -> None:
        if (
            self.min.x > self.max.x
            or self.min.y > self.max.y
            or self.min.z > self.max.z
        ):
            msg = "The minimum coordinate must be less than the maximum coordinate."
            msg += f" Got: min={self.min}, max={self.max}"
            raise ValueError(msg)

        self.size = Size3D(
            self.max.x - self.min.x,
            self.max.y - self.min.y,
            self.max.z - self.min.z,
        )

    def __repr__(self) -> str:
        """prints out like this:

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


if __name__ == "__main__":
    from rich import print  # noqa

    basicbox = Box(Coordinate3D(0, 0, 0), Coordinate3D(10, 10, 10))

    print(basicbox)

    tupleinitbox = Box.from_tuple((0, 0, 0), (10, 10, 10))

    print(tupleinitbox)
