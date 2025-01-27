r"""
Parser module for extracting and validating placeholders from target patterns.

Summary
-------
This module provides functionality to parse and validate sorting patterns
with placeholders. Users can define custom regex patterns to extract keys
from their sorting patterns.

Extended Summary
----------------
The `PatternParser` class allows users to define patterns with placeholders
that can be replaced with actual values. The placeholders can be defined
using custom regex patterns, making the parser flexible for various use cases.


Examples
--------
***Setup:***

>>> import re
>>> from imgtools.dicom.sort.parser import (
...     PatternParser,
... )

***Example 1***: Suppose you want to parse a target pattern like `{Key1}-{Key2}`
and replace the placeholders with values from a dictionary:

>>> key_values = {
...     "Key1": "John",
...     "Key2": "Doe",
... }

>>> pattern = "{Key1}-{Key2}"
>>> pattern_parser = re.compile(r"\{(\w+)\}")
>>> parser = PatternParser(
...     pattern,
...     pattern_parser,
... )
>>> (
...     formatted_pattern,
...     keys,
... ) = parser.parse()
>>> print(formatted_pattern)
'%(Key1)s-%(Key2)s'
>>> print(keys)
['Key1', 'Key2']

Now you can use the formatted pattern to replace the placeholders:


>>> resolved_string = formatted_pattern % key_values
>>> print(resolved_string)
'John-Doe'

***Example 2***: Suppose you want to parse a target pattern like `%<Key1> and {Key2}`
and replace the placeholders with values from a dictionary:

>>> key_values = {
...     "Key1": "Alice",
...     "Key2": "Bob",
... }

>>> pattern = "%<Key1> and {Key2}"
>>> pattern_parser = re.compile(
...     r"%<(\w+)>|\{(\w+)\}"
... )
>>> parser = PatternParser(
...     pattern,
...     pattern_parser,
... )
>>> (
...     formatted_pattern,
...     keys,
... ) = parser.parse()
>>> print(formatted_pattern)
'%(Key1)s and %(Key2)s'
>>> print(keys)
['Key1', 'Key2']

Now you can use the formatted pattern to replace the placeholders:

>>> resolved_string = formatted_pattern % key_values
>>> print(resolved_string)
'Alice and Bob'


***Example 3***: Suppose you want to parse a target pattern like `/path/to/{Key1}/and/{Key2}`
and replace the placeholders with values from a dictionary:

>>> key_values = {
...     "Key1": "folder1",
...     "Key2": "folder2",
... }

>>> pattern = "/path/to/{Key1}/and/{Key2}"
>>> pattern_parser = re.compile(r"\{(\w+)\}")
>>> parser = PatternParser(
...     pattern,
...     pattern_parser,
... )
>>> (
...     formatted_pattern,
...     keys,
... ) = parser.parse()
>>> print(formatted_pattern)
'/path/to/%(Key1)s/and/%(Key2)s'
>>> print(keys)
['Key1', 'Key2']

Now you can use the formatted pattern to replace the placeholders:

>>> resolved_string = formatted_pattern % key_values
>>> print(resolved_string)
'/path/to/folder1/and/folder2'

"""  # noqa: A005

from typing import List, Match, Pattern, Tuple

from imgtools.dicom.sort.exceptions import InvalidPatternError


class PatternParser:
    r"""
    A helper class to parse, validate, and sanitize sorting patterns.

    This class handles:
    - Pattern parsing and validation
    - Key extraction from patterns

    Parameters
    ----------
    pattern : str
        The pattern string to parse.
    pattern_parser : Pattern, optional
        Custom regex pattern for parsing

    Attributes
    ----------
    keys : list of str
        Extracted keys from the pattern.

    Examples
    --------
    >>> import re
    >>> from imgtools.dicom.sort.parser import (
    ...     PatternParser,
    ... )

    >>> key_values = {
    ...     "Key1": "Value1",
    ...     "Key2": "Value2",
    ... }
    >>> pattern = "{Key1}-{Key2}"
    >>> pattern_parser = re.compile(r"\{(\w+)\}")
    >>> parser = PatternParser(
    ...     pattern,
    ...     pattern_parser,
    ... )
    >>> (
    ...     formatted_pattern,
    ...     keys,
    ... ) = parser.parse()
    >>> print(formatted_pattern)
    '%(Key1)s-%(Key2)s'
    >>> print(keys)
    ['Key1', 'Key2']
    >>> resolved_string = formatted_pattern % key_values
    >>> print(resolved_string)
    'Value1-Value2'
    """

    def __init__(self, pattern: str, pattern_parser: Pattern) -> None:
        assert isinstance(pattern, str) and pattern, (
            "Pattern must be a non-empty string."
        )
        self._pattern = pattern
        self._keys: List[str] = []
        assert isinstance(pattern_parser, Pattern), (
            "Pattern parser must be a regex pattern."
        )
        self._parser: Pattern = pattern_parser

    def parse(self) -> Tuple[str, List[str]]:
        """
        Parse and validate the pattern.

        Returns
        -------
        Tuple[str, List[str]]
            The formatted pattern string and a list of extracted keys.

        Raises
        ------
        InvalidPatternError
            If the pattern contains no valid placeholders or is invalid.
        """

        sanitized_pattern = self._pattern.strip()
        if not self._parser.search(sanitized_pattern):
            errmsg = f"Pattern must contain placeholders matching '{self._parser.pattern}'."
            raise InvalidPatternError(errmsg)

        formatted_pattern = self._parser.sub(
            self._replace_key, sanitized_pattern
        )
        return formatted_pattern, self._keys

    def _replace_key(self, match: Match) -> str:
        """Replace placeholders with formatted keys and store them."""
        key = match.group(1) or match.group(2)
        self._keys.append(key)
        return f"%({key})s"

    @property
    def keys(self) -> List[str]:
        """Get the list of extracted keys."""
        return self._keys
