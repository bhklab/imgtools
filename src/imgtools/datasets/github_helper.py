from __future__ import annotations

import asyncio
import os
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import aiohttp
from rich import print  # noqa
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

# create a single console for all progress bars, so they don't clutter the output
console = Console()


try:
    from github import Github  # type: ignore # noqa
    from github.Repository import Repository  # type: ignore # noqa
except ImportError as e:
    raise ImportError(
        "PyGithub is required for the test data feature of med-imagetools. "
        "Install it using 'pip install med-imagetools[test]'."
    ) from e


@dataclass
class GitHubReleaseAsset:
    """
    Represents an asset in a GitHub release.

    Attributes
    ----------
    name : str
        Name of the asset (e.g., 'dataset.zip').
    url : str
        Direct download URL for the asset.
    content_type : str
        MIME type of the asset (e.g., 'application/zip').
    size : int
        Size of the asset in bytes.
    download_count : int
        Number of times the asset has been downloaded.
    """

    name: str
    url: str
    content_type: str
    size: int
    download_count: int


@dataclass
class GitHubRelease:
    """
    Represents a GitHub release.

    Attributes
    ----------
    tag_name : str
        The Git tag associated with the release.
    name : str
        The name of the release.
    body : str
        Release notes or description.
    html_url : str
        URL to view the release on GitHub.
    created_at : str
        ISO 8601 timestamp of release creation.
    published_at : str
        ISO 8601 timestamp of release publication.
    assets : List[GitHubReleaseAsset]
        List of assets in the release.
    """

    tag_name: str
    name: str
    body: str
    html_url: str
    created_at: str
    published_at: str
    assets: List[GitHubReleaseAsset]


@dataclass
class GitHubReleaseManager:
    """
    Class to fetch and interact with datasets from the latest GitHub release.

    Attributes
    ----------
    repo_name : str
        The full name of the GitHub repository (e.g., 'user/repo').
    token : str | None
        Optional GitHub token for authenticated requests (higher rate limits).
    """

    repo_name: str
    github: Github
    repo: Repository
    latest_release: GitHubRelease

    # github parameters
    timeout = 300

    def __init__(self, repo_name: str, token: str | None = None) -> None:
        self.repo_name = repo_name
        token = token or os.environ.get("GITHUB_TOKEN")
        if token:
            print("Using token")
            self.github = Github(token, timeout=self.timeout)
        else:
            self.github = Github(timeout=self.timeout)

        self.repo = self.github.get_repo(repo_name)

    def get_release(self, tag: str = "latest") -> GitHubRelease:
        """
        Fetches the details of a specific release or the latest release if no tag is provided.

        Parameters
        ----------
        tag : str, optional
            The tag of the release to fetch. If 'latest', fetches the latest release.

        Returns
        -------
        GitHubRelease
            The details of the requested release.
        """
        if tag == "latest":
            release = self.repo.get_latest_release()
        else:
            release = self.repo.get_release(tag)

        assets = [
            GitHubReleaseAsset(
                name=asset.name,
                url=asset.browser_download_url,
                content_type=asset.content_type,
                size=asset.size,
                download_count=asset.download_count,
            )
            for asset in release.get_assets()
        ]

        return GitHubRelease(
            tag_name=release.tag_name,
            name=release.title,
            body=release.body or "",
            html_url=release.html_url,
            created_at=release.created_at.isoformat(),
            published_at=release.published_at.isoformat(),
            assets=assets,
        )

    def get_latest_release(self) -> GitHubRelease:
        """Fetches the latest release details from the repository."""
        self.latest_release = self.get_release("latest")
        return self.latest_release


async def download_dataset(
    download_link: str,
    file_path: Path,
    progress: Progress,
    timeout_seconds: int = 3600,
) -> Path:
    """
    Download a single dataset.

    Parameters
    ----------
    download_link : str
        The URL to download the dataset from.
    file_path : Path
        The path where the downloaded file will be saved.
    progress : Progress
        The progress bar to use for the download.
    timeout_seconds : int, optional
        The timeout for the download in seconds, by default 3600.

    Returns
    -------
    Path
        The path to the downloaded file.
    """
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(download_link) as response:
                total = int(response.headers.get("content-length", 0))
                task = progress.add_task(
                    f"[cyan]Downloading {file_path.name}...", total=total
                )
                with file_path.open("wb") as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))
        except asyncio.TimeoutError:
            console.print(
                f"[bold red]Timeout while downloading {file_path.name}. Please try again later.[/]"
            )
            raise
    return file_path


@dataclass
class MedImageTestData(GitHubReleaseManager):
    """
    Manager for downloading and extracting med-image test data from GitHub releases.
    """

    downloaded_paths: List[Path] = field(default_factory=list, init=False)
    progress: Progress = field(default_factory=Progress, init=False)

    def __init__(self) -> None:
        super().__init__("bhklab/med-image_test-data")
        self.downloaded_paths = []
        self.get_latest_release()

    @property
    def datasets(self) -> List[GitHubReleaseAsset]:
        return self.latest_release.assets

    @property
    def dataset_names(self) -> List[str]:
        return [asset.name for asset in self.datasets]

    async def _download_asset(
        self,
        session: aiohttp.ClientSession,
        asset: GitHubReleaseAsset,
        dest: Path,
        progress: Progress,
    ) -> Path:
        """
        Helper method to download a single asset asynchronously with a progress bar.

        Parameters
        ----------
        session : aiohttp.ClientSession
            The aiohttp session to use for the request.
        asset : GitHubReleaseAsset
            The asset to download.
        dest : Path
            Destination directory where the file will be saved.
        progress : Progress
            The progress bar to use for the download.

        Returns
        -------
        Path
            Path to the downloaded file.
        """
        dest.mkdir(parents=True, exist_ok=True)
        filepath = dest / asset.name

        if filepath.exists():
            print(f"File {asset.name} already exists. Skipping download.")
            return filepath

        return await download_dataset(asset.url, filepath, progress)

    async def _download(
        self,
        dest: Path,
        assets: List[GitHubReleaseAsset] | None,
        progress: Progress,
    ) -> List[Path]:
        """
        Download specified assets or all assets if none are specified.

        Parameters
        ----------
        dest : Path
            Destination directory where the files will be saved.
        assets : List[GitHubReleaseAsset], optional
            List of assets to download. If None, all assets will be downloaded.
        progress : Progress
            The progress bar to use for the download.

        Returns
        -------
        List[Path]
            List of paths to the downloaded files.
        """
        if assets is None:
            assets = self.latest_release.assets

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._download_asset(session, asset, dest, progress)
                for asset in assets
            ]
            self.downloaded_paths = await asyncio.gather(*tasks)
        return self.downloaded_paths

    def download_all(self, dest: Path) -> List[Path]:
        """
        Download all assets of the latest release synchronously.

        Parameters
        ----------
        dest : Path
            Destination directory where the files will be saved.

        Returns
        -------
        List[Path]
            List of paths to the downloaded files.
        """
        with Progress(
            TextColumn("[bold blue]{task.description}", justify="right"),
            BarColumn(),
            TaskProgressColumn(),
            DownloadColumn(),
            TextColumn("{task.completed}/{task.total} MB", justify="right"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            return asyncio.run(
                self._download(
                    dest,
                    assets=self.latest_release.assets,
                    progress=progress,
                )
            )

    def download(
        self, dest: Path, assets: Optional[List[GitHubReleaseAsset]] = None
    ) -> List[Path]:
        """
        Download specified assets synchronously.

        Parameters
        ----------
        dest : Path
            Destination directory where the files will be saved.
        assets : List[GitHubReleaseAsset], optional
            List of assets to download. If None, all assets will be downloaded.

        Returns
        -------
        List[Path]
            List of paths to the downloaded files.
        """
        print(f"Downloading assets to {dest}...")
        with Progress(
            TextColumn("[bold blue]{task.description}", justify="right"),
            BarColumn(),
            TaskProgressColumn(),
            DownloadColumn(),
            TextColumn("{task.completed}/{task.total} MB", justify="right"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            return asyncio.run(self._download(dest, assets, progress))

    def extract(self, dest: Path) -> List[Path]:
        """Extract downloaded archives to the specified directory."""
        if not self.downloaded_paths:
            raise ValueError(
                "No archives have been downloaded yet. Call `download_release_data` first."
            )

        extracted_paths = []
        for path in self.downloaded_paths:
            print(f"Extracting {path.name}...")
            if tarfile.is_tarfile(path):
                with tarfile.open(path, "r:*") as archive:
                    archive.extractall(dest, filter="data")
                    extracted_paths.extend(
                        [dest / member.name for member in archive.getmembers()]
                    )
            elif zipfile.is_zipfile(path):
                with zipfile.ZipFile(path, "r") as archive:
                    archive.extractall(dest)
                    extracted_paths.extend(
                        [dest / name for name in archive.namelist()]
                    )
            else:
                print(f"Unsupported archive format: {path.name}")
        return extracted_paths


# Usage example
if __name__ == "__main__":
    manager = MedImageTestData()

    print(manager)

    old_release_tag = "v0.11"
    old_release = manager.get_release(old_release_tag)
    print(old_release)

    chosen_assets = old_release.assets[:2]

    dest_dir = Path("data")
    downloaded_files = manager.download(dest_dir, assets=chosen_assets)
