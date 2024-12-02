# Preparing Data for nnUNet

nnUNet repo can be found at: <https://github.com/MIC-DKFZ/nnUNet>

## Processing DICOM Data with Med-ImageTools

Ensure that you have followed the steps in <https://github.com/bhklab/med-imagetools#installing-med-imagetools> before proceeding.

To convert your data from DICOM to NIfTI for training an nnUNet auto-segmentation model, run the following command:

```sh
autopipeline\
  [INPUT_DIRECTORY] \
  [OUTPUT_DIRECTORY] \
  --modalities CT,RTSTRUCT \
  --nnunet
```

Modalities can also be set to `--modalities MR,RTSTRUCT`

AutoPipeline offers many more options and features for you to customize your outputs: <<https://github.com/bhklab/med-imagetools/tree/main/README.md>  


## nnUNet Preprocess and Train

### One-Step Preprocess and Train

Med-ImageTools generates a file in your output folder called `nnunet_preprocess_and_train.sh` that combines all the commands needed for preprocessing and training your nnUNet model. Run that shell script to get a fully trained nnUNet model.

Alternatively, you can go through each step individually as follows below:

### nnUNet Preprocessing

Follow the instructions for setting up your paths for nnUNet: <https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/setting_up_paths.md>

Med-ImageTools generates the dataset.json that nnUNet requires in the output directory that you specify.

The generated output directory structure will look something like:

```sh
OUTPUT_DIRECTORY
├── nnUNet_preprocessed
├── nnUNet_raw
│   └── Dataset001_HNSCC
│       ├── nnunet_preprocess_and_train.sh
│       └── ...
└── nnUNet_results

```

nnUNet requires that environment variables be set before any commands are executed. To temporarily set them, run the following:

```sh
export nnUNet_raw="/OUTPUT_DIRECTORY/nnUNet_raw"
export nnUNet_preprocessed="/OUTPUT_DIRECTORY/nnUNet_preprocessed"
export nnUNet_results="/OUTPUT_DIRECTORY/nnUNet_results"
```

To permanently set these environment variables, make sure that in your `~/.bashrc` file, these environment variables are set for nnUNet. The `nnUNet_preprocessed` and `nnUNet_results` folders are generated as empty folders for you by Med-ImageTools. `nnUNet_raw` is populated with the required raw data files. Add this to the file:

```sh
export nnUNet_raw="/OUTPUT_DIRECTORY/nnUNet_raw"
export nnUNet_preprocessed="/OUTPUT_DIRECTORY/nnUNet_preprocessed"
export nnUNet_results=="/OUTPUT_DIRECTORY/nnUNet_results"
```

Then, execute the command:

```sh
source ~/.bashrc
```

Too allow nnUNet to preprocess your data for training, run the following command. Set X to the ID that you want to preprocess. This is your dataset ID. For example, for Dataset001_HNSCC, the dataset ID is 1. Dataset IDs must be between 1 and 999, so Med-ImageTools can run 999 instances with the `--nnunet` flag in a single output folder.

```sh
nnUNetv2_plan_and_preprocess -d X --verify_dataset_integrity -c 3d_fullres
```

### nnUNet Training

Once nnUNet has finished preprocessing, you may begin training your nnUNet model. To train your model, run the following command. Learn more about nnUNet's options here: <https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/how_to_use_nnunet.md>

```sh
nnUNetv2_train DATASET_NAME_OR_ID UNET_CONFIGURATION FOLD
```

## nnUNet Inference

For inference data, nnUNet requires data to be in a different output format. To run AutoPipeline for nnUNet inference, run the following command:

```sh
autopipeline\
  [INPUT_DIRECTORY] \
  [OUTPUT_DIRECTORY] \
  --modalities CT \
  --nnunet_inference \
  --dataset_json_path [DATASET_JSON_PATH]
```
To execute this command AutoPipeline needs a json file with the image modality definitions.

Modalities can also be set to `--modalities MR`.

The directory structue will look like:

```sh
    OUTPUT_DIRECTORY
    ├── {DATASET}_{SUBJECT_NUM}_{MODALITY}.nii.gz
    └── ...
```

To run inference, run the command:

```sh
nnUNetv2_predict -i INPUT_FOLDER -o OUTPUT_FOLDER -d DATASET_NAME_OR_ID -c CONFIGURATION
```

In this case, the `INPUT_FOLDER` of nnUNet is the `OUTPUT_DIRECTORY` of Med-ImageTools.