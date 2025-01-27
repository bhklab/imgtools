from __future__ import annotations

import re
from abc import ABC, abstractmethod
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    NoReturn,
    Optional,
    TypeVar,
    Generic,
)

from fasteners import InterProcessLock  # type: ignore

from imgtools.exceptions import DirectoryNotFoundError
from imgtools.logging import logger
from imgtools.pattern_parser import (
    PatternResolver,
    MissingPlaceholderValueError,
)

if TYPE_CHECKING:
    from types import TracebackType


class ExistingFileMode(str, Enum):
    """
    Enum to specify handling behavior for existing files.

    Attributes
    ----------
    OVERWRITE: str
        Overwrite the existing file. Logs as debug and continues with the
        operation.
    FAIL: str
        Fail the operation if the file exists. Logs as error and raises a
        FileExistsError.
    SKIP: str
        Skip the operation if the file exists. Meant to be used for previewing
        the path before any expensive computation. `preview_path()` will return
        None if the file exists. `resolve_path()` will still return the path
        even if the file exists. The writer's `save` method should handle the
        file existence if set to SKIP.
    """

    OVERWRITE = "overwrite"
    SKIP = "skip"
    FAIL = "fail"


# Generic type for any content that will be saved by an
# implementation of AbstractBaseWriter
ContentType = TypeVar("ContentType")


# here we add a Generic type to the class
#
@dataclass
class AbstractBaseWriter(ABC, Generic[ContentType]):
    """
    Abstract base class for managing file writing with customizable paths and
    filenames.

    This class provides a template for writing files with a flexible directory
    structure.
    """

    # Any subclass has to be initialized with a root directory and a filename format
    # Gets converted to a Path object in __post_init__
    root_directory: Path = field(
        metadata={"help": "Root directory where files will be saved."}
    )

    # The filename format string with placeholders for context variables
    # e.g. "{subject_id}_{date}/{disease}.txt"
    filename_format: str = field(
        metadata={
            "help": (
                "Format string defining the directory and filename structure. "
                "Supports placeholders for context variables. "
                "e.g. '{subject_id}_{date}/{disease}.txt'"
            )
        }
    )

    # optionally, you can set create_dirs to False if you want to handle the directory creation yourself
    create_dirs: bool = field(
        default=True,
        metadata={
            "help": "If True, creates necessary directories if they don't exist."
        },
    )

    existing_file_mode: ExistingFileMode = field(
        default=ExistingFileMode.FAIL,
        metadata={
            "help": "Behavior when a file already exists. Options: OVERWRITE, SKIP, FAIL"
        },
    )

    sanitize_filenames: bool = field(
        default=True,
        metadata={
            "help": "If True, replaces illegal characters from filenames with underscores."
        },
    )

    # Internal context storage for pre-checking
    context: Dict[str, Any] = field(default_factory=dict)

    # PatternResolver to handle filename formatting
    # class-level pattern resolver instance shared across all instances
    pattern_resolver: PatternResolver = field(init=False)

    index_filename: Optional[str] = field(
        default=None,
        metadata={
            "help": (
                "Name of the index file to track saved files. If an absolute path "
                "is provided, it will be used as is. If not provided, it will be saved "
                f"in the root directory with the format of {root_directory.name}_index.csv."
            )
        },
    )

    overwrite_index: bool = field(
        default=False,
        metadata={
            "help": "If True, overwrites the index file if it already exists."
        },
    )

    absolute_paths_in_index: bool = field(
        default=False,
        metadata={
            "help": (
                "If True, saves absolute paths in the index file. "
                "If False, saves paths relative to the root directory."
            )
        },
    )

    # Cache for directories to avoid redundant checks
    _checked_directories: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        """
        Initialize the writer with the given root directory and filename
        format.
        """
        self.root_directory = Path(self.root_directory)
        if self.create_dirs:
            self._ensure_directory_exists(self.root_directory)
            self._ensure_directory_exists(self.index_file.parent)
        elif not self.root_directory.exists():
            msg = f"Root directory {self.root_directory} does not exist."
            raise DirectoryNotFoundError(msg)
        elif not self.index_file.parent.exists():
            msg = f"Index file directory {self.index_file.parent} does not exist."
            raise DirectoryNotFoundError(msg)
        if self.index_file.exists() and self.overwrite_index:
            logger.info(
                f"Index file {self.index_file} already exists. Copying to .backup."
            )
            # copy to .backup just in case
            self.index_file.rename(f"{self.index_file}.backup")
        self.pattern_resolver = PatternResolver(self.filename_format)

        # if the existing_file_mode is a string, convert it to the Enum
        match self.existing_file_mode:
            case str():
                self.existing_file_mode = ExistingFileMode[
                    self.existing_file_mode.upper()
                ]
            case _:
                errmsg = (  # type: ignore
                    f"Invalid existing_file_mode {self.existing_file_mode}. "
                    "Must be one of 'overwrite', 'skip', or 'fail'."
                )
                raise ValueError(errmsg)

    @abstractmethod
    def save(self, data: ContentType, **kwargs: Any) -> Path:
        """
        Abstract method for writing data. Must be implemented by subclasses.

        Can use resolve_path() or resolve_and_validate_path() to get the output
        path.

        For efficiency, use self.context to access the context variables,
        updating them with the kwargs passed from the save method.

        This will help simplify repeated saves with similar context variables.
        """
        pass

    @property
    def index_file(self) -> Path:
        """
        Get the path to the index CSV file.
        """
        if (index_path := Path(self._index_filename)).is_absolute():
            return index_path
        return self.root_directory / self._index_filename

    @property
    def _index_filename(self) -> str:
        """
        Get the path to the index CSV file.
        """
        if self.index_filename is None:
            root_dir_basename = self.root_directory.name
            return f"{root_dir_basename}_index.csv"
        return self.index_filename

    def _get_index_lock(self) -> Path:
        """
        Get the path to the lock file for the index CSV.
        """
        return Path(f"{self.index_file}.lock")

    def set_context(self, **kwargs: object) -> None:
        """
        Set the context for the writer.
        """
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """
        Clear the context for the writer.

        Useful for resetting the context after using `preview_path` or `save`
        and want to make sure that the context is empty for new operations.
        """
        self.context.clear()

    def _generate_path(self, **kwargs: object) -> Path:
        """
        Helper for resolving paths with the given context.
        """
        save_context = {
            **self._generate_datetime_strings(),
            **self.context,
            **kwargs,
        }
        self.set_context(**save_context)
        try:
            filename = self.pattern_resolver.resolve(save_context)
        except MissingPlaceholderValueError as e:
            # Replace the class name in the error message dynamically
            raise MissingPlaceholderValueError(
                e.missing_keys,
                class_name=self.__class__.__name__,
                key=e.key,
            ) from e
        if self.sanitize_filenames:
            filename = self._sanitize_filename(filename)
        out_path = self.root_directory / filename
        logger.debug(
            f"Resolved path: {out_path} and {out_path.exists()=}",
            handling=self.existing_file_mode,
        )
        return out_path

    def resolve_path(self, **kwargs: object) -> Path:
        """
        Generate a file path based on the filename format, subject ID, and
        additional parameters.

        Meant to be used by developers when creating a new writer class
        and used internally by the `save` method.

        **What It Does**:

        - Dynamically generates a file path based on the provided context and
        filename format.

        **When to Use It**:

        - This method is meant to be used in the `save` method to determine the
        file’s target location, but can also be used by external code to
        generate paths.
        - It ensures you’re working with a valid path and can handle file
        existence scenarios.
        - Only raises `FileExistsError` if the file already exists and the mode
        is set to `FAIL`.

        Parameters
        ----------
        **kwargs : Any
            Parameters for resolving the filename and validating existence.

        Returns
        -------
        resolved_path: Path
            The resolved path for the file.

        Raises
        ------
        FileExistsError
            If the file already exists and the mode is set to FAIL.
        """
        out_path = self._generate_path(**kwargs)
        if not out_path.exists():
            if self.create_dirs:
                self._ensure_directory_exists(out_path.parent)
            # should we raise this error here?
            # elif not out_path.parent.exists():
            #     msg = f"Directory {out_path.parent} does not exist."
            #     raise DirectoryNotFoundError(msg)
            return out_path
        match self.existing_file_mode:
            case ExistingFileMode.SKIP:
                return out_path
            case ExistingFileMode.FAIL:
                msg = f"File {out_path} already exists."
                raise FileExistsError(msg)
            case ExistingFileMode.OVERWRITE:
                logger.debug(f"Deleting existing {out_path} and overwriting.")
                out_path.unlink()
                return out_path

    def preview_path(self, **kwargs: object) -> Optional[Path]:
        """
        Pre-checking file existence and setting up the writer context.

        Meant to be used by users to skip expensive computations if a file
        Only difference between this and resolve_path is that this method
        returns `None` if the file exists and the mode is `SKIP`.
        This is because, the `.save()` method should be able to return
        the path even if the file exists.

        **What It Does**:

        - Pre-checks the file path based on context without writing the file.
        - Returns `None` if the file exists and the mode is set to `SKIP`.
        - Raises a `FileExistsError` if the mode is set to `FAIL`.
        - An added benefit of using `preview_path` is that it automatically
        caches the context variables for future use, and `save()` can be called
        without passing in the context variables again.

        **When to Use It**:

        - Meant to be called by users to skip expensive computations if a file
        already exists and you don’t want to overwrite it.

        Examples
        --------

        Main idea here is to allow users to save computation if they choose to
        skip existing files.

        i.e if file exists and mode is **`SKIP`**, we return
        `None`, so the user can skip the computation.
        >>> if nifti_writer.preview_path(subject="math", name="test") is None:
        >>>     logger.info("File already exists. Skipping computation.")
        >>>     continue # could be `break` or `return` depending on the use case

        if the mode is **`FAIL`**, we raise an error if the file exists, so user
        doesnt have to perform expensive computation only to fail when saving.

        **Useful Feature**
        ----------------------
        the context is saved in the instance, so running
        `.save()` after this will use the same context, and user can optionally
        update the context with new values passed to .save().

        ```python
        >>> if path := writer.preview_path(subject="math", name="test"):
        >>>     ... # do some expensive computation to generate the data
        >>>     writer.save(data)
        ```
        `.save()` automatically uses the context for `subject` and `name` we
        passed to `preview_path`

        Parameters
        ----------
        **kwargs : Any
            Parameters for resolving the filename and validating existence.

        Returns
        ------
        Path | None
            if the file exists and the mode is SKIP, returns None. if the file
            exists and the mode is FAIL, raises a FileExistsError. if the file
            exists and the mode is OVERWRITE, logs a debug message and returns
            the path.

        Raises
        ------
        FileExistsError
            If the file exists and the mode is FAIL.
        """
        out_path = self._generate_path(**kwargs)

        if not out_path.exists():
            return out_path
        elif out_path.is_dir():
            msg = f"Path {out_path} is already a directory that exists."
            msg += " Use a different filename format or context to avoid this."
            raise IsADirectoryError(msg)

        match self.existing_file_mode:
            case ExistingFileMode.SKIP:
                return None
            case ExistingFileMode.FAIL:
                msg = f"File {out_path} already exists."
                raise FileExistsError(msg)
            case ExistingFileMode.OVERWRITE:
                logger.debug(
                    f"File {out_path} exists. Deleting and overwriting."
                )
                out_path.unlink()

        return out_path

    # Context Manager Implementation
    def __enter__(self) -> AbstractBaseWriter:
        """
        Enter the runtime context related to this writer.

        Useful if the writer needs to perform setup actions, such as opening
        connections or preparing resources.
        """
        logger.debug(f"Entering context manager for {self.__class__.__name__}")
        return self

    def __exit__(
        self: AbstractBaseWriter,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """
        Exit the runtime context related to this writer.

        Parameters
        ----------
        exc_type : Optional[type]
            The exception type, if an exception was raised, otherwise None.
        exc_value : Optional[BaseException]
            The exception instance, if an exception was raised, otherwise None.
        traceback : Optional[Any]
            The traceback object, if an exception was raised, otherwise None.
        """
        logger.debug(f"Exiting context manager for {self.__class__.__name__}")

        if exc_type:
            msg = f"An exception occurred in {self.__class__.__name__}."
            logger.exception(
                msg,
                exc_info=exc_value,
            )

        if self.index_file.exists():
            logger.debug(f"Removing lock file {self._get_index_lock()}")
            lock_file = self._get_index_lock()
            if lock_file.exists():
                lock_file.unlink()

        # if the root directory is empty, aka we created it but didn't write anything, delete it
        if (
            self.create_dirs
            and self.root_directory.exists()
            and not any(self.root_directory.iterdir())
        ):
            logger.debug(f"Deleting empty directory {self.root_directory}")
            self.root_directory.rmdir()  # remove the directory if it's empty

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Sanitize a filename to remove or replace bad characters.

        Parameters
        ----------
        filename : str
            The original filename.

        Returns
        -------
        str
            A sanitized filename safe for most file systems.
        """

        # Replace bad characters with underscores
        sanitized = re.sub(r'[<>:"\\|?*]', "_", filename)

        # Optionally trim leading/trailing spaces or periods
        sanitized = sanitized.strip(" .")

        return sanitized

    def _ensure_directory_exists(self, directory: Path) -> None:
        """
        Ensure a directory exists, caching the check to avoid redundant
        operations.
        """
        if str(directory) not in self._checked_directories:
            directory.mkdir(parents=True, exist_ok=True)
            self._checked_directories.add(str(directory))

    def put(self, *args, **kwargs) -> NoReturn:  # type: ignore # noqa
        """
        Accdidentally using put() instead of save() will raise a fatal error.
        """
        msg = (
            "Method put() is deprecated and will be removed in future versions. "
            "Please use AbstractBaseWriter.save() instead of the old BaseWriter.put()."
        )
        logger.fatal(msg)
        import sys

        sys.exit(1)

    def _generate_datetime_strings(self) -> dict[str, str]:
        """
        Free to use date-time context values.
        """
        now = datetime.now(timezone.utc)
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H%M%S"),
            "date_time": now.strftime("%Y-%m-%d_%H%M%S"),
        }

    def __del__(self) -> None:
        """
        Ensure the lock file is removed when the writer is deleted.
        """
        if (lock := self._get_index_lock()).exists():
            lock.unlink()

    def add_to_index(
        self,
        path: Path,
        include_all_context: bool = True,
        filepath_column: str = "path",
        replace_existing: bool = False,
        **additional_context: object,
    ) -> None:
        """
        Add or update an entry in the shared CSV index file.


        **What It Does**:

        - Logs the file’s path and associated context variables to a
            shared CSV index file.
        - Uses inter-process locking to avoid conflicts when
            multiple writers are active.

        **When to Use It**:

        - Use this method to maintain a centralized record of saved
        files for auditing or debugging.

        **Relevant Writer Parameters**
        ------------------------------

        - The `index_filename` parameter allows you to specify a
        custom filename for the index file.
        By default, it will be named after the `root_directory`
        with `_index.csv` appended.

        - If the index file already exists in the root directory,
        it will overwrite it unless
        the `overwrite_index` parameter is set to `False`.

        - The `absolute_paths_in_index` parameter controls whether
        the paths in the index file are absolute or relative to the
        `root_directory`, with `False` being the default.

        Parameters
        ----------
        path : Path
            The file path being saved.
        include_all_context : bool
            If True, write existing context variables passed into writer and
            the additional context to the CSV.
            If False, determines only the context keys parsed from the
            `filename_format` (excludes all other context variables, and
            unused context keys).
        filepath_column : str
            The name of the column to store the file path. Defaults to "path".
        replace_existing : bool
            If True, checks if the file path already exists in the index and
            replaces it.
        **additional_context : Any
            Additional context information to include in the CSV passed in as
            keyword arguments.

        Notes
        -----
        When `replace_existing` is set to True, the method will check if the
        file path already exists in the index file using `csv.Sniffer` and
        replace the row if it does. If the file path does not exist in the
        index file, it will add a new row with the file path and context
        information.
        """

        lock_file = self._get_index_lock()
        self._ensure_directory_exists(self.index_file.parent)

        # Prepare context and resolve the file path
        context = {**self.context, **additional_context}
        resolved_path = (
            path.resolve().absolute()
            if self.absolute_paths_in_index
            else path.relative_to(self.root_directory)
        )
        fieldnames = [
            filepath_column,
            *(
                context.keys()
                if include_all_context
                else self.pattern_resolver.keys
            ),
        ]

        rows = []
        # Check if replacing existing entries and if the index file exists
        if replace_existing and self.index_file.exists():
            # Read and validate the index file format
            try:
                with (
                    InterProcessLock(lock_file),
                    self.index_file.open(mode="r", encoding="utf-8") as f,
                ):
                    # Use csv.Sniffer to check if the file has a header
                    sniffer = csv.Sniffer()
                    if not sniffer.has_header(f.readline()):
                        msg = (
                            f"Index {self.index_file} is missing a header row."
                        )
                        raise ValueError(msg)

                    # Reset the file pointer after sampling
                    f.seek(0)
                    reader = csv.DictReader(f)
                    # Check if the required column is present in the index file
                    if (
                        reader.fieldnames is None
                        or filepath_column not in reader.fieldnames
                    ):
                        msg = (
                            f"Index file {self.index_file} does "
                            f"not contain the column '{filepath_column}'."
                        )
                        raise ValueError(msg)
                    # Filter out the existing entry for the resolved path
                    rows = [
                        row
                        for row in reader
                        if row[filepath_column] != str(resolved_path)
                    ]
            except Exception as e:
                # Log and raise any exceptions encountered during validation
                logger.exception(
                    f"Error validating index file {self.index_file}.", error=e
                )
                raise

        # Add the new or updated row
        rows.append({filepath_column: str(resolved_path), **context})

        # Write the updated rows back to the index file
        try:
            with (
                InterProcessLock(lock_file),
                self.index_file.open(
                    mode="w", newline="", encoding="utf-8"
                ) as f,
            ):
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except Exception as e:
            logger.exception(
                f"Error writing to index file {self.index_file}.", error=e
            )
            raise


class ExampleWriter(AbstractBaseWriter[str]):
    """
    A concrete implementation of AbstractBaseWriter for demonstration.
    """

    def save(self, data: str, **kwargs: object) -> Path:
        """
        Save content to a file with the resolved path.

        Parameters
        ----------
        content : str
            The content to write to the file.
        **kwargs : Any
            Additional context for filename generation.

        Returns
        -------
        Path
            The path to the saved file.
        """
        # Resolve the output file path
        output_path = self.resolve_path(**kwargs)

        # Write content to the file
        with output_path.open(mode="w", encoding="utf-8") as f:
            f.write(data)

        # Log the save operation
        logger.debug(f"File saved: {output_path}")

        self.add_to_index(output_path, replace_existing=output_path.exists())

        return output_path


# ruff: noqa

# if __name__ == "__main__":
#     import multiprocessing
#     import time
#     from pathlib import Path
#     from random import randint
#     from typing import Any, Dict

#     # Configuration for the test
#     num_processes = 2
#     files_per_process = 5

#     def write_files_in_process(
#         process_id: int,
#         writer_config: Dict[str, Any],
#         file_count: int,
#         mode: str,
#     ):
#         """
#         Worker function for a process to write files using ExampleWriter.
#         """
#         writer = ExampleWriter(**writer_config)

#         content = f"This is a file written by process {process_id}."
#         with writer:
#             for i in range(file_count):
#                 time.sleep(randint(1, 5) / 100)
#                 context = {
#                     "name": f"file_{process_id}_{i:04}",
#                     "extra_info": f"process_{process_id}",
#                 }
#                 writer.save(content, **context, experiment_type=mode)

#     def run_multiprocessing(
#         writer_config: Dict[str, Any],
#         num_processes: int,
#         files_per_process: int,
#     ):
#         """
#         Run file-writing tasks using multiprocessing.
#         """
#         processes = []
#         for process_id in range(num_processes):
#             p = multiprocessing.Process(
#                 target=write_files_in_process,
#                 args=(
#                     process_id,
#                     writer_config,
#                     files_per_process,
#                     "multiprocessing",
#                 ),
#             )
#             processes.append(p)
#             p.start()

#         for p in processes:
#             p.join()

#     def run_single_process(
#         writer_config: Dict[str, Any],
#         num_processes: int,
#         files_per_process: int,
#     ):
#         """
#         Run file-writing tasks sequentially without multiprocessing.
#         """
#         for process_id in range(num_processes):
#             write_files_in_process(
#                 process_id, writer_config, files_per_process, "single"
#             )

#     ROOT_DIR = Path("./data/demo/abstract_writer_showcase")

#     # Writer configuration
#     writer_config = {
#         "root_directory": ROOT_DIR,
#         "filename_format": "{experiment_type}/{name}_{extra_info}.txt",
#         "create_dirs": True,
#         "existing_file_mode": ExistingFileMode.OVERWRITE,
#         "overwrite_index": False,  # default
#         "index_filename": "wow.csv",
#     }

#     try:
#         writer = ExampleWriter(
#             **writer_config, context={"experiment_type": "test"}
#         )
#     except:
#         logger.exception("Error creating writer.")
#     else:
#         print(writer.index_file)
#         # print(writer.context)
#         # exit(0)

#     print("Running with multiprocessing...")
#     start_time = time.time()
#     run_multiprocessing(writer_config, num_processes, files_per_process)
#     multiprocessing_duration = time.time() - start_time

#     print("\nRunning without multiprocessing...")
#     start_time = time.time()
#     run_single_process(writer_config, num_processes, files_per_process)
#     single_process_duration = time.time() - start_time
#     print(
#         f"Time taken with multiprocessing: {multiprocessing_duration:.2f} seconds"
#     )
#     print(
#         f"Time taken without multiprocessing: {single_process_duration:.2f} seconds"
#     )

#     # Compare times
#     time_difference = single_process_duration - multiprocessing_duration
#     print(
#         f"\nMultiprocessing was faster by {time_difference:.2f} seconds"
#         if time_difference > 0
#         else f"\nSingle process was faster by {-time_difference:.2f} seconds"
#     )
#     # Calculate and print the percentage improvement
#     improvement_percentage = (time_difference / single_process_duration) * 100
#     print(
#         f"Multiprocessing improved the performance by {improvement_percentage:.2f}%"
# )

# Output:
# 4 procs and 100 files per proc
# Time taken with multiprocessing: 3.51 seconds
# Time taken without multiprocessing: 13.16 seconds

# Multiprocessing was faster by 9.65 seconds
# Multiprocessing improved the performance by 73.31%
