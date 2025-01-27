class DICOMSortError(Exception):
    """Base exception for DICOM sorting errors."""

    def __init__(
        self, message: str = "An error occurred during DICOM sorting"
    ) -> None:
        super().__init__(message)


class InvalidPatternError(DICOMSortError):
    """Raised when the target pattern is invalid."""

    def __init__(self, pattern: str | None = None) -> None:
        message = (
            f"Invalid target pattern: {pattern}"
            if pattern
            else "Invalid target pattern"
        )
        super().__init__(message)


class InvalidDICOMKeyError(DICOMSortError):
    """Raised when a DICOM key is invalid."""

    def __init__(self, key: str | None = None) -> None:
        message = f"Invalid DICOM key: {key}" if key else "Invalid DICOM key"
        super().__init__(message)


class SorterBaseError(Exception):
    """Base exception for sorting errors."""

    def __init__(
        self, message: str = "An error occurred during sorting"
    ) -> None:
        super().__init__(message)
