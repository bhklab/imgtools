import click

from imgtools import __version__

from . import set_log_verbosity
from .dicomfind import find_dicoms
from .dicomsort import dicomsort
from .testdatasets import is_testdata_available


@click.group(
    no_args_is_help=True,
)
@set_log_verbosity()
@click.version_option(
    version=__version__,
    package_name="med-imagetools",
    prog_name="imgtools",
    message="%(package)s:%(prog)s:%(version)s",
)
@click.help_option(
    "-h",
    "--help",
)
def cli(verbose: int, quiet: bool) -> None:
    """A collection of tools for working with medical imaging data."""
    pass


cli.add_command(dicomsort)
cli.add_command(find_dicoms, "find-dicoms")

if is_testdata_available():
    from .testdatasets import testdata

    cli.add_command(testdata)

if __name__ == "__main__":
    cli()
