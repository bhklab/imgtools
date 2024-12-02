from typing import Tuple, Dict
import pathlib, json
import matplotlib.pyplot as plt

def markdown_report_images(
    output_folder: str | pathlib.Path, 
    modality_count: Dict[str, int], 
    train_total: int, 
    test_total: int) -> None:
    output_folder = pathlib.Path(output_folder)
    images_folder = output_folder / "markdown_images"

    images_folder.mkdir(parents=True, exist_ok=True)

    # Bar plot for modality counts
    modalities = list(modality_count.keys())
    modality_totals = list(modality_count.values())
    plt.figure()  
    plt.bar(modalities, modality_totals)
    plt.title("Modality Counts")
    plt.xlabel("Modalities")
    plt.ylabel("Counts")
    plt.savefig(images_folder / "nnunet_modality_count.png")
    plt.close()  

    # Pie chart for train/test distribution
    plt.figure()
    plt.pie(
        [train_total, test_total],
        labels=[f"Train - {train_total}", f"Test - {test_total}"],
        autopct='%1.1f%%', 
    )
    plt.title("Train/Test Distribution")
    plt.savefig(images_folder / "nnunet_train_test_pie.png")
    plt.close()


def save_json(
    obj: dict,
    file: str | pathlib.Path,  
    indent: int = 4, 
    sort_keys: bool = True) -> None:
    with open(file, 'w') as f:
        json.dump(obj, f, sort_keys=sort_keys, indent=indent)

def create_train_script(
        output_directory: str | pathlib.Path,
        dataset_id: int):
    """
    Creates a bash script (`nnunet_preprocess_and_train.sh`) for running nnUNet training, with paths for raw data,
    preprocessed data, and trained models. The script ensures environment variables are set and 
    executes the necessary training commands.

    Parameters:
    - output_directory (str): The directory where the output and subdirectories are located.
    - dataset_id (int): The ID of the dataset to be processed.
    """
    # Define paths using pathlib
    output_directory = pathlib.Path(output_directory)
    shell_path = output_directory / 'nnunet_preprocess_and_train.sh'
    base_dir = output_directory.parent.parent

    if shell_path.exists():
        shell_path.unlink()

    # Define the environment variables and the script commands
    script_content = f"""#!/bin/bash
set -e

export nnUNet_raw="{base_dir}/nnUNet_raw"
export nnUNet_preprocessed="{base_dir}/nnUNet_preprocessed"
export nnUNet_results="{base_dir}/nnUNet_results"

nnUNetv2_plan_and_preprocess -d {dataset_id} --verify_dataset_integrity -c 3d_fullres

for (( i=0; i<5; i++ ))
do
    nnUNetv2_train {dataset_id} 3d_fullres $i
done
"""

    # Write the script content to the file
    with shell_path.open("w", newline="\n") as f:
        f.write(script_content)

# Code take from: https://github.com/MIC-DKFZ/nnUNet/blob/master/nnunetv2/dataset_conversion/generate_dataset_json.py

def generate_dataset_json(output_folder: str,
                          channel_names: Dict[str, str],
                          labels: Dict[str, int],
                          num_training_cases: int,
                          file_ending: str,
                          regions_class_order: Tuple[int, ...] = None,
                          dataset_name: str = None, 
                          reference: str = None, 
                          release: str = None, 
                          usage_license: str = 'hands off!',
                          description: str = None,
                          overwrite_image_reader_writer: str = None, 
                          **kwargs):
    """
    Generates a dataset.json file in the output folder

    channel_names:
        Channel names must map the index to the name of the channel, example:
        {
            0: 'T1',
            1: 'CT'
        }
        Note that the channel names may influence the normalization scheme!! Learn more in the documentation.

    labels:
        This will tell nnU-Net what labels to expect. Important: This will also determine whether you use region-based training or not.
        Example regular labels:
        {
            'background': 0,
            'left atrium': 1,
            'some other label': 2
        }
        Example region-based training:
        {
            'background': 0,
            'whole tumor': (1, 2, 3),
            'tumor core': (2, 3),
            'enhancing tumor': 3
        }

        Remember that nnU-Net expects consecutive values for labels! nnU-Net also expects 0 to be background!

    num_training_cases: is used to double check all cases are there!

    file_ending: needed for finding the files correctly. IMPORTANT! File endings must match between images and
    segmentations!

    dataset_name, reference, release, license, description: self-explanatory and not used by nnU-Net. Just for
    completeness and as a reminder that these would be great!

    overwrite_image_reader_writer: If you need a special IO class for your dataset you can derive it from
    BaseReaderWriter, place it into nnunet.imageio and reference it here by name

    kwargs: whatever you put here will be placed in the dataset.json as well

    """

    has_regions: bool = any([isinstance(i, (tuple, list)) and len(i) > 1 for i in labels.values()])
    if has_regions:
        assert regions_class_order is not None, "You have defined regions but regions_class_order is not set. " \
                                                "You need that."

    # Construct the dataset JSON structure  
    dataset_json = {  
        "channel_names": channel_names,  
        "labels": labels,  
        "numTraining": num_training_cases,  
        "file_ending": file_ending,  
        "name": dataset_name,  
        "reference": reference,  
        "release": release,  
        "licence": usage_license,  
        "description": description,  
        "overwrite_image_reader_writer": overwrite_image_reader_writer,  
        "regions_class_order": regions_class_order,  
    }   

    dataset_json = {k: v for k, v in dataset_json.items() if v is not None}  

    dataset_json.update(kwargs) 

    save_json(dataset_json, pathlib.Path(output_folder) / 'dataset.json', sort_keys=False)