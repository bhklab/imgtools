from pathlib import Path

import pytest

from imgtools.datasets.github_helper import MedImageTestData


@pytest.fixture
def med_image_test_data():
    manager = MedImageTestData()
    _ = manager.get_latest_release()
    return manager


def test_get_latest_release(med_image_test_data):
    latest_release = med_image_test_data.get_latest_release()
    assert latest_release is not None
    assert latest_release.tag_name is not None
    assert latest_release.name is not None
    assert isinstance(latest_release.tag_name, str)
    assert isinstance(latest_release.name, str)


def test_extract(med_image_test_data, tmp_path):
    download_dir = tmp_path / "downloads"
    extract_dir = tmp_path / "extracted"

    release = med_image_test_data.get_latest_release()
    # assert release is at least 'v0.13'
    assert release.tag_name >= "v0.13"

    # chosen_assets = release.assets[:2]
    strings_of_interest = [
        "NSCLC-Radiomics",
        "NSCLC_Radiogenomics",
        "Vestibular-Schwannoma-SEG",
    ]
    chosen_assets = [
        asset
        for asset in release.assets
        if any(string in asset.name for string in strings_of_interest)
    ]

    med_image_test_data.download(download_dir, assets=chosen_assets)

    assert len(med_image_test_data.downloaded_paths) > 0
    for path in med_image_test_data.downloaded_paths:
        assert path.exists()
        assert path.is_file()

    extracted_paths = med_image_test_data.extract(extract_dir)
    assert len(extracted_paths) > 0
    for path in extracted_paths:
        assert path.exists()
        assert path.is_file() or path.is_dir()
        if path.is_file():
            assert path.suffix in [
                ".nii",
                ".nii.gz",
                ".dcm",
                ".jpg",
                ".png",
            ]  # Add other expected file types here
