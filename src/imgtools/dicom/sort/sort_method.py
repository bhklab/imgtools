"""
File Handling Utility.

This module provides functionality to handle files with different actions
such as moving, copying, creating symbolic links, and creating hard links.

Classes
-------
FileAction(Enum)
    Enum for file actions including MOVE, COPY, SYMLINK, and HARDLINK.

Functions
---------
handle_file(source_path: Path, resolved_path: Path, action: FileAction, overwrite: bool) -> None
    Perform specified file operations (move, copy, symlink, hardlink) on a file.

Notes
-----
Symlinks vs. Hardlinks:
- **Symlinks (Symbolic Links)**:
    A symbolic link is a shortcut or reference to another file. It creates a new
    file that points to the target file but does not duplicate the file's data.
    If the target file is moved or deleted, the symlink becomes invalid.
    Example: `ln -s target symlink`

- **Hardlinks**:
    A hard link is an additional reference to the same data on the disk. Both the
    original file and the hard link share the same inode, meaning they are
    indistinguishable. Deleting the original file does not affect the hard link,
    and vice versa.
    Example: `ln target hardlink`

Examples
--------
Move a file:
    >>> from pathlib import (
    ...     Path,
    ... )
    >>> handle_file(
    ...     Path("source.txt"),
    ...     Path("destination.txt"),
    ...     action=FileAction.MOVE,
    ... )

Create a symlink:
    >>> handle_file(
    ...     Path("source.txt"),
    ...     Path("symlink.txt"),
    ...     action=FileAction.SYMLINK,
    ... )

Copy a file:
    >>> handle_file(
    ...     Path("source.txt"),
    ...     Path("copy.txt"),
    ...     action=FileAction.COPY,
    ...     overwrite=True,
    ... )
"""

import shutil
from enum import Enum
from pathlib import Path
from typing import List, Type


class FileAction(Enum):
    MOVE = "move"
    COPY = "copy"
    SYMLINK = "symlink"
    HARDLINK = "hardlink"

    def handle(self, source_path: Path, resolved_path: Path) -> None:
        match self:
            case FileAction.MOVE:
                self.move_file(source_path, resolved_path)
            case FileAction.COPY:
                self.copy_file(source_path, resolved_path)
            case FileAction.SYMLINK:
                self.create_symlink(source_path, resolved_path)
            case FileAction.HARDLINK:
                self.create_hardlink(source_path, resolved_path)

    def move_file(self, source_path: Path, resolved_path: Path) -> None:
        source_path.rename(resolved_path)

    def copy_file(self, source_path: Path, resolved_path: Path) -> None:
        shutil.copy2(
            source_path, resolved_path
        )  # shutil.copy2 preserves metadata

    def create_symlink(self, source_path: Path, resolved_path: Path) -> None:
        try:
            real_source = source_path.resolve(strict=True)
        except (FileNotFoundError, RuntimeError, OSError) as e:
            errmsg = (
                f"Invalid source path {source_path}: possible symlink loop"
            )
            raise RuntimeError(errmsg) from e
        resolved_path.symlink_to(real_source, target_is_directory=False)

    def create_hardlink(self, source_path: Path, resolved_path: Path) -> None:
        try:
            resolved_path.hardlink_to(source_path)
        except OSError as e:
            errmsg = (
                f"Failed to create hard link: {source_path} to {resolved_path}"
            )
            raise RuntimeError(errmsg) from e

    @classmethod
    def validate(cls: Type["FileAction"], action: str) -> "FileAction":
        if not isinstance(action, cls):
            try:
                return cls(action)
            except ValueError as e:
                valid_actions = ", ".join([f"`{a.value}`" for a in cls])
                msg = f"Invalid action: {action}. Must be one of: {valid_actions}"
                raise ValueError(msg) from e
        return action

    @staticmethod
    def choices() -> List[str]:
        """Return a list of valid file actions."""
        return [action.value for action in FileAction]


def handle_file(
    source_path: Path,
    resolved_path: Path,
    action: FileAction | str,
    overwrite: bool = False,
) -> None:
    if not isinstance(action, FileAction):
        action = FileAction.validate(action)

    # Check if the source exists
    if not source_path.exists():
        msg = f"Source does not exist: {source_path}"
        raise FileNotFoundError(msg)

    try:
        if not overwrite and resolved_path.exists():
            msg = f"Destination already exists: {resolved_path}"
            raise FileExistsError(msg)
        # Ensure the parent directory exists and has write permission
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        errmsg = f"Failed to create parent directory or no write permission: {resolved_path.parent}"
        raise PermissionError(errmsg) from e

    action.handle(source_path, resolved_path)
