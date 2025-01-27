import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from imgtools.dicom.sort.sort_method import FileAction, handle_file


@pytest.fixture
def temp_dir():
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_move_file(temp_dir) -> None:
    source = temp_dir / "source.txt"
    destination = temp_dir / "destination.txt"
    source.write_text("Test content")

    handle_file(source, destination, FileAction.MOVE)

    assert not source.exists()
    assert destination.exists()
    assert destination.read_text() == "Test content"


def test_copy_file(temp_dir) -> None:
    source = temp_dir / "source.txt"
    destination = temp_dir / "destination.txt"
    source.write_text("Test content")

    handle_file(source, destination, FileAction.COPY)

    assert source.exists()
    assert destination.exists()
    assert destination.read_text() == "Test content"


def test_create_symlink(temp_dir) -> None:
    source = temp_dir / "source.txt"
    symlink = temp_dir / "symlink.txt"
    source.write_text("Test content")

    handle_file(source, symlink, FileAction.SYMLINK)

    assert symlink.exists()
    assert symlink.is_symlink()
    assert symlink.read_text() == "Test content"


def test_create_hardlink(temp_dir) -> None:
    source = temp_dir / "source.txt"
    hardlink = temp_dir / "hardlink.txt"
    source.write_text("Test content")

    handle_file(source, hardlink, FileAction.HARDLINK)

    assert hardlink.exists()
    assert hardlink.stat().st_ino == source.stat().st_ino


def test_invalid_action(temp_dir) -> None:
    source = temp_dir / "source.txt"
    destination = temp_dir / "destination.txt"
    source.write_text("Test content")

    with pytest.raises(ValueError):
        handle_file(source, destination, "invalid_action")


def test_source_does_not_exist(temp_dir) -> None:
    source = temp_dir / "non_existent.txt"
    destination = temp_dir / "destination.txt"

    with pytest.raises(FileNotFoundError):
        handle_file(source, destination, FileAction.MOVE)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Skipping test: chmod behavior is inconsistent on Windows."
)
def test_no_write_permission(temp_dir) -> None:
    source = temp_dir / "source.txt"
    destination = temp_dir / "no_permission_dir/destination.txt"
    source.write_text("Test content")

    os.chmod(temp_dir, 0o400)  # Read-only permission

    with pytest.raises(PermissionError):
        handle_file(source, destination, FileAction.MOVE)

    os.chmod(temp_dir, 0o700)  # Restore permissions


@pytest.mark.skipif(
    sys.platform == "win32", reason="Skipping test: chmod behavior is inconsistent on Windows."
)
def test_parent_directory_creation_error(temp_dir) -> None:
    source = temp_dir / "source.txt"
    destination = temp_dir / "no_permission_dir/destination.txt"
    source.write_text("Test content")

    os.chmod(temp_dir, 0o400)  # Read-only permission

    with pytest.raises(PermissionError):
        handle_file(source, destination, FileAction.COPY)

    os.chmod(temp_dir, 0o700)  # Restore permissions


@pytest.mark.skipif(
    sys.platform == "win32", reason="Skipping test: chmod behavior is inconsistent on Windows."
)
def test_no_write_permissions_for_directory(temp_dir) -> None:
    source = temp_dir / "source.txt"
    destination = temp_dir / "no_permission_dir/destination.txt"
    source.write_text("Test content")
    destination.parent.mkdir(0o400, parents=True)  # Create a read-only parent directory

    with pytest.raises(
        PermissionError, match="Failed to create parent directory or no write permission"
    ):
        handle_file(source, destination, FileAction.MOVE)

    os.chmod(temp_dir, 0o700)  # Restore permissions


def test_overwrite_file(temp_dir) -> None:
    source = temp_dir / "source.txt"
    destination = temp_dir / "destination.txt"
    source.write_text("Test content")
    destination.write_text("Old content")

    handle_file(source, destination, FileAction.COPY, overwrite=True)

    assert destination.read_text() == "Test content"


def test_no_overwrite_file(temp_dir) -> None:
    source = temp_dir / "source.txt"
    destination = temp_dir / "destination.txt"
    source.write_text("Test content")
    destination.write_text("Old content")

    with pytest.raises(FileExistsError):
        handle_file(source, destination, FileAction.COPY, overwrite=False)


def test_create_symlink_error(temp_dir) -> None:
    source = temp_dir / "source.txt"
    source.write_text("Test content")
    symlink = temp_dir / "symlink.txt"
    symlink.symlink_to(source)  # Create a symlink to the source file

    # Create a symlink loop
    source.unlink()
    source.symlink_to(symlink)

    with pytest.raises(RuntimeError):
        FileAction.SYMLINK.create_symlink(source, symlink)


def test_create_hardlink_error(temp_dir) -> None:
    source = temp_dir / "source.txt"
    hardlink = temp_dir / "hardlink.txt"
    source.write_text("Test content")
    hardlink.mkdir()  # Create a directory to cause an error

    with pytest.raises(RuntimeError, match="Failed to create hard link"):
        FileAction.HARDLINK.create_hardlink(source, hardlink)


def test_choices() -> None:
    assert FileAction.choices() == ["move", "copy", "symlink", "hardlink"]
