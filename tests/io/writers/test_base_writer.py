from pathlib import Path

import pytest

from imgtools.exceptions import DirectoryNotFoundError
from imgtools.io.writers import AbstractBaseWriter, ExistingFileMode


class SimpleWriter(AbstractBaseWriter):
    def save(self, content: str) -> Path:
        """
        Save the provided content to a file at the resolved path.

        Writes the input content to a file located at the path returned by `resolve_path()`.
        Opens the file in write mode, which will create a new file or overwrite an existing file.

        Parameters:
            content (str): The text content to be written to the file.

        Returns:
            Path: The file path where the content was saved.

        Raises:
            IOError: If there are issues writing to the file.
            OSError: If there are filesystem-related errors during file creation.
        """
        file_path = self.resolve_path()
        with open(file_path, "w") as f:
            f.write(content)
        return file_path


class MediumWriter(AbstractBaseWriter):
    def save(self, content: str, suffix: str = "") -> Path:
        """
        Save content to a file with an optional filename suffix.

        Parameters:
            content (str): The text content to be written to the file
            suffix (str, optional): A suffix to be appended to the filename. Defaults to an empty string.

        Returns:
            Path: The file path where the content was saved

        Raises:
            IOError: If there are issues writing to the file
        """
        file_path = self.resolve_path(suffix=suffix)
        with open(file_path, "w") as f:
            f.write(content)
        return file_path


class ComplexWriter(AbstractBaseWriter):
    def save(self, content: str, metadata: dict) -> Path:
        """
        Save content to a file using metadata to resolve the file path.

        Parameters:
            content (str): The text content to be written to the file
            metadata (dict): A dictionary containing parameters used to resolve the file path

        Returns:
            Path: The resolved file path where the content was saved

        Raises:
            OSError: If there are issues creating or writing to the file
        """
        file_path = self.resolve_path(**metadata)
        with open(file_path, "w") as f:
            f.write(content)
        return file_path


def test_simple_writer(tmp_path):
    """
    Test the functionality of SimpleWriter by saving content and verifying file creation and content.

    This test ensures that:
    - A SimpleWriter can be instantiated with a temporary directory and filename format
    - Content can be saved using the save() method
    - The resulting file exists
    - The file contains the exact content that was saved

    Args:
        tmp_path (Path): Temporary directory provided by pytest for test isolation

    Raises:
        AssertionError: If file is not created or content does not match
    """
    writer = SimpleWriter(root_directory=tmp_path, filename_format="{date_time}.txt")
    with writer:
        file_path = writer.save("Simple content")
    assert file_path.exists()
    assert file_path.read_text() == "Simple content"


def test_medium_writer(tmp_path):
    """
    Test the MediumWriter's ability to save content with a custom suffix.

    This test verifies that:
    - A MediumWriter can be instantiated with a temporary directory and custom filename format
    - The save method works with a provided suffix
    - The file is created successfully
    - The file contains the expected content

    Args:
        tmp_path (Path): Temporary directory provided by pytest for test isolation

    Raises:
        AssertionError: If file is not created or content does not match expected value
    """
    writer = MediumWriter(
        root_directory=tmp_path, filename_format="{date_time}_{suffix}.txt"
    )
    with writer:
        file_path = writer.save("Medium content", suffix="test")
    assert file_path.exists()
    assert file_path.read_text() == "Medium content"


def test_complex_writer(tmp_path):
    """
    Test the functionality of the ComplexWriter class with metadata-based file naming.

    This test verifies that:
    - A ComplexWriter can be instantiated with a root directory and filename format
    - The save method works with metadata to generate a unique filename
    - The content is correctly written to the file
    - The file is created and exists after saving

    Args:
        tmp_path (Path): Temporary directory provided by pytest for test isolation

    Raises:
        AssertionError: If file is not created or content does not match expected value
    """
    writer = ComplexWriter(
        root_directory=tmp_path, filename_format="{date_time}_{user}.txt"
    )
    with writer:
        file_path = writer.save("Complex content", metadata={"user": "testuser"})
    assert file_path.exists()
    assert file_path.read_text() == "Complex content"


def test_context_manager_cleanup(tmp_path):
    """
    Test the context manager functionality of SimpleWriter to ensure directory cleanup.

    This test verifies that when a SimpleWriter is used as a context manager, the specified
    directory is created during entry and automatically removed upon exit, leaving no trace
    of the temporary directory.

    Args:
        tmp_path (Path): Temporary directory provided by pytest for isolated testing

    Raises:
        AssertionError: If the directory is not created during context manager entry
                        or not cleaned up during context manager exit
    """
    subdir = tmp_path / "nested"
    writer = SimpleWriter(root_directory=subdir, filename_format="{date_time}.txt")
    with writer:
        assert subdir.exists()
    assert not subdir.exists()


def test_directory_creation(tmp_path):
    """
    Test the directory creation functionality of SimpleWriter.

    This test verifies that:
    1. SimpleWriter creates the specified nested directory if it does not exist
    2. The file is successfully saved within the created directory
    3. The saved file contains the expected content

    Args:
        tmp_path (Path): Temporary directory provided by pytest for testing file operations

    Raises:
        AssertionError: If the directory is not created, file is not saved, or content is incorrect
    """
    writer = SimpleWriter(
        root_directory=tmp_path / "nested", filename_format="{date_time}.txt"
    )
    with writer:
        file_path = writer.save("Content")
    assert file_path.exists()
    assert file_path.read_text() == "Content"
    assert (tmp_path / "nested").exists()


def test_directory_not_created_if_exists(tmp_path):
    """
    Test that an existing directory is not recreated when using SimpleWriter.

    This test verifies that when a directory already exists, SimpleWriter does not attempt to create it again.
    The test ensures that:
    - An existing directory remains intact
    - Content can be saved to the directory
    - The saved file is created correctly with the expected content

    Parameters:
        tmp_path (Path): Temporary directory provided by pytest for isolated file operations

    Raises:
        AssertionError: If the file is not created, content is incorrect, or directory is modified
    """
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()
    writer = SimpleWriter(
        root_directory=existing_dir, filename_format="{date_time}.txt"
    )
    with writer:
        file_path = writer.save("Content")
    assert file_path.exists()
    assert file_path.read_text() == "Content"
    assert existing_dir.exists()


def test_writer_put_exit(tmp_path):
    """
    Test that calling the `put()` method on a `SimpleWriter` raises a `SystemExit` exception.

    This test verifies the behavior of the `put()` method when called without arguments, ensuring it terminates the program
    with an exit code of 1.

    Args:
        tmp_path (Path): Temporary directory provided by pytest for test file operations.

    Raises:
        SystemExit: Expected exception with exit code 1 when `put()` is called.
    """
    writer = SimpleWriter(root_directory=tmp_path, filename_format="{date_time}.txt")
    with pytest.raises(SystemExit) as excinfo:
        writer.put()
    assert excinfo.value.code == 1


def test_no_create_dirs_non_existent(tmp_path):
    """
    Test that saving a file to a non-existent directory raises a DirectoryNotFoundError when create_dirs is set to False.

    This test verifies the behavior of SimpleWriter when attempting to save a file in a directory that does not exist and the create_dirs option is disabled. It ensures that an exception is raised instead of automatically creating the directory.

    Args:
        tmp_path (Path): Temporary directory path provided by pytest for testing file operations.

    Raises:
        DirectoryNotFoundError: When attempting to save a file in a non-existent directory with create_dirs=False.
    """
    with pytest.raises(DirectoryNotFoundError):
        with SimpleWriter(
            root_directory=tmp_path / "nested_non_existent",
            filename_format="{date_time}.txt",
            create_dirs=False,
        ) as writer:
            file_path = writer.save("Content")  # noqa


def test_pre_check_context(tmp_path):
    """
    Test the preview_path method of SimpleWriter with various existing file modes.

    This test function verifies the behavior of the preview_path method under different configurations:
    - Checks successful path preview and file creation
    - Validates context management
    - Tests handling of existing files with FAIL mode
    - Ensures correct behavior for SKIP and OVERWRITE modes

    Parameters:
        tmp_path (Path): Temporary directory provided by pytest for test isolation

    Raises:
        FileExistsError: When attempting to preview an existing file with FAIL mode
        AssertionError: If file creation or path preview does not meet expected conditions
    """
    writer = SimpleWriter(
        root_directory=tmp_path,
        filename_format="{subject}_{name}.txt",
        existing_file_mode=ExistingFileMode.FAIL,
    )
    if path := writer.preview_path(subject="math", name="context_test"):
        file_path = writer.save("Content")
        assert file_path.exists()
        assert file_path == path
        assert writer.context["name"] == "context_test"

    # assert writer.context == {}

    with pytest.raises(FileExistsError):
        if writer.preview_path(subject="math", name="context_test"):
            pass

    with pytest.raises(FileExistsError):
        another_path = writer.preview_path(subject="math", name="context_test")  # noqa

    successfulpath = writer.preview_path(subject="math", name="context_test2")
    assert not successfulpath.exists()

    skip_writer = SimpleWriter(
        root_directory=tmp_path,
        filename_format="{subject}_{name}.txt",
        existing_file_mode=ExistingFileMode.SKIP,
    )

    assert skip_writer.preview_path(subject="math", name="context_test") is None

    overwrite_writer = SimpleWriter(
        root_directory=tmp_path,
        filename_format="{subject}_{name}.txt",
        existing_file_mode=ExistingFileMode.OVERWRITE,
    )

    assert (
        overwrite_writer.preview_path(subject="math", name="context_test") is not None
    )


#######################
# some simpler tests


# self.index_file.parent.exists()
def test_index_file_parent_exists(tmp_path):
    with pytest.raises(DirectoryNotFoundError):
        writer = SimpleWriter(
            root_directory=tmp_path,
            filename_format="{date_time}.txt",
            index_filename="/tmp/should_nonexistent/index.csv",
            create_dirs=False,
        )
