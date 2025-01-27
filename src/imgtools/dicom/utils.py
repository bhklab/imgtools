"""
DICOM Utilities.

This module provides utilities for:
- Searching and validating DICOM files in directories.
- Looking up DICOM tags by keywords with optional hexadecimal formatting.
- Checking the existence of DICOM tags.
- Finding similar DICOM tags.
"""

import difflib
import functools
from itertools import islice
from pathlib import Path
from typing import FrozenSet, List, Optional

from pydicom._dicom_dict import DicomDictionary
from pydicom.datadict import dictionary_has_tag, tag_for_keyword
from pydicom.misc import is_dicom

from imgtools.logging import logger


def _is_valid_dicom(file: Path, check_header: bool) -> bool:
    """
    Notes
    -----
    Validation includes:
    - Ensuring the file is a valid DICOM file (if `check_header` is True).
    - Ensuring the file exists and is not a directory (if `check_header` is False).
    """
    if check_header:
        return is_dicom(file) and file.is_file()
    return file.is_file()


def find_dicoms(
    directory: Path,
    recursive: bool,
    check_header: bool,
    extension: Optional[str] = None,
    limit: Optional[int] = None,
    search_input: Optional[List[str]] = None,
) -> List[Path]:
    """Locate DICOM files in a specified directory.

    This function scans a directory for files matching the specified extension
    and validates them as DICOM files based on the provided options. It supports
    recursive search and optional header validation to confirm file validity.

    Parameters
    ----------
    directory : Path
        The directory in which to search for DICOM files.
    recursive : bool
        Whether to include subdirectories in the search
    check_header : bool
        Whether to validate files by checking for a valid DICOM header.
            - If `True`, perform DICOM header validation (slower but more accurate).
            - If `False`, skip header validation and rely on extension.

    extension : str, optional
        File extension to search for (e.g., "dcm"). If `None`, consider all files
        regardless of extension.

    limit : int, optional
        Maximum number of DICOM files to return. If `None`, return all found files.

    Returns
    -------
    List[Path]
        A list of valid DICOM file paths found in the directory.

    Notes
    -----
    - If `check_header` is enabled, the function checks each file for a valid
        DICOM header, which may slow down the search process.

    Examples
    --------
    Setup

    >>> from pathlib import (
    ...     Path,
    ... )
    >>> from imgtools.dicom.utils import (
    ...     find_dicoms,
    ... )

    Find DICOM files recursively without header validation:

    >>> find_dicoms(
    ...     Path("/data"),
    ...     recursive=True,
    ...     check_header=False,
    ... )
    [PosixPath('/data/scan1.dcm'), PosixPath('/data/subdir/scan2.dcm'), PosixPath('/data/subdir/scan3.dcm')]

    Suppose that `scan3.dcm` is not a valid DICOM file. Find DICOM files with header validation:

    >>> find_dicoms(
    ...     Path("/data"),
    ...     recursive=True,
    ...     check_header=True,
    ... )
    [PosixPath('/data/scan1.dcm'), PosixPath('/data/subdir/scan2.dcm')]

    Find DICOM files without recursion:
    >>> find_dicoms(
    ...     Path("/data"),
    ...     recursive=False,
    ...     check_header=False,
    ... )
    [PosixPath('/data/scan1.dcm')]

    Find DICOM files with a specific extension:
    >>> find_dicoms(
    ...     Path("/data"),
    ...     recursive=True,
    ...     check_header=False,
    ...     extension="dcm",
    ... )
    [PosixPath('/data/scan1.dcm'), PosixPath('/data/subdir/scan2.dcm')]

    Find DICOM files with a search input:
    >>> find_dicoms(
    ...     Path("/data"),
    ...     recursive=True,
    ...     check_header=False,
    ...     search_input=[
    ...         "scan1",
    ...         "scan2",
    ...     ],
    ... )
    [PosixPath('/data/scan1.dcm'), PosixPath('/data/subdir/scan2.dcm')]

    Find DICOM files with a limit:
    >>> find_dicoms(
    ...     Path("/data"),
    ...     recursive=True,
    ...     check_header=False,
    ...     limit=1,
    ... )
    [PosixPath('/data/scan1.dcm')]

    Find DICOM files with all options:
    >>> find_dicoms(
    ...     Path("/data"),
    ...     recursive=True,
    ...     check_header=True,
    ...     extension="dcm",
    ...     limit=2,
    ...     search_input=["scan"],
    ... )
    [PosixPath('/data/scan1.dcm'), PosixPath('/data/subdir/scan2.dcm')]
    """
    pattern = f"*.{extension}" if extension else "*"

    glob_method = directory.rglob if recursive else directory.glob

    logger.debug(
        "Looking for DICOM files",
        directory=directory,
        recursive=recursive,
        search_pattern=pattern,
        check_header=check_header,
        limit=limit,
        search_input=search_input,
    )

    files = (
        file.absolute()
        for file in glob_method(pattern)
        if (
            not search_input
            or all(term in str(file.as_posix()) for term in search_input)
        )
        and _is_valid_dicom(file, check_header)
    )

    return list(islice(files, limit)) if limit else list(files)


###############################################################################
# DICOM TAG UTILITIES
###############################################################################

ALL_DICOM_TAGS: FrozenSet[str] = frozenset(
    value[4] for value in DicomDictionary.values()
)


@functools.lru_cache(maxsize=1024)
def lookup_tag(keyword: str, hex_format: bool = False) -> Optional[str]:
    """
    Lookup the tag for a given DICOM keyword.

    Parameters
    ----------
    keyword : str
                    The DICOM keyword to look up.
    hex_format : bool, optional
                    If True, return the tag in hexadecimal format (default is False).

    Returns
    -------
    str or None
                    The DICOM tag as a string, or None if the keyword is invalid.

    Examples
    --------

    Lookup a DICOM tag in decimal format:

    >>> lookup_tag("PatientID")
    '1048608'

    Lookup a DICOM tag in hexadecimal format:

    >>> lookup_tag(
    ...     "PatientID",
    ...     hex_format=True,
    ... )
    '0x100020'
    """
    if (tag := tag_for_keyword(keyword)) is None:
        return None
    return f"0x{tag:X}" if hex_format else str(tag)


@functools.lru_cache(maxsize=1024)
def tag_exists(keyword: str) -> bool:
    """Boolean check if a DICOM tag exists for a given keyword.

    Parameters
    ----------
    keyword : str
                    The DICOM keyword to check.

    Returns
    -------
    bool
                    True if the tag exists, False otherwise.

    Examples
    --------

    >>> tag_exists("PatientID")
    True

    >>> tag_exists("InvalidKeyword")
    False
    """
    return dictionary_has_tag(keyword)


@functools.lru_cache(maxsize=1024)
def similar_tags(
    keyword: str, n: int = 3, threshold: float = 0.6
) -> List[str]:
    """Find similar DICOM tags for a given keyword.

    Useful for User Interface to suggest similar tags based on a misspelled keyword.

    Parameters
    ----------
    keyword : str
                    The keyword to search for similar tags.
    n : int, optional
                    Maximum number of similar tags to return (default is 3).
    threshold : float, optional
                    Minimum similarity ratio (default is 0.6).

    Returns
    -------
    List[str]
                    A list of up to `n` similar DICOM tags.

    Examples
    --------
    Find similar tags for a misspelled keyword:

    >>> similar_tags("PatinetID")
    ['PatientID', 'PatientName', 'PatientBirthDate']

    Adjust the number of results and threshold:

    >>> similar_tags(
    ...     "PatinetID",
    ...     n=5,
    ...     threshold=0.7,
    ... )
    ['PatientID', 'PatientName']
    """
    return difflib.get_close_matches(keyword, ALL_DICOM_TAGS, n, threshold)
