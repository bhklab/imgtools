from rich.highlighter import RegexHighlighter


class TagHighlighter(RegexHighlighter):
    """
    Highlights DICOM keys, forward slashes, and braces when printing with Rich.

    Attributes
    ----------
    base_style : str
            The base style for highlighted elements.
    highlights : list of str
            Regular expressions used for highlighting.

    Examples
    --------
    >>> from rich.console import (
    ...     Console,
    ... )
    >>> highlighter = TagHighlighter()
    >>> console = Console(
                    highlighter=highlighter,
                    theme=Theme(
                            {
                                    "example.Tag": "bold magenta",
                            }
                    ),
            )
    >>> console.print(
    ...     "%(PatientID)s/%(StudyID)s/{SomeValue}"
    ... )
    """

    base_style = "example."
    highlights = [
        r"%\((?P<Tag>[a-zA-Z0-9_]+)\)s",
        r"(?P<ForwardSlash>/)",
        r"(?P<Braces>\{[a-zA-Z0-9_]+\})",
    ]
