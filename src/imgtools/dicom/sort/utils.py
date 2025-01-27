"""DICOM Sorting Utilities.

This module provides utilities for sanitizing filenames, truncating UIDs,
and reading specific tags from DICOM files.

Functions
---------
sanitize_file_name(filename: str) -> str
    Sanitize filenames by replacing potentially dangerous characters.
truncate_uid(uid: str, last_digits: int = 5) -> str
    Truncate a UID to the last n characters.
read_tags(file: Path, tags: list[str], truncate: bool = True, sanitize: bool = True) -> dict[str, str]
    Read specified tags from a DICOM file.

Examples
--------
Sanitize a filename:
    >>> sanitize_file_name("test<>file:/name.dcm")
    'test_file_name.dcm'

Truncate a UID:
    >>> truncate_uid(
    ...     "1.2.840.10008.1.2.1",
    ...     last_digits=5,
    ... )
    '.1.2.1'

Read tags from a DICOM file:
    >>> from pathlib import (
    ...     Path,
    ... )
    >>> tags = [
    ...     "PatientID",
    ...     "StudyInstanceUID",
    ... ]
    >>> read_tags(
    ...     Path("sample.dcm"),
    ...     tags,
    ... )
    {'PatientID': '12345', 'StudyInstanceUID': '1.2.3.4.5'}
"""

import re
from pathlib import Path
from typing import Dict, List, Optional

from pydicom import dcmread
from pydicom.errors import InvalidDicomError


def sanitize_file_name(filename: str) -> str:
    """
    Sanitize the file name by replacing potentially dangerous characters.

    Replaces disallowed characters with underscores, converts spaces to
    underscores, and removes subsequent underscores.

    Parameters
    ----------
    filename : str
        The input file name to sanitize.

    Returns
    -------
    str
        The sanitized file name.

    Examples
    --------
    >>> sanitize_file_name("test<>file:/name.dcm")
    'test_file_name.dcm'
    >>> sanitize_file_name("my file name.dcm")
    'my_file_name.dcm'
    """
    assert filename is not None
    assert isinstance(filename, str)

    disallowed_characters_pattern = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
    sanitized_name = disallowed_characters_pattern.sub("_", filename)
    sanitized_name = sanitized_name.replace(" ", "_")
    sanitized_name = re.sub(r"(_{2,})", "_", sanitized_name)
    return sanitized_name


def truncate_uid(uid: str, last_digits: int = 5) -> str:
    """
    Truncate the UID to the last n characters (including periods and underscores).

    If the UID is shorter than `last_digits`, the entire UID is returned.

    Parameters
    ----------
    uid : str
        The UID string to truncate.
    last_digits : int, optional
        The number of characters to keep at the end of the UID (default is 5).

    Returns
    -------
    str
        The truncated UID string.

    Examples
    --------
    >>> truncate_uid(
    ...     "1.2.840.10008.1.2.1",
    ...     last_digits=5,
    ... )
    '.1.2.1'
    >>> truncate_uid(
    ...     "12345",
    ...     last_digits=10,
    ... )
    '12345'
    """
    assert uid is not None
    assert isinstance(uid, str)
    assert isinstance(last_digits, int)
    if last_digits >= len(uid) or last_digits <= 0:
        return uid

    return uid[-last_digits:]


def read_tags(
    file: Path,
    tags: List[str],
    truncate: bool = True,
    sanitize: bool = True,
    default: Optional[str] = "",
) -> Dict[str, str]:
    """
    Read the specified tags from a DICOM file.

    Reads a set of tags from a DICOM file and applies optional sanitization
    and truncation for UIDs. Handles cases where specific tags may be missing.

    Parameters
    ----------
    file : Path
                                    Path to the DICOM file.
    tags : list of str
                                    List of DICOM tags to read.
    truncate : bool, optional
                                    If True, truncate UIDs to the last 5 characters (default is True).
    sanitize : bool, optional
                                    If True, sanitize tag values to remove disallowed characters
                                    (default is True).

    Returns
    -------
    dict of str : str
                                    A dictionary mapping tags to their values.

    Raises
    ------
    TypeError
                                    If there is a type error while reading the DICOM file.
    InvalidDicomError
                                    If the file is not a valid DICOM file.
    ValueError
                                    If there is a value error while reading the file.

    Notes
    -----
    For RTSTRUCT files, missing 'InstanceNumber' tags default to '1'.

    Examples
    --------
    Read tags from a valid DICOM file with truncation:
    >>> from pathlib import (
    ...     Path,
    ... )
    >>> read_tags(
    ...     Path("sample.dcm"),
    ...     [
    ...         "PatientID",
    ...         "StudyInstanceUID",
    ...     ],
    ... )
    {'PatientID': '12345', 'StudyInstanceUID': '1.2.3.4.5'}

    Read tags without truncating UIDs:
    >>> read_tags(
    ...     Path("sample.dcm"),
    ...     [
    ...         "PatientID",
    ...         "StudyInstanceUID",
    ...     ],
    ...     truncate=False,
    ... )
    {'PatientID': '12345', 'StudyInstanceUID': '1.2.840.10008.1.2.1'}

    Handle missing tags:
    >>> read_tags(
    ...     Path("sample.dcm"),
    ...     ["NonexistentTag"],
    ... )
    [warn] No value for tag: NonexistentTag in file: sample.dcm
    {'NonexistentTag': 'UNKNOWN'}
    """
    assert isinstance(file, Path)
    assert (
        isinstance(tags, list)
        and all(isinstance(tag, str) for tag in tags)
        and tags is not None
    )

    try:
        dicom = dcmread(file, specific_tags=tags, stop_before_pixels=True)
    except FileNotFoundError as fnfe:
        errmsg = f"File not found: {file}"
        raise FileNotFoundError(errmsg) from fnfe
    except InvalidDicomError as ide:
        errmsg = f"Invalid DICOM file: {file}"
        raise InvalidDicomError(errmsg) from ide
    except ValueError as ve:
        errmsg = f"Value error reading DICOM file: {file}"
        raise ValueError(errmsg) from ve

    result = {}
    # is_rtstruct = dicom.get('Modality') == 'RTSTRUCT' if 'InstanceNumber' in tags else False

    for tag in tags:
        value = str(dicom.get(tag, default=default))

        if truncate and tag.endswith("UID"):
            value = truncate_uid(value)

        if sanitize:
            value = sanitize_file_name(value)

        result[tag] = value
    return result
