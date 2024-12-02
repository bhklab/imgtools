# AutoPipeline Usage

To use AutoPipeline, follow the installation instructions found at <https://github.com/bhklab/med-imagetools#installing-med-imagetools>.

## Intro to AutoPipeline

AutoPipeline will crawl and process any DICOM dataset. To run the most basic variation of the script, run the following command:

```
autopipeline INPUT_DIRECTORY OUTPUT_DIRECTORY --modalities MODALITY_LIST
```

Replace INPUT_DIRECTORY with the directory containing all your DICOM data, OUTPUT_DIRECTORY with the directory that you want the data to be outputted to.

The `--modalities` option allows you to only process certain modalities that are present in the DICOM data. The available modalities are:

1. CT
2. MR
3. RTSTRUCT
4. PT    
5. RTDOSE

Set the modalities you want to use by separating each one with a comma. For example, to use CT and RTSTRUCT, run AutoPipeline with `--modalities CT,RTSTRUCT`

## AutoPipeline Flags
AutoPipeline comes with many built-in features to make your data processing easier:

1. **Spacing**

    The spacing for the output image. default = (1., 1., 0.). 0. spacing means maintaining the image's spacing as-is. Spacing of (0., 0., 0.,) will not resample any image.

    ```sh
    --spacing [Tuple: (int,int,int)]
    ```

2. **Parallel Job Execution**

    The number of jobs to be run in parallel. Set -1 to use all cores. default = -1

    ```sh
    --n_jobs [int]
    ```

3. **Dataset Graph Visualization (not recommended for large datasets)**

    Whether to visualize the entire dataset using PyViz.

    ```sh
    --visualize [flag]
    ```

4. **Continue Pipeline Processing**

    Whether to continue the most recent run of AutoPipeline that terminated prematurely for that output directory. Will only work if the `.imgtools` directory was not deleted from previous run. Using this flag will retain the same flags and parameters carried over from the previous run.

    ```sh
    --continue_processing [flag]
    ```

5. **Processing Dry Run**

    Whether to execute a dry run, only generating the .imgtools folder, which includes the crawled index.

    ```sh
    --dry_run [flag]
    ```

6. **Show Progress**

    Whether to print AutoPipeline progress to the standard output.

    ```sh
    --show_progress [flag]
    ```

7. **Warning on Subject Processing Errors**

    Whether to warn instead of error when processing subjects

    ```sh
    --warn_on_error [flag]
    ```

8. **Overwrite Existing Output Files**

    Whether to overwrite existing file outputs

    ```sh
    --overwrite [flag]
    ```

9. **Update existing crawled index**

    Whether to update existing crawled index

    ```sh
    --update [flag]
    ```



## Flags for parsing RTSTRUCT contours/regions of interest (ROI)
The contours can be selected by creating a YAML file to define a regular expression (regex), or list of potential contour names, or a combination of both. **If none of the flags are set or the YAML file does not exist, the AutoPipeline will default to processing every contour.**

1. **Defining YAML file path for contours**

    Whether to read a YAML file that defines regex or string options for contour names for regions of interest (ROI). By default, it will look for and read from `INPUT_DIRECTORY/roi_names.yaml`

    ```sh
    --read_yaml_label_names [flag]
    ```

    Path to the above-mentioned YAML file. Path can be absolute or relative. default = "" (each ROI will have its own label index in dataset.json for nnUNet)

    ```sh
    --roi_yaml_path [str]
    ```

2. **Defining contour selection behaviour**

    A typical ROI YAML file may look like this:
    ```yaml
    GTV: GTV*
    LUNG:
        - LUNG*
        - LNUG
        - POUMON*
    NODES:
        - IL1
        - IIL2
        - IIIL3
        - IVL4
    ```

    By default, **all ROIs** that match any of the regex or strings will be **saved as one label**. For example, GTVn, GTVp, GTVfoo will be saved as GTV. However, this is not always the desirable behaviour. 

    **Only select the first matching regex/string**

    The StructureSet iterates through the regex and string in the order it is written in the YAML. When this flag is set, once any contour matches the regex or string, the ROI search is interrupted and moves to the next ROI. This may be useful if you have a priority order of potentially matching contour names. 

    ```sh
    --roi_select_first [flag]
    ```

    If a patient has  contours `[GTVp, LNUG, IL1, IVL4]`, with the above YAML file and `--roi_select_first` flag set, it will only process `[GTVp, LNUG, IL1]` contours as `[GTV, LUNG, NODES]`, respectively. 

    **Process each matching contour as a separate ROI**

    Any matching contour will be saved separate with its contour name as a suffix to the ROI name. This will not apply to ROIs that only have one regex/string.
    
    ```sh
    --roi_separate [flag]
    ```
    If a patient had contours `[GTVp, LNUG, IL1, IVL4]`, with the above YAML file and `--roi_sepearate` flag set, it will process the contours as `[GTV, LUNG_LNUG, NODES_IL1, NODES_IVL4]`, respectively. 

3.  **Ignore patients with no contours**

    Ignore patients with no contours that match any of the defined regex or strings instead of throwing error. 

    ```sh
    --ignore_missing_regex [flag]
    ```

## Additional nnUNet-specific flags

1. **Format Output for nnUNet Training**

    Whether to format output for nnUNet training. Modalities must be CT,RTSTRUCT or MR,RTSTRUCT. `--modalities CT,RTSTRUCT` or `--modalities MR,RTSTRUCT`

    ```sh
    --nnunet [flag]
    ```

    ```sh
    OUTPUT_DIRECTORY
    ├── nnUNet_preprocessed
    ├── nnUNet_raw
    │   └── Dataset001_HNSCC
    │       ├── dataset.csv
    │       ├── dataset.json
    │       ├── imagesTr
    │       ├── imagesTs
    │       ├── labelsTr
    │       ├── labelsTs
    │       ├── markdown_images
    │       ├── nnunet_preprocess_and_train.sh
    │       └── report.md
    └── nnUNet_results
    ```

2. **Training Size**

    Training size of the train-test-split. default = 1.0 (all data will be in imagesTr/labelsTr)

    ```sh
    --train_size [float]
    ```

3. **Random State**

    Random state for the train-test-split. Uses sklearn's train_test_split(). default = 42

    ```sh
    --random_state [int]
    ```

4. **Custom Train-Test-Split YAML**

    Whether to use a custom train-test-split. Must be in a file found at `INPUT_DIRECTORY/custom_train_test_split.yaml`. All subjects not defined in this file will be randomly split to fill the defined value for `--train_size` (default = 1.0). File must conform to:

    ```yaml
    train:
        - subject_1
        - subject_2
        ...
    test:
        - subject_1
        - subject_2
        ...
    ```

    ```sh
    --custom_train_test_split [flag]
    ```

## Additional flags for nnUNet Inference

1. **Format Output for nnUNet Inference**

    Whether to format output for nnUNet Inference.

    ```sh
    --nnunet_inference [flag]
    ```

    ```sh
    OUTPUT_DIRECTORY
    ├── {DATASET}_{SUBJECT_NUM}_{MODALITY}.nii.gz
    └── ...
    ```

2. **Path to `dataset.json`**

    The path to the `dataset.json` file for nnUNet inference.

    ```sh
    --dataset_json_path [str]
    ```

    A dataset json file may look like this:
    ```json
    {
    "channel_names": { 
        "0": "CT"
    },
    "labels": {
        "background": 0,
        "GTV": 1
    },
    "numTraining": 5,
    "file_ending": ".nii.gz",
    "licence": "hands off!"
    }
    ```
