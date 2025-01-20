from __future__ import annotations

import re
from abc import ABC, abstractmethod
from csv import DictWriter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, NoReturn, Optional

from fasteners import InterProcessLock

from imgtools.exceptions import DirectoryNotFoundError
from imgtools.logging import logger
from imgtools.pattern_parser import PatternResolver, MissingPlaceholderValueError

if TYPE_CHECKING:
    from types import TracebackType


class ExistingFileMode(Enum):
    """
    Enum to specify handling behavior for existing files.

    Attributes
    ----------
    OVERWRITE : auto()
        Overwrite the existing file. Logs as debug and continues with the operation.
    FAIL : auto()
        Fail the operation if the file exists. Logs as error and raises a FileExistsError.
    RAISE_WARNING : auto()
        Raise a warning if the file exists. Logs as warning and continues with the operation.
    SKIP : auto()
        Skip the operation if the file exists.
        Meant to be used for previewing the path before any expensive computation.
        `preview_path()` will return None if the file exists.
        `resolve_path()` will still return the path even if the file exists.
        The writer's `save` method should handle the file existence if set to SKIP.
    """

    OVERWRITE = auto()
    SKIP = auto()
    FAIL = auto()
    RAISE_WARNING = auto()


@dataclass
class AbstractBaseWriter(ABC):
    """Abstract base class for managing file writing with customizable paths and filenames.

    This class provides a template for writing files with a flexible directory structure.
    """

    # Any subclass has to be initialized with a root directory and a filename format
    # Gets converted to a Path object in __post_init__
    root_directory: Path = field(metadata={"help": "Root directory where files will be saved."})

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
        metadata={"help": "If True, creates necessary directories if they don't exist."},
    )

    existing_file_mode: ExistingFileMode = field(
        default=ExistingFileMode.FAIL,
        metadata={
            "help": "Behavior when a file already exists. Options: OVERWRITE, SKIP, FAIL, RAISE_WARNING."
        },
    )

    sanitize_filenames: bool = field(
        default=True,
        metadata={"help": "If True, replaces illegal characters from filenames with underscores."},
    )

    # Internal context storage for pre-checking
    context: Dict[str, Any] = field(default_factory=dict, init=False)

    # PatternResolver to handle filename formatting
    # class-level pattern resolver instance shared across all instances
    pattern_resolver: PatternResolver = field(init=False)

    index_filename: Optional[str] = field(
        default=None,
        metadata={
            "help": (
                "Name of the index file to track saved files. If an absolute path "
                "is provided, it will be used as is. Otherwise, it will be saved "
                f"in the root directory with the format of {root_directory.name}_index.csv."
            )
        },
    )

    overwrite_index: bool = field(
        default=True,
        metadata={"help": "If True, overwrites the index file if it already exists."},
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
        """Initialize the writer with the given root directory and filename format."""
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
            logger.info(f"Index file {self.index_file} already exists. Copying to .backup.")
            # copy to .backup just in case
            self.index_file.rename(f"{self.index_file}.backup")
        self.pattern_resolver = PatternResolver(self.filename_format)

        # if the existing_file_mode is a string, convert it to the Enum
        if isinstance(self.existing_file_mode, str):
            self.existing_file_mode = ExistingFileMode[self.existing_file_mode.upper()]

    @property
    def index_file(self) -> Path:
        """Get the path to the index CSV file."""
        if (index_path := Path(self._index_filename)).is_absolute():
            return index_path
        return self.root_directory / self._index_filename

    @property
    def _index_filename(self) -> Path:
        """Get the path to the index CSV file."""
        if self.index_filename is None:
            root_dir_basename = self.root_directory.name
            return Path(f"{root_dir_basename}_index.csv")
        return Path(self.index_filename)

    def _get_index_lock(self) -> Path:
        """Get the path to the lock file for the index CSV."""
        return Path(f"{self.index_file}.lock")

    @abstractmethod
    def save(self, *args: Any, **kwargs: Any) -> Path:  # noqa
        """Abstract method for writing data. Must be implemented by subclasses.

        Can use resolve_path() or resolve_and_validate_path() to get the output path.

        For efficiency, use self.context to access the context variables, updating
        them with the kwargs passed from the save method.

        This will help simplify repeated saves with similar context variables.
        """
        pass

    def set_context(self, **kwargs: Any) -> None:  # noqa: ANN401
        """Set the context for the writer."""
        self.context.update(kwargs)

    def _generate_path(self, **kwargs: Any) -> Path:  # noqa: ANN401
        """Helper for resolving paths with the given context."""
        save_context = {**self._generate_datetime_strings(), **self.context, **kwargs}
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

    def resolve_path(self, **kwargs: Any) -> Path:  # noqa: ANN401
        """Generate a file path based on the filename format, subject ID, and additional parameters."""
        out_path = self._generate_path(**kwargs)
        if not out_path.exists() and self.create_dirs:
            self._ensure_directory_exists(out_path.parent)
            return out_path
        match self.existing_file_mode:
            case ExistingFileMode.SKIP:
                logger.debug(f"File {out_path} exists. Skipping.")
                return out_path
            case ExistingFileMode.FAIL:
                msg = f"File {out_path} already exists."
                raise FileExistsError(msg)
            case ExistingFileMode.RAISE_WARNING:
                logger.warning(f"File {out_path} exists. Proceeding anyway.")
            case ExistingFileMode.OVERWRITE:
                logger.debug(f"File {out_path} exists. Deleting and overwriting.")
                out_path.unlink()

        return out_path

    def preview_path(self, **kwargs: Any) -> Optional[Path]:  # noqa: ANN401
        """Pre-checking file existence and setting up the writer context.

        Only difference between this and resolve_path is that this method returns
        None if the file exists and the mode is SKIP.

        Main idea here is to allow users to save computation if they choose to skip existing files.
        i.e if file exists and mode is SKIP, we return None, so the user can skip the computation.
        >>> if writer.preview_path(subject="math", name="context_test") is None:
        >>>     continue

        if the mode is FAIL, we raise an error if the file exists, so user doesnt have to
        perform expensive computation only to fail when saving.

        The keyword arguments passed are also saved in the instance, so running .save() will use
        the same context, optionally can update the context with new values passed to .save().

        >>> if path := writer.preview_path(subject="math", name="context_test"):
        # do some expensive computation to generate the data you wish to save
        >>> writer.save(data)  # automatically uses the context set in preview_path

        Parameters
        ----------
        **kwargs : Any
            Parameters for resolving the filename and validating existence.

        Returns
        ------
        Path | None
            if the file exists and the mode is SKIP, returns None.
            if the file exists and the mode is FAIL, raises a FileExistsError.
            if the file exists and the mode is RAISE_WARNING, logs a warning and returns the path.
            if the file exists and the mode is OVERWRITE, logs a debug message and returns the path.

        Raises
        ------
        FileExistsError
            If the file exists and the mode is FAIL.
        """
        out_path = self._generate_path(**kwargs)

        if not out_path.exists():
            return out_path

        match self.existing_file_mode:
            case ExistingFileMode.SKIP:
                logger.debug(f"File {out_path} exists. Skipping.")
                return None
            case ExistingFileMode.FAIL:
                msg = f"File {out_path} already exists."
                raise FileExistsError(msg)
            case ExistingFileMode.RAISE_WARNING:
                logger.warning(f"File {out_path} exists. Proceeding anyway.")
            case ExistingFileMode.OVERWRITE:
                logger.debug(f"File {out_path} exists. Deleting and overwriting.")
                out_path.unlink()

        return out_path

    # Context Manager Implementation
    def __enter__(self) -> AbstractBaseWriter:
        """
        Enter the runtime context related to this writer.

        Useful if the writer needs to perform setup actions, such as
        opening connections or preparing resources.
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
        if exc_type:
            logger.exception(
                f"Exception raised in {self.__class__.__name__} while in context manager.",
                exc_info=exc_value,
            )
        logger.debug(f"Exiting context manager for {self.__class__.__name__}")
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
        """Ensure a directory exists, caching the check to avoid redundant operations."""
        if str(directory) not in self._checked_directories:
            directory.mkdir(parents=True, exist_ok=True)
            self._checked_directories.add(str(directory))

    def put(self, *args, **kwargs) -> NoReturn:  # noqa
        """Accdidentally using put() instead of save() will raise a fatal error."""
        msg = (
            "Method put() is deprecated and will be removed in future versions. "
            "Please use AbstractBaseWriter.save() instead of the old BaseWriter.put()."
        )
        logger.fatal(msg)
        import sys

        sys.exit(1)

    def _generate_datetime_strings(self) -> dict[str, str]:
        """Free to use date-time context values."""
        now = datetime.now(timezone.utc)
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H%M%S"),
            "date_time": now.strftime("%Y-%m-%d_%H%M%S"),
        }

    def __del__(self) -> None:
        """Ensure the lock file is removed when the writer is deleted."""
        if (lock := self._get_index_lock()).exists():
            lock.unlink()

    def add_to_index(
        self,
        path: Path,
        include_all_context: bool = True,
        filepath_column: str = "path",
        **additional_context: Any,  # noqa
    ) -> None:
        """Dump the given path and context information to a shared CSV file.

        This method writes the provided path and additional context information to a CSV file.
        It uses an inter-process lock to prevent concurrent writes to the file.

        Parameters
        ----------
        path : Path
            The file path being saved.
        include_all_context : bool
            If True, includes all context keys in the CSV (includes datetime strings).
            If False, only includes keys used in the filename.
            Defaults to True.
        filepath_column : str
            The name of the column to store the file path.
            Defaults to "path".
        **additional_context : Any
            Additional context information as keyword-arguments to include in the CSV for this row.

        Notes
        -----
        This does not handle the cases where the headers are different between calls.
        """

        lock_file = self._get_index_lock()
        self._ensure_directory_exists(self.index_file.parent)

        context = {**self.context, **additional_context}

        # Determine which context keys to include based on the parameter
        if include_all_context:
            save_context = context
        else:
            # only consider the keys that were used in the filename_format
            save_context = {k: context[k] for k in self.pattern_resolver.keys}

        fieldnames = [filepath_column, *save_context.keys()]

        resolved_path = (
            path.resolve().absolute()
            if self.absolute_paths_in_index
            else path.relative_to(self.root_directory)
        )
        try:
            with InterProcessLock(lock_file):
                with self.index_file.open(mode="a", newline="", encoding="utf-8") as f:
                    writer = DictWriter(f, fieldnames=fieldnames)

                    # Write the header if the file is empty
                    if self.index_file.stat().st_size == 0:
                        writer.writeheader()

                    # Write the data
                    writer.writerow({"path": str(resolved_path), **save_context})
        except Exception as e:
            logger.exception(f"Error writing to index file {self.index_file}.", error=e)
            raise


class ExampleWriter(AbstractBaseWriter):
    """A concrete implementation of AbstractBaseWriter for demonstration."""

    def save(self, content: str, **kwargs) -> Path:
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
            f.write(content)

        # Log the save operation
        logger.debug(f"File saved: {output_path}")

        self.add_to_index(output_path)

        return output_path


# ruff: noqa

if __name__ == "__main__":
    import multiprocessing
    import time
    from pathlib import Path
    from random import randint
    from typing import Any, Dict

    # Configuration for the test
    num_processes = 2
    files_per_process = 6

    def write_files_in_process(
        process_id: int, writer_config: Dict[str, Any], file_count: int, mode: str
    ):
        """Worker function for a process to write files using ExampleWriter."""
        writer = ExampleWriter(**writer_config)

        content = f"This is a file written by process {process_id}."
        with writer:
            for i in range(file_count):
                time.sleep(randint(1, 5) / 100)
                context = {
                    "name": f"file_{process_id}_{i:04}",
                    "extra_info": f"process_{process_id}",
                }
                writer.save(content, **context, experiment_type=mode)

    def run_multiprocessing(
        writer_config: Dict[str, Any], num_processes: int, files_per_process: int
    ):
        """Run file-writing tasks using multiprocessing."""
        processes = []
        for process_id in range(num_processes):
            p = multiprocessing.Process(
                target=write_files_in_process,
                args=(process_id, writer_config, files_per_process, "multiprocessing"),
            )
            processes.append(p)
            p.start()

        for p in processes:
            p.join()

    def run_single_process(
        writer_config: Dict[str, Any], num_processes: int, files_per_process: int
    ):
        """Run file-writing tasks sequentially without multiprocessing."""
        for process_id in range(num_processes):
            write_files_in_process(process_id, writer_config, files_per_process, "single")

    ROOT_DIR = Path("./data/demo/abstract_writer_showcase")
    if ROOT_DIR.exists():
        import shutil

        shutil.rmtree(ROOT_DIR)

    # Writer configuration
    writer_config = {
        "root_directory": ROOT_DIR,
        "filename_format": "{experiment_type}/{name}_{extra_info}.txt",
        "create_dirs": True,
        "existing_file_mode": ExistingFileMode.OVERWRITE,
        "overwrite_index": False,
    }

    try:
        writer = ExampleWriter(**writer_config)
    except:
        logger.exception("Error creating writer.")
    else:
        print(writer.index_file)

    print("Running with multiprocessing...")
    start_time = time.time()
    run_multiprocessing(writer_config, num_processes, files_per_process)
    multiprocessing_duration = time.time() - start_time

    print("\nRunning without multiprocessing...")
    start_time = time.time()
    run_single_process(writer_config, num_processes, files_per_process)
    single_process_duration = time.time() - start_time
    print(f"Time taken with multiprocessing: {multiprocessing_duration:.2f} seconds")
    print(f"Time taken without multiprocessing: {single_process_duration:.2f} seconds")

    # Compare times
    time_difference = single_process_duration - multiprocessing_duration
    print(
        f"\nMultiprocessing was faster by {time_difference:.2f} seconds"
        if time_difference > 0
        else f"\nSingle process was faster by {-time_difference:.2f} seconds"
    )
    # Calculate and print the percentage improvement
    improvement_percentage = (time_difference / single_process_duration) * 100
    print(f"Multiprocessing improved the performance by {improvement_percentage:.2f}%")

    # Output:
    # 4 procs and 100 files per proc
    # Time taken with multiprocessing: 3.51 seconds
    # Time taken without multiprocessing: 13.16 seconds

    # Multiprocessing was faster by 9.65 seconds
    # Multiprocessing improved the performance by 73.31%
