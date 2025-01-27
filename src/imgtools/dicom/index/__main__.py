from pathlib import Path

import click

from imgtools.cli import set_log_verbosity
from imgtools.dicom import find_dicoms
from imgtools.dicom.index import (
    DatabaseHandler,
    DICOMDatabaseInterface,
    DICOMIndexer,
)
from imgtools.logging import logger

DEFAULT_DB_DIR = Path(".imgtools")
DEFAULT_DB_NAME = "imgtools.db"


@click.command()
@set_log_verbosity()
@click.option(
    "--directory",
    "-d",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        path_type=Path,
    ),
    help="Directory to search for DICOM files",
    required=True,
)
@click.option(
    "--update-db",
    "-u",
    is_flag=True,
    help="Force update the database",
    default=False,
)
@click.option(
    "--limit",
    "-l",
    type=int,
    default=0,
    help="Number of files to index, 0 for all",
)
def index(
    directory: Path,
    update_db: bool = False,
    verbose: int = 0,
    quiet: bool = False,
    limit: int = 0,
) -> None:
    """Index DICOM files in a directory.

    For now, creates a database in the current directory at .imgtools/imgtools.db.

    """
    extension = "dcm"
    check_header = False
    logger.info("Searching for DICOM files.", args=locals())

    dicom_files = find_dicoms(
        directory=directory,
        check_header=check_header,
        recursive=True,
        extension=extension,
    )
    if not dicom_files:
        warningmsg = f"No DICOM files found in {directory}."
        logger.warning(
            warningmsg,
            directory=directory,
            check_header=check_header,
            recursive=True,
            extension=extension,
        )
        return

    logger.info("DICOM find successful.", count=len(dicom_files))

    db_path = DEFAULT_DB_DIR / DEFAULT_DB_NAME

    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_handler = DatabaseHandler(db_path=db_path, force_delete=update_db)

    indexer = DICOMIndexer(db_handler=db_handler)

    if limit:
        dicom_files = dicom_files[:limit]

    logger.debug("Building index.", count=len(dicom_files), limit=limit)
    # Build index
    indexer.build_index_from_files(dicom_files)

    _ = DICOMDatabaseInterface(db_handler=db_handler)

    logger.info("Indexing complete.")

    click.echo(f"Indexed {len(dicom_files)} files to {db_path}")


if __name__ == "__main__":
    index()
