import pathlib
from typing import List

import click


def is_testdata_available() -> bool:
    try:
        from github import Github  # type: ignore # noqa

        return True
    except ImportError:
        return False


if is_testdata_available():
    from imgtools.datasets import MedImageTestData


@click.command()
@click.argument(
    "dest",
    type=click.Path(
        exists=False,
        file_okay=False,
        dir_okay=True,
        writable=True,
        path_type=pathlib.Path,
        resolve_path=True,
    ),
)
@click.option(
    "-a",
    "--assets",
    multiple=True,
    help="Specific assets to download. If not provided, all assets will be downloaded.",
)
@click.help_option(
    "-h",
    "--help",
)
def testdata(dest: pathlib.Path, assets: List[str]) -> None:
    """Download test data from the latest GitHub release.

    DEST is the directory where the test data will be saved.

    assets can be one of the following:

    \b
    - 4D-Lung.tar.gz
    - CC-Tumor-Heterogeneity.tar.gz
    - NSCLC-Radiomics.tar.gz
    - NSCLC_Radiogenomics.tar.gz
    - QIN-PROSTATE-Repeatability.tar.gz
    - Soft-tissue-Sarcoma.tar.gz
    - Vestibular-Schwannoma-SEG.tar.gz

    """
    manager = MedImageTestData()
    selected_assets = None

    if assets:
        selected_assets = [asset for asset in manager.datasets if asset.name in assets]
        if not selected_assets:
            click.echo(f"No matching assets found for: {', '.join(assets)}")
            return

    downloaded_files = manager.download(dest, assets=selected_assets)
    click.echo(f"Downloaded files: {', '.join(str(file) for file in downloaded_files)}")


if __name__ == "__main__":
    testdata()
