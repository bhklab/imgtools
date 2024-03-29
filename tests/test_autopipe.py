import os, pathlib, shutil
from zipfile import ZipFile
from urllib import request
import subprocess
import pytest

@pytest.fixture(scope="session")
def dataset_path():
    curr_path = pathlib.Path(__file__).parent.parent.resolve()
    quebec_path = pathlib.Path(pathlib.Path(curr_path, "data", "Head-Neck-PET-CT").as_posix())
    output_path = pathlib.Path(curr_path, 'tests','temp').as_posix()

    if not os.path.exists(quebec_path):
        pathlib.Path(quebec_path).mkdir(parents=True, exist_ok=True)
        # Download QC dataset
        print("Downloading the test dataset...")
        quebec_data_url = "https://github.com/bhklab/tcia_samples/blob/main/Head-Neck-PET-CT.zip?raw=true"
        quebec_zip_path = pathlib.Path(quebec_path, "Head-Neck-PET-CT.zip").as_posix()
        request.urlretrieve(quebec_data_url, quebec_zip_path)
        with ZipFile(quebec_zip_path, 'r') as zipfile:
            zipfile.extractall(quebec_path)
        os.remove(quebec_zip_path)
    else:
        print("Data already downloaded...")
    
    quebec_path = quebec_path.as_posix()

    return quebec_path, output_path

@pytest.mark.parametrize("modalities", ["CT", "CT,RTSTRUCT", "CT,RTSTRUCT,RTDOSE"])#, "CT,RTDOSE,PT"])
def test_autopipe(dataset_path, modalities):
    quebec_path, output_path = dataset_path
    subprocess.run(["autopipeline", quebec_path, output_path, "--modalities", modalities, "--overwrite", "--update"], shell=True)
