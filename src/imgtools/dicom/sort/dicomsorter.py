import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from os.path import commonpath
from pathlib import Path
from typing import Dict, List, Pattern, Set

from rich import progress
from rich.text import Text
from rich.tree import Tree

from imgtools.dicom import similar_tags, tag_exists
from imgtools.dicom.sort import (
    FileAction,
    InvalidDICOMKeyError,
    SorterBase,
    handle_file,
    resolve_path,
)

DEFAULT_PATTERN_PARSER: Pattern = re.compile(r"%([A-Za-z]+)|\{([A-Za-z]+)\}")


class DICOMSorter(SorterBase):
    """A specialized implementation of the `SorterBase` for sorting DICOM files by metadata.

    This class resolves paths for DICOM files based on specified
    target patterns, using metadata extracted from the files. The
    filename of each source file is preserved during this process.

    Attributes
    ----------
    source_directory : Path
        The directory containing the files to be sorted.
    logger : Logger
        The instance logger bound with the source directory context.
    dicom_files : list of Path
        The list of DICOM files found in the `source_directory`.
    format : str
        The parsed format string with placeholders for DICOM tags.
    keys : Set[str]
        DICOM tags extracted from the target pattern.
    invalid_keys : Set[str]
        DICOM tags from the pattern that are invalid.
    """

    def __init__(
        self,
        source_directory: Path,
        target_pattern: str,
        pattern_parser: Pattern = DEFAULT_PATTERN_PARSER,
    ) -> None:
        super().__init__(
            source_directory=source_directory,
            target_pattern=target_pattern,
            pattern_parser=pattern_parser,
        )
        self.logger.debug(
            "All DICOM Keys are Valid in target pattern", keys=self.keys
        )

    def validate_keys(self) -> None:
        """Validate the DICOM keys in the target pattern.

        If any invalid keys are found, it
        suggests similar valid keys and raises an error.
        """
        if not self.invalid_keys:
            return

        for key in sorted(self.invalid_keys):
            # TODO: keep this logic, but make the suggestion more user-friendly/readable
            similar = similar_tags(key)
            suggestion = (
                f"\n\tDid you mean: [bold green]{', '.join(similar)}[/bold green]?"
                if similar
                else " And [bold red]no similar keys[/bold red] found."
            )
            _error = (
                f"Invalid DICOM key: [bold red]{key}[/bold red].{suggestion}"
            )
            self._console.print(f"{_error}")
        self._console.print(f"Parsed Path: `{self.pattern_preview}`")
        errmsg = "Invalid DICOM Keys found."
        raise InvalidDICOMKeyError(errmsg)

    @property
    def invalid_keys(self) -> Set[str]:
        """Get the set of invalid keys.

        Essentially, this will check `pydicom.dictionary_has_tag` for each key
        in the pattern and return the set of keys that are invalid.

        Returns
        -------
        Set[str]
            The set of invalid keys.
        """
        return {key for key in self.keys if not tag_exists(key)}

    def execute(
        self,
        action: FileAction | str = FileAction.MOVE,
        overwrite: bool = False,
        dry_run: bool = False,
        num_workers: int = 1,
    ) -> None:
        """Execute the file action on DICOM files.

        Users are encouraged to use FileAction.HARDLINK for
        efficient storage and performance for large dataset, as well as
        protection against lost data.

        Using hard links can save disk space and improve performance by
        creating multiple directory entries (links) for a single file
        instead of duplicating the file content. This is particularly
        useful when working with large datasets, such as DICOM files,
        where storage efficiency is crucial.

        Parameters
        ----------
        action : FileAction, default: FileAction.MOVE
                The action to apply to the DICOM files (e.g., move, copy).
        overwrite : bool, default: False
                If True, overwrite existing files at the destination.
        dry_run : bool, default: False
                If True, perform a dry run without making any changes.
        num_workers : int, default: 1
                The number of worker threads to use for processing files.

        Raises
        ------
        ValueError
                If the provided action is not a valid FileAction.
        """
        if not isinstance(action, FileAction):
            action = FileAction.validate(action)

        self.logger.debug(
            f"Mapping {len(self.dicom_files)} files to new paths"
        )

        # Create a progress bar that can be used to track everything
        with self._progress_bar() as progress_bar:
            ################################################################################
            # Resolve new paths
            ################################################################################
            file_map: Dict[Path, Path] = self._resolve_new_paths(
                progress_bar=progress_bar, num_workers=num_workers
            )
        self.logger.info("Finished resolving paths")

        ################################################################################
        # Check if any of the resolved paths are duplicates
        ################################################################################
        file_map = self._check_duplicates(file_map)
        self.logger.info("Finished checking for duplicates")

        ################################################################################
        # Handle files
        ################################################################################
        if dry_run:
            self._dry_run(file_map)
            return

        with self._progress_bar() as progress_bar:
            task_files = progress_bar.add_task(
                "Handling files", total=len(file_map)
            )
            new_paths: List[Path | None] = []
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                future_to_file = {
                    executor.submit(
                        handle_file,
                        source_path,
                        resolved_path,
                        action,
                        overwrite,
                    ): source_path
                    for source_path, resolved_path in file_map.items()
                }
                for future in as_completed(future_to_file):
                    try:
                        result = future.result()
                        new_paths.append(result)
                        progress_bar.update(task_files, advance=1)
                    except Exception as e:
                        self.logger.exception(
                            "Failed to handle file",
                            exc_info=e,
                            file=future_to_file[future],
                        )

    def _check_duplicates(
        self, file_map: Dict[Path, Path]
    ) -> Dict[Path, Path]:
        """
        Check if any of the resolved paths are duplicates.

        Parameters
        ----------
        file_map : Dict[Path, Path]
            A dictionary mapping source paths to resolved paths.

        Returns
        -------
        Dict[Path, Path]
            A dictionary mapping source paths to resolved paths.

        Raises
        ------
        ValueError
            If any of the resolved paths are duplicates.
        """
        # opposite of the file_map
        # key: resolved path, value: list of source paths
        duplicate_paths: Dict[Path, List[Path]] = {}

        for source_path, resolved_path in file_map.items():
            if resolved_path in duplicate_paths:
                duplicate_paths[resolved_path].append(source_path)
            else:
                duplicate_paths[resolved_path] = [source_path]

        duplicates = False
        for resolved_path, source_paths in duplicate_paths.items():
            if len(source_paths) > 1:
                msg = f"Duplicate paths found for {resolved_path}: {source_paths}"
                self.logger.warning(msg)
                duplicates = True

        if duplicates:
            msg = "Duplicate paths found. Please check the log file for more information."
            raise ValueError(msg)

        return file_map

    def _resolve_new_paths(
        self, progress_bar: progress.Progress, num_workers: int = 1
    ) -> Dict[Path, Path]:
        """Resolve the new paths for all DICOM files using parallel processing.

        Parameters
        ----------
        progress_bar : progress.Progress
                Progress bar to use for tracking the progress of the operation.
        num_workers : int, default=1
                Number of threads to use for parallel processing.

        Returns
        -------
        Dict[Path, Path]
                A mapping of source paths to resolved paths.
        """
        task = progress_bar.add_task(
            "Resolving paths", total=len(self.dicom_files)
        )

        # Use ProcessPoolExecutor for parallel processing
        results: Dict[Path, Path] = {}
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            future_to_path = {
                executor.submit(
                    resolve_path, path, self.keys, self.format
                ): path
                for path in self.dicom_files
            }
            for future in as_completed(future_to_path):
                source, resolved = future.result()
                results[source] = resolved
                progress_bar.update(task, advance=1)

        return results

    def _dry_run(self, file_map: Dict[Path, Path]) -> None:
        """Perform a dry run without making any changes."""
        self._console.print(
            "[bold green]:double_exclamation_mark: Dry run mode enabled. No files will be moved or copied. :double_exclamation_mark: [/bold green]"
        )

        new_paths = sorted(list(file_map.values()))
        ppa = Path(self.pattern_preview).absolute()
        common_prefix: Path = self._common_prefix([ppa, *new_paths])
        common_prefix_styled = f"[bold yellow]{common_prefix}[/bold yellow]"
        self._console.print(
            f"\nCommon Prefix: :file_folder:{common_prefix_styled}\n\n"
        )

        tree = self._setup_tree(Path(common_prefix_styled))

        root = ppa.relative_to(common_prefix).as_posix()
        self._generate_tree_structure(
            root,
            tree,
        )
        self._build_tree(new_paths, tree, common_prefix)
        self._console.print(
            "[bold]Preview of the [magenta]parsed pattern[/magenta] and sample paths as directories:[/bold]\n"
        )
        self._console.print(tree)

    @staticmethod
    def _common_prefix(paths: List[Path]) -> Path:
        """Find the common prefix for a list of paths.

        Parameters
        ----------
        paths : List[Path]
            A list of paths.

        Returns
        -------
        str
            The common prefix of the paths.
        """
        return Path(
            commonpath(
                [str(path) for path in paths],
            ),
        )

    def _build_tree(
        self,
        paths: List[Path],
        tree: Tree,
        common_prefix: Path,
        max_children: int = 3,
    ) -> None:
        """
        Build a tree view given a set of paths (all having a common prefix).

        Parameters
        ----------
        paths : List[Path]
                        List of pathlib.Path objects representing the proposed paths.
        tree : Tree
                        A Rich Tree object where the directory structure will be added.
        common_prefix : Path
                        The common prefix for all paths. Used to normalize the input paths.
        """

        # Make all paths relative to the common prefix and sort them
        paths = [path.relative_to(common_prefix) for path in paths]
        # Create a dictionary to hold references to tree nodes
        node_map: Dict[Path, Tree] = {Path(): tree}  # Start with the root tree
        depth_counts: Dict[int, Set] = {
            0: set()
        }  # Track the number of nodes at each depth
        for path in paths:
            parts = list(path.parts)
            for depth, part in enumerate(parts):
                current_path = Path(*parts[: depth + 1])
                # Add the current path to the tree if it's not already in the map
                if current_path in node_map:
                    continue

                # add depth to the depth_counts
                depth_counts.setdefault(depth, set()).add(part)
                parent_path = Path(*parts[:depth])  # Determine parent path
                parent_node = node_map[parent_path]  # Get the parent Tree node

                if len(parent_node.children) < max_children:
                    # Add the current node to the tree
                    node_map[current_path] = parent_node.add(part)
                    break
                # Check if the parent has 3+ children already
                # If no "..." placeholder exists, add it and replace the 3rd child
                if not any(
                    child.label == "..." for child in parent_node.children
                ):
                    third_child = parent_node.children.pop(
                        2
                    )  # Remove the 3rd child
                    parent_node.add("...")  # Add the "..." placeholder
                    parent_node.add(third_child)  # Add the 3rd child back

                # Replace the last child after the "..." placeholder
                _ = parent_node.children.pop()  # Remove the last child
                node_map[current_path] = parent_node.add(part)
                break

        # Add counts to the first child and its children recursively
        def add_counts(node: Tree, depth: int) -> None:
            if depth in depth_counts:
                node.label = Text.assemble(
                    node.label,  # type: ignore
                    Text(
                        f" ({len(depth_counts[depth])} unique)",
                        style="bold green",
                    ),
                )
            for child in node.children:
                add_counts(child, depth + 1)

        add_counts(tree.children[0], 0)
