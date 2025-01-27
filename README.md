<div align="center">

# Med-Imagetools: Transparent and Reproducible Medical Image Processing Pipelines in Python


[![CI/CD Status](https://github.com/bhklab/med-imagetools/actions/workflows/main.yml/badge.svg)](https://github.com/bhklab/med-imagetools/actions/workflows/main.yml)
![GitHub repo size](https://img.shields.io/github/repo-size/bhklab/med-imagetools)
![GitHub contributors](https://img.shields.io/github/contributors/bhklab/med-imagetools)
![GitHub stars](https://img.shields.io/github/stars/bhklab/med-imagetools?style=social)
![GitHub forks](https://img.shields.io/github/forks/bhklab/med-imagetools?style=social)
[![Documentation Status](https://readthedocs.org/projects/med-imagetools/badge/?version=documentation)](https://med-imagetools.readthedocs.io/en/documentation/?badge=documentation)
![DOI Status](https://zenodo.org/badge/243786996.svg)

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/med-imagetools)](https://pypi.org/project/med-imagetools/)
[![PyPI - Version](https://img.shields.io/pypi/v/med-imagetools)](https://pypi.org/project/med-imagetools/)

[![PyPI - Format](https://img.shields.io/pypi/format/med-imagetools)](https://pypi.org/project/med-imagetools/)
[![Downloads](https://static.pepy.tech/badge/med-imagetools)](https://pepy.tech/project/med-imagetools)

</div>
<!--intro-start-->
## Med-ImageTools core features

* AutoPipeline CLI
* `nnunet` nnU-Net compatibility mode
* Built-in train/test split for both normal/nnU-Net modes
* `random_state` for reproducible seeds
* Region of interest (ROI) yaml dictionary intake for RTSTRUCT processing
* Markdown report output post-processing
* `continue_processing` flag to continue autopipeline
* `dry_run` flag to only crawl the dataset

Med-Imagetools, a python package offers the perfect tool to transform messy medical dataset folders to deep learning ready format in few lines of code. It not only processes DICOMs consisting of different modalities (like CT, PET, RTDOSE and RTSTRUCTS), it also transforms them into deep learning ready subject based format taking the dependencies of these modalities into consideration.  

## Introduction

A medical dataset, typically contains multiple different types of scans for a single patient in a single study. As seen in the figure below, the different scans containing DICOM of different modalities are interdependent on each other. For making effective machine learning models, one ought to take different modalities into account.

![graph](https://github.com/bhklab/med-imagetools/blob/main/images/graph.png?raw=true)

Fig.1 - Different network topology for different studies of different patients

Med-Imagetools is a unique tool, which focuses on subject based Machine learning. It crawls the dataset and makes a network by connecting different modalities present in the dataset. Based on the user defined modalities, med-imagetools, queries the graph and process the queried raw DICOMS. The processed DICOMS are saved as nrrds, which med-imagetools converts to torchio subject dataset and eventually torch dataloader for ML pipeline.

![graph](https://github.com/bhklab/med-imagetools/blob/main/images/autopipeline.png?raw=true)

Fig.2 - Med-Imagetools AutoPipeline diagram

## Installing med-imagetools

```console
pip install med-imagetools
```

### (recommended) Create new conda virtual environment

```console
conda create -n mit
conda activate mit
pip install med-imagetools
```

### (optional) Install in development mode

```console
conda create -n mit
conda activate mit
pip install -e git+https://github.com/bhklab/med-imagetools.git
```

This will install the package in editable mode, so that the installed package will update when the code is changed.
<!--intro-end-->
## Latest Updates Nov 21st, 2024

### New CLI entry point `imgtools`

![imgtools](https://github.com/bhklab/med-imagetools/blob/main/images/imgtools_help.png?raw=true)

### Feature: DICOMSort

> [!WARNING]
> **Warning**: This feature is still in beta. Use with caution and report any issues on [GitHub](https://github.com/bhklab/med-imagetools/issues).

![imgtools](https://github.com/bhklab/med-imagetools/blob/main/images/dicomsort_help.png?raw=true)

## Latest Updates (v1.2.0) - Feb 5th, 2024

* Documentation is now available at: [https://med-imagetools.readthedocs.io](https://med-imagetools.readthedocs.io)
* Dependencies have been reduced for a lighter install. `torch` and `torchio` dependencies have been moved to an extra pip install flag. Use `pip install med-imagetools[torch]`.

## Getting Started

Med-Imagetools takes two step approch to turn messy medical raw dataset to ML ready dataset.  

1. ***Autopipeline***: Crawls the raw dataset, forms a network and performs graph query, based on the user defined modalities. The relevant DICOMS, get processed and saved as nrrds

    ```console
    autopipeline\
      [INPUT DIRECTORY] \
      [OUTPUT DIRECTORY] \
      --modalities [str: CT,RTSTRUCT,PT] \
      --spacing [Tuple: (int,int,int)]\
      --n_jobs [int]\
      --visualize [flag]\
      --nnunet [flag]\
      --train_size [float]\
      --random_state [int]\
      --roi_yaml_path [str]\
      --continue_processing [flag]\
      --dry_run [flag]
    ```

2. ***class Dataset***: This class converts processed nrrds to torchio subjects, which can be easily converted to torch dataset

    ```console
    from imgtools.io import Dataset
    
    subjects = Dataset.load_from_nrrd(output_directory, ignore_multi=True)
    data_set = tio.SubjectsDataset(subjects)
    data_loader = torch.utils.data.DataLoader(data_set, batch_size=4, shuffle=True, num_workers=4)
    ```

## Demo (Outdated as of v0.4)

These google collab notebooks will introduce the main functionalities of med-imagetools. More information can be found [here](https://github.com/bhklab/med-imagetools/blob/master/examples/README.md)

### Tutorial 1: Forming Dataset with med-imagetools Autopipeline

[![Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/skim2257/tcia_samples/blob/main/notebooks/Tutorial_1_Forming_Dataset_with_Med_Imagetools.ipynb)

### Tutorial 2: Machine Learning with med-imagetools and torchio

[![Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/skim2257/tcia_samples/blob/main/notebooks/Tutorial_2_Machine_Learning_with_Med_Imagetools_and_torchio.ipynb)

## Contributors

Thanks to the following people who have contributed to this project:

* [@mkazmier](https://github.com/mkazmier)
* [@skim2257](https://github.com/skim2257)
* [@fishingguy456](https://github.com/fishingguy456)
* [@Vishwesh4](https://github.com/Vishwesh4)
* [@mnakano](https://github.com/mnakano)

## License

This project uses the following license: [MIT License](https://github.com/bhklab/med-imagetools/blob/master/LICENSE)
