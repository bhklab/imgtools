"""An attempt at a cross-platform way to get the maximum path length for a given OS.

This is useful for ensuring file operations stay within safe bounds for the operating system.

Mostly to deal with the fact that Windows has a default path length of 260 characters,
and so a dicomsorter path should be validated to be less than that.
"""

import os
import platform


def os_max_path_length() -> int:
    """
    Returns the maximum file path length supported by the current operating system.

    On Windows, this function accounts for long path support if enabled (32767 characters).
    On Linux and macOS (Darwin), it retrieves the limit using os.pathconf or falls back
    to reasonable default values.

    Returns
    -------
    int
        The maximum file path length in characters for the current operating system.

    Raises
    ------
    ValueError
        If the operating system is unknown and the path length cannot be determined.
    """
    system = platform.system()
    if system == "Windows":
        # Check for long path support on Windows
        # MAX_PATH is 260, but long paths allow up to 32767 characters
        return 32767 if os.environ.get("LongPathsEnabled", "0") == "1" else 260  # noqa: SIM112
    elif system == "Linux":
        try:
            return os.pathconf("/", "PC_PATH_MAX")
        except (AttributeError, ValueError, OSError):
            return 4096  # Common default for Linux filesystems
    elif system == "Darwin":
        try:
            return os.pathconf("/", "PC_PATH_MAX")
        except (AttributeError, ValueError, OSError):
            return 1024  # Safe fallback for macOS
    else:
        errmsg = (
            "Unknown operating system. Unable to determine max path length."
        )
        raise ValueError(errmsg)


def os_max_filename_length() -> int:
    """
    Returns the maximum filename length supported by the current operating system.

    On Windows, the default maximum filename length is 255 characters.
    On Linux and macOS (Darwin), it retrieves the limit using os.pathconf or
    falls back to a safe default value.

    Returns
    -------
    int
        The maximum filename length in characters for the current operating system.

    Raises
    ------
    ValueError
        If the operating system is unknown and the filename length cannot be determined.
    """
    system = platform.system()
    if system == "Windows":
        return 255  # Windows NTFS and FAT32 typically support 255 characters
    elif system in ("Linux", "Darwin"):
        try:
            return os.pathconf("/", "PC_NAME_MAX")
        except (AttributeError, ValueError, OSError):
            return 255  # Common fallback for most filesystems
    else:
        errmsg = "Unknown operating system. Unable to determine max filename length."
        raise ValueError(errmsg)


# Example usage

if __name__ == "__main__":
    try:
        print(  # noqa: T201
            f"The maximum file path length on this system is: {os_max_path_length()} characters"
        )  # noqa: T201
    except ValueError as e:
        print(f"Error determining max path length: {e}")  # noqa: T201

    try:
        print(  # noqa: T201
            f"The maximum filename length on this system is: {os_max_filename_length()} characters"
        )
    except ValueError as e:
        print(f"Error determining max filename length: {e}")  # noqa: T201
