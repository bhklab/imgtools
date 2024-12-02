from aifc import Error
import os
import pathlib
import shutil
import glob
import pickle
import numpy as np
import warnings

import yaml
import json
import SimpleITK as sitk

from imgtools.ops import StructureSetToSegmentation, ImageAutoInput, ImageAutoOutput, Resample
from imgtools.pipeline import Pipeline
from imgtools.utils.nnunet import generate_dataset_json, create_train_script, markdown_report_images
from imgtools.utils.args import parser
from imgtools.logging import logger

from joblib import Parallel, delayed
from imgtools.modules import Segmentation
from sklearn.model_selection import train_test_split

import dill
###############################################################
# Example usage:
# python radcure_simple.py ./data/RADCURE/data ./RADCURE_output
###############################################################


class AutoPipeline(Pipeline):
    """Example processing pipeline for the RADCURE dataset.
    This pipeline loads the CT images and structure sets, re-samples the images,
    and draws the GTV contour using the resampled image.
    """

    def __init__(self,
                 input_directory="",
                 output_directory="",
                 modalities="CT",
                 spacing=(1., 1., 0.),
                 n_jobs=-1,
                 visualize=False,
                 missing_strategy="drop",
                 show_progress=False,
                 warn_on_error=False,
                 overwrite=False,
                 nnunet=False,
                 train_size=1.0,
                 random_state=42,
                 read_yaml_label_names=False,
                 ignore_missing_regex=False,
                 roi_yaml_path="",
                 custom_train_test_split=False,
                 nnunet_inference=False,
                 dataset_json_path="",
                 continue_processing=False,
                 dry_run=False,
                 verbose=False,
                 update=False,
                 roi_select_first=False,
                 roi_separate=False):
        """Initialize the pipeline.

        Parameters
        ----------
        input_directory: str
            Directory containing the input data
        output_directory: str
            Directory where the output data will be stored
        modalities: str, default="CT"
            Modalities to load. Can be a comma-separated list of modalities with no spaces
        spacing: tuple of floats, default=(1., 1., 0.)
            Spacing of the output image
        n_jobs: int, default=-1
            Number of jobs to run in parallel. If -1, use all cores
        visualize: bool, default=False
            Whether to visualize the results of the pipeline using pyvis. Outputs to an HTML file
        missing_strategy: str, default="drop"
            How to handle missing modalities. Can be "drop" or "fill"
        show_progress: bool, default=False
            Whether to show progress bars
        warn_on_error: bool, default=False
            Whether to warn on errors
        overwrite: bool, default=False
            Whether to write output files even if existing output files exist
        nnunet: bool, default=False
            Whether to format the output for nnunet
        train_size: float, default=1.0
            Proportion of the dataset to use for training, as a decimal
        random_state: int, default=42
            Random state for train_test_split
        read_yaml_label_names: bool, default=False
            Whether to read dictionary representing the label that regexes are mapped to from YAML. For example, "GTV": "GTV.*" will combine all regexes that match "GTV.*" into "GTV"
        ignore_missing_regex: bool, default=False
            Whether to ignore missing regexes. Will raise an error if none of the regexes in label_names are found for a patient
        roi_yaml_path: str, default=""
            The path to the yaml file defining regexes
        custom_train_test_split: bool, default=False
            Whether to use a custom train/test split. The remaining patients will be randomly split using train_size and random_state
        nnunet_inference: bool, default=False
            Whether to format the output for nnUNet inference
        dataset_json_path: str, default=""
            The path to the dataset.json file for nnUNet inference
        continue_processing: bool, default=False
            Whether to continue processing a partially processed dataset
        dry_run: bool, default=False
            Whether to run the pipeline without writing any output files
        """

        self.continue_processing = continue_processing
        self.dry_run = dry_run
        self.v = verbose

        if dry_run:
            nnunet = False
            nnunet_inference = False

        if dry_run and continue_processing:
            raise ValueError("Cannot continue processing a dry run. Set --continue_processing to False to do a dry run.")

        if not dry_run and output_directory == "":
            raise ValueError("Must specify an output directory")
        
        # input/output directory configuration
        if not os.path.isabs(input_directory):
            input_directory = pathlib.Path(os.getcwd(), input_directory).as_posix()
        else:
            input_directory = pathlib.Path(input_directory).as_posix()  # consistent parsing. ensures last child directory doesn't end with slash
        
        if not os.path.isabs(output_directory):
            output_directory = pathlib.Path(os.getcwd(), output_directory).as_posix()
        else:
            output_directory = pathlib.Path(output_directory).as_posix()  # consistent parsing. ensures last child directory doesn't end with slash

        # check/make output directory
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        # check input directory exists
        if not os.path.exists(input_directory):
            raise FileNotFoundError(f"Input directory {input_directory} does not exist")
        
        self.input_directory = pathlib.Path(input_directory).as_posix()
        self.output_directory = pathlib.Path(output_directory).as_posix()
        
        # if wanting to continue processing but no .temp folders
        if not nnunet and continue_processing and not os.path.exists(pathlib.Path(output_directory, ".temp").as_posix()):
            raise FileNotFoundError(f"Cannot continue processing. .temp directory does not exist in {output_directory}. Run without --continue_processing to start from scratch.")

        if nnunet_inference:
            roi_yaml_path = ""
            custom_train_test_split = False
            nnunet = False
            if modalities != "CT" and modalities != "MR":
                raise ValueError("nnUNet inference can only be run on image files. Please set modalities to 'CT' or 'MR'")
        if nnunet:
        
            pathlib.Path(self.output_directory, "nnUNet_results").mkdir(parents=True, exist_ok=True)
            pathlib.Path(self.output_directory, "nnUNet_preprocessed").mkdir(parents=True, exist_ok=True)
            raw_path = pathlib.Path(self.output_directory, "nnUNet_raw")
            raw_path.mkdir(parents=True, exist_ok=True)
            self.output_directory = raw_path.as_posix()

            all_nnunet_folders = glob.glob(pathlib.Path(self.output_directory, "*", " ").as_posix())

            # Extract used dataset IDs from folder names that match the "Dataset###_" format
            used_ids = {
                int(pathlib.Path(folder).parent.parent.name[7:10]) 
                for folder in all_nnunet_folders
                if pathlib.Path(folder).parent.parent.name.startswith("Dataset")
            }

            study_name = pathlib.Path(self.input_directory).name
            new_dataset_required = (
                not used_ids  # No existing datasets
                or not continue_processing  # Processing shouldn't continue with existing datasets
                or not pathlib.Path(self.output_directory, f"Dataset{max(used_ids):03}_{study_name}", ".temp").exists()  # Temp folder missing
            )

            if new_dataset_required:
                all_ids = set(range(1, 1000))
                available_ids = sorted(all_ids - used_ids)
                if not available_ids:
                    raise ValueError(
                        "There are not enough dataset IDs for the nnUNet output. "
                        "Please ensure at least one dataset ID is available between 001 and 999, inclusive."
                    )
                dataset_id = available_ids[0]  # Assign the first available dataset ID
            else:
                dataset_id = max(used_ids)  # Reuse the highest existing dataset ID

            self.dataset_id = dataset_id 

            # Create the dataset folder name and update the output directory path
            dataset_folder_name = f"Dataset{self.dataset_id:03}_{study_name}"
            self.output_directory = pathlib.Path(self.output_directory, dataset_folder_name).as_posix()

            temp_folder_path = pathlib.Path(self.output_directory, ".temp")
            temp_folder_path.mkdir(parents=True, exist_ok=True)
        
        if not dry_run:
            # Make a directory
            if not os.path.exists(pathlib.Path(self.output_directory,".temp").as_posix()):
                os.mkdir(pathlib.Path(self.output_directory,".temp").as_posix())
                
            with open(pathlib.Path(self.output_directory, ".temp", "init_parameters.pkl").as_posix(), "wb") as f:
                parameters = locals()  # save all the parameters in case we need to continue processing
                dill.dump(parameters, f)

            # continue processing operations
            self.finished_subjects = [pathlib.Path(e).name[:-4] for e in glob.glob(pathlib.Path(self.output_directory, ".temp", "*.pkl").as_posix())]  # remove the .pkl
            

        super().__init__(n_jobs=n_jobs,
                         missing_strategy=missing_strategy,
                         show_progress=show_progress,
                         warn_on_error=warn_on_error)
        self.overwrite = overwrite
        self.spacing = spacing
        self.existing = [None]   # self.existing_patients()
        self.is_nnunet = nnunet
        if nnunet or nnunet_inference:
            self.nnunet_info = {}
        else:
            self.nnunet_info = None
        self.train_size = train_size
        self.random_state = random_state
        self.label_names = {}
        self.ignore_missing_regex = ignore_missing_regex
        self.custom_train_test_split = custom_train_test_split
        self.is_nnunet_inference = nnunet_inference
        self.roi_select_first = roi_select_first
        self.roi_separate = roi_separate

        if roi_yaml_path != "" and not read_yaml_label_names:
            warnings.warn("The YAML will not be read since it has not been specified to read them. To use the file, run the CLI with --read_yaml_label_names")

        roi_path = pathlib.Path(self.input_directory, "roi_names.yaml").as_posix() if roi_yaml_path == "" else roi_yaml_path
        if read_yaml_label_names:
            if os.path.exists(roi_path):
                with open(roi_path, "r") as f:
                    try:
                        self.label_names = yaml.safe_load(f)
                    except yaml.YAMLError as exc:
                        print(exc)
            else:
                raise FileNotFoundError(f"No file named roi_names.yaml found at {roi_path}. If you did not intend on creating ROI regexes, run the CLI without --read_yaml_label_names")
        
        if not isinstance(self.label_names, dict):
            raise ValueError("roi_names.yaml must parse as a dictionary")

        for k, v in self.label_names.items():
            if not isinstance(v, list) and not isinstance(v, str):
                raise ValueError(f"Label values must be either a list of strings or a string. Got {v} for {k}")
            elif isinstance(v, list):
                for a in v:
                    if not isinstance(a, str):
                        raise ValueError(f"Label values must be either a list of strings or a string. Got {a} in list {v} for {k}")
            elif not isinstance(k, str):
                raise ValueError(f"Label names must be a string. Got {k} for {v}")

        if self.train_size == 1.0 and nnunet:
            warnings.warn("Train size is 1, all data will be used for training")
        
        if self.train_size == 0.0 and nnunet:
            warnings.warn("Train size is 0, all data will be used for testing")

        if self.train_size != 1 and not nnunet:
            warnings.warn("Cannot run train/test split without nnunet, ignoring train_size")

        if self.train_size > 1 or self.train_size < 0 and nnunet:
            raise ValueError("train_size must be between 0 and 1")
        
        if nnunet and (not read_yaml_label_names or self.label_names == {}):
            raise ValueError("YAML label names must be provided for nnunet")
        
        if custom_train_test_split and not nnunet:
            raise ValueError("Cannot use custom train/test split without nnunet")

        custom_train_test_split_path = pathlib.Path(self.input_directory, "custom_train_test_split.yaml").as_posix()
        if custom_train_test_split and nnunet:
            if os.path.exists(custom_train_test_split_path):
                with open(custom_train_test_split_path, "r") as f:
                    try:
                        self.custom_split = yaml.safe_load(f)
                        if isinstance(self.custom_split, list):
                            for e in self.custom_split:
                                if not isinstance(e, str):
                                    raise ValueError("Custom split must be a list of strings. Place quotes around patient ID's that don't parse as YAML strings")
                            self.custom_split = {"train": [], "test": self.custom_split}
                        if isinstance(self.custom_split, dict):
                            if sorted(list(self.custom_split.keys())) != ["test", "train"] and list(self.custom_split.keys()) != ["train"] and list(self.custom_split.keys()) != ["test"]:
                                raise ValueError("Custom split must be a dictionary with keys 'train' and 'test'")
                            for k, v in self.custom_split.items():
                                if not isinstance(v, list):
                                    raise ValueError(f"Custom split must be a list of strings. Place quotes around patient ID's that don't parse as YAML strings. Got {v} for {k}")
                                for e in v:
                                    if not isinstance(e, str):
                                        raise ValueError("Custom split must be a list of strings. Place quotes around patient ID's that don't parse as YAML strings")
                            if list(self.custom_split.keys()) == ["train"]:
                                self.custom_split = {"train": self.custom_split["train"], "test": []}
                            elif list(self.custom_split.keys()) == ["test"]:
                                self.custom_split = {"train": [], "test": self.custom_split["test"]}
                        for e in self.custom_split["train"]:
                            if e in self.custom_split["test"]:
                                raise ValueError("Custom split cannot contain the same patient ID in both train and test")
                    except yaml.YAMLError as exc:
                        print(exc)
            else:
                raise FileNotFoundError(f"No file named custom_train_test_split.yaml found at {custom_train_test_split_path}. If you did not intend on creating a custom train-test-split, run the CLI without --custom_train_test_split")

        if self.is_nnunet:
            self.nnunet_info["modalities"] = {"CT": "0000"}  # modality to 4-digit code

        if nnunet_inference:
            if not os.path.exists(dataset_json_path):
                raise FileNotFoundError(f"No file named {dataset_json_path} found. Image modality definitions are required for nnUNet inference")
            else:
                with open(dataset_json_path, "r") as f:
                    self.nnunet_info["modalities"] = {v: k.zfill(4) for k, v in json.load(f)["channel_names"].items()}

        # Input operations
        self.input = ImageAutoInput(input_directory, modalities, n_jobs, visualize, update)
        self.output_df_path = pathlib.Path(self.output_directory, "dataset.csv").as_posix()

        # Output component table
        self.output_df = self.input.df_combined

        # Name of the important columns which needs to be saved
        self.output_streams = self.input.output_streams
        
        # image processing ops
        self.resample = Resample(spacing=self.spacing)
        self.make_binary_mask = StructureSetToSegmentation(roi_names=self.label_names, continuous=False)

        # output ops
        self.output = ImageAutoOutput(self.output_directory, self.output_streams, self.nnunet_info, self.is_nnunet_inference)
        
        self.existing_roi_indices = {"background": 0}
        if nnunet or nnunet_inference:
            self.total_modality_counter = {}
            self.patients_with_missing_labels = set()

    def glob_checker_nnunet(self, subject_id):
        folder_names = ["imagesTr", "labelsTr", "imagesTs", "labelsTs"]
        files = []
        for folder_name in folder_names:
            if os.path.exists(pathlib.Path(self.input_directory, folder_name).as_posix()):
                files.extend(glob.glob(pathlib.Path(self.output_directory,folder_name,"*.nii.gz").as_posix()))
        for f in files:
            if f.startswith(subject_id):
                return True
        return False

    def process_one_subject(self, subject_id):
        """Define the processing operations for one subject.
        This method must be defined for all pipelines. It is used to define
        the preprocessing steps for a single subject (note: that might mean
        multiple images, structures, etc.). During pipeline execution, this
        method will receive one argument, subject_id, which can be used to
        retrieve inputs and save outputs.

        Parameters
        ----------
        subject_id : str
           The ID of subject to process
        """
        if self.continue_processing:
            if subject_id in self.finished_subjects:
                return
        # if we want overwriting or if we don't want it and the file doesn't exist, we can process
        if self.overwrite or (not self.overwrite and not (os.path.exists(pathlib.Path(self.output_directory, subject_id).as_posix()) or self.glob_checker_nnunet(subject_id))):
            # Check if the subject_id has already been processed
            if os.path.exists(pathlib.Path(self.output_directory,".temp",f'temp_{subject_id}.pkl').as_posix()):
                print(f"{subject_id} already processed")
                return
            print("Processing:", subject_id)

            read_results = self.input(subject_id)
            # print(read_results)

            print(subject_id, " start")
            
            metadata = {}
            subject_modalities = set()  # all the modalities that this subject has
            num_rtstructs = 0

            for i, colname in enumerate(self.output_streams):  # sorted(self.output_streams)):  # CT comes before MR before PT before RTDOSE before RTSTRUCT
                modality = colname.split("_")[0]
                subject_modalities.add(modality)  # set add
                
                # Taking modality pairs if it exists till _{num}
                output_stream = ("_").join([item for item in colname.split("_") if not item.isnumeric()])

                # If there are multiple connections existing, multiple connections means two modalities connected to one modality. They end with _1
                # mult_conn = colname.split("_")[-1].isnumeric()
                # num = colname.split("_")[-1]

                if self.v:
                    print("output_stream:", output_stream)

                if read_results[i] is None:
                    print("The subject id: {} has no {}".format(subject_id, colname))
                    pass

                # Process image (CT/MR)
                elif modality == "CT" or modality == 'MR':
                    image = read_results[i].image
                    if len(image.GetSize()) == 4:
                        assert image.GetSize()[-1] == 1, f"There is more than one volume in this CT file for {subject_id}."
                        extractor = sitk.ExtractImageFilter()
                        extractor.SetSize([*image.GetSize()[:3], 0])
                        extractor.SetIndex([0, 0, 0, 0])    
                        
                        image = extractor.Execute(image)
                        if self.v:
                            print("image.GetSize():", image.GetSize())
                    try:
                        image = self.resample(image)
                    except Exception as e:
                        print(e)
                        warnings.warn("Could not resample {} for subject {}".format(colname, subject_id))

                    # update the metadata for this image
                    if hasattr(read_results[i], "metadata") and read_results[i].metadata is not None:
                        metadata.update(read_results[i].metadata)

                    if self.is_nnunet or self.is_nnunet_inference: 
                        nnunet_subject_name = f"{pathlib.Path(self.input_directory).name}_{subject_id.split('_')[0]:>03}"

                    subject_name = "_".join(subject_id.split("_")[1::]) # Extracts {SUBJECT_NAME}

                    # modality is MR and the user has selected to have nnunet output
                    if self.is_nnunet:
                        if modality == "MR":  # MR images can have various modalities like FLAIR, T1, etc.
                            if metadata["AcquisitionContrast"] not in self.total_modality_counter.keys():
                                self.total_modality_counter[metadata["AcquisitionContrast"]] = 1
                            else:
                                self.total_modality_counter[metadata["AcquisitionContrast"]] += 1
                            self.nnunet_info['current_modality'] = metadata["AcquisitionContrast"]
                            if metadata["AcquisitionContrast"] not in self.nnunet_info["modalities"].keys():  # if the modality is new
                                self.nnunet_info["modalities"][metadata["AcquisitionContrast"]] = str(len(self.nnunet_info["modalities"])).zfill(4)  # fill to 4 digits
                        else:
                            self.nnunet_info['current_modality'] = modality  # CT
                            if modality not in self.total_modality_counter.keys():
                                self.total_modality_counter[modality] = 1
                            else:
                                self.total_modality_counter[modality] += 1
                        if subject_name in self.train:
                            self.output(nnunet_subject_name, image, output_stream, nnunet_info=self.nnunet_info)
                        else:
                            self.output(nnunet_subject_name, image, output_stream, nnunet_info=self.nnunet_info, train_or_test="Ts")
                    elif self.is_nnunet_inference:
                        self.nnunet_info["current_modality"] = modality if modality == "CT" else metadata["AcquisitionContrast"]
                        if self.nnunet_info["current_modality"] not in self.nnunet_info["modalities"].keys():
                            raise ValueError(f"The modality {self.nnunet_info['current_modality']} is not in the list of modalities that are present in dataset.json.")
                        self.output(nnunet_subject_name, image, output_stream, nnunet_info=self.nnunet_info)
                    else:
                        self.output(subject_id, image, output_stream)

                    metadata[f"size_{output_stream}"] = str(image.GetSize())
                    print(subject_id, " SAVED IMAGE")

                # Process dose
                elif modality == "RTDOSE":
                    try:   # For cases with no image present
                        doses = read_results[i].resample_dose(image)
                    except:
                        Warning("No CT image present. Returning dose image without resampling")
                        doses = read_results[i]
                    
                    # save output
                    self.output(subject_id, doses, output_stream)
                    metadata[f"size_{output_stream}"] = str(doses.GetSize())
                    metadata[f"metadata_{colname}"] = [read_results[i].get_metadata()]

                    if hasattr(doses, "metadata") and doses.metadata is not None:
                        metadata.update(doses.metadata)

                    print(subject_id, " SAVED DOSE")
                    
                # Process PET
                elif modality == "PT":
                    try:
                        # For cases with no image present
                        pet = read_results[i].resample_pet(image)
                    except:
                        Warning("No CT image present. Returning PT/PET image without resampling.")
                        pet = read_results[i]

                    # output
                    self.output(subject_id, pet, output_stream)
                    metadata[f"size_{output_stream}"] = str(pet.GetSize())
                    metadata[f"metadata_{colname}"] = [read_results[i].get_metadata()]

                    if hasattr(pet, "metadata") and pet.metadata is not None:
                        metadata.update(pet.metadata)

                    print(subject_id, " SAVED PET")

                # Process contour
                elif modality == "RTSTRUCT":
                    num_rtstructs += 1
                    # For RTSTRUCT, you need image or PT
                    structure_set = read_results[i]
                    conn_to = output_stream.split("_")[-1]

                    # make_binary_mask relative to ct/pet
                    if conn_to in ["CT", "MR", "PT"]:
                        if conn_to == "CT" or conn_to == "MR":
                            img = image
                        elif conn_to == "PT":
                            img = pet  # noqa: F821
                        
                        mask = self.make_binary_mask(structure_set, img, 
                                                     self.existing_roi_indices, 
                                                     self.ignore_missing_regex, 
                                                     roi_select_first=self.roi_select_first, 
                                                     roi_separate=self.roi_separate)

                    else:
                        raise ValueError("You need to pass a reference CT or PT/PET image to map contours to.")
                    
                    if mask is None:  # ignored the missing regex, and exit the loop
                        if self.is_nnunet:
                            image_test_path = pathlib.Path(self.output_directory, "imagesTs").as_posix()
                            image_train_path = pathlib.Path(self.output_directory, "imagesTr").as_posix()
                            if os.path.exists(image_test_path):
                                all_files = glob.glob(pathlib.Path(image_test_path, "*.nii.gz").as_posix())
                                # print(all_files)
                                for file in all_files:
                                    if subject_id in os.path.split(file)[1]:
                                        os.remove(file)
                            if os.path.exists(image_train_path):
                                all_files = glob.glob(pathlib.Path(image_train_path, "*.nii.gz").as_posix())
                                # print(all_files)
                                for file in all_files:
                                    if nnunet_subject_name in os.path.split(file)[1]:
                                        os.remove(file)
                            warnings.warn(f"Patient {subject_id} is missing a complete image-label pair")
                            self.patients_with_missing_labels.add("".join(subject_id.split("_")[1:]))
                            return
                        else:
                            break
                    
                    for name in mask.roi_indices.keys():
                        if name not in self.existing_roi_indices.keys():
                            self.existing_roi_indices[name] = len(self.existing_roi_indices)
                    mask.existing_roi_indices = self.existing_roi_indices

                    if self.v:
                        print("mask.GetSize():", mask.GetSize())
                    mask_arr = np.transpose(sitk.GetArrayFromImage(mask))
                    
                    if self.is_nnunet:
                        sparse_mask = np.transpose(mask.generate_sparse_mask().mask_array)
                        sparse_mask = sitk.GetImageFromArray(sparse_mask)  # convert the nparray to sitk image
                        sparse_mask.CopyInformation(image)
                        if subject_name in self.train:
                            self.output(nnunet_subject_name, sparse_mask, output_stream, nnunet_info=self.nnunet_info, label_or_image="labels")  # rtstruct is label for nnunet
                        else:
                            self.output(nnunet_subject_name, sparse_mask, output_stream, nnunet_info=self.nnunet_info, label_or_image="labels", train_or_test="Ts")
                    else:
                        # if there is only one ROI, sitk.GetArrayFromImage() will return a 3d array instead of a 4d array with one slice
                        if len(mask_arr.shape) == 3:
                            mask_arr = mask_arr.reshape(1, mask_arr.shape[0], mask_arr.shape[1], mask_arr.shape[2])
                        
                        if self.v:
                            print(mask_arr.shape)

                        roi_names_list = list(mask.roi_indices.keys())
                        for i in range(mask_arr.shape[0]):
                            new_mask = sitk.GetImageFromArray(np.transpose(mask_arr[i]))
                            new_mask.CopyInformation(mask)
                            new_mask = Segmentation(new_mask)
                            mask_to_process = new_mask
                            
                            # output
                            self.output(subject_id, mask_to_process, output_stream, True, roi_names_list[i])
                    
                    if hasattr(structure_set, "metadata") and structure_set.metadata is not None:
                        metadata.update(structure_set.metadata)

                    metadata[f"metadata_{colname}"] = [structure_set.roi_names]
                    for roi, labels in mask.raw_roi_names.items():
                        metadata[f"raw_labels_{roi}"] = labels                    

                    print(subject_id, "SAVED MASK ON", conn_to)
                
                
                
                metadata[f"output_folder_{colname}"] = pathlib.Path(subject_id, colname).as_posix()
            
            # Saving all the metadata in multiple text files
            metadata["Modalities"] = str(list(subject_modalities))
            metadata["numRTSTRUCTs"] = num_rtstructs
            if self.is_nnunet:
                metadata["Train or Test"] = "train" if subject_name in self.train else "test"
            with open(pathlib.Path(self.output_directory,".temp",f'{subject_id}.pkl').as_posix(),'wb') as f:  # the continue flag depends on this being the last line in this method
                pickle.dump(metadata,f)
            return 
    
    def save_data(self):
        """
        Saves metadata about processing. 
        """
        files = glob.glob(pathlib.Path(self.output_directory, ".temp", "*.pkl").as_posix())
        for file in files:
            filename = pathlib.Path(file).name
            if filename == "init_parameters.pkl":
                continue
            subject_id = os.path.splitext(filename)[0]
            with open(file,"rb") as f:
                metadata = pickle.load(f)

            self.output_df.loc[subject_id, metadata.keys()] = metadata.values()  # subject id targets the rows with that subject id and it is reassigning all the metadata values by key

        folder_renames = {}
        for col in self.output_df.columns:
            if col.startswith("folder"):
                self.output_df[col] = self.output_df[col].apply(lambda x: x if not isinstance(x, str) else pathlib.Path(x).as_posix().split(self.input_directory)[1][1:]) # rel path, exclude the slash at the beginning
                folder_renames[col] = f"input_{col}"
        self.output_df.rename(columns=folder_renames, inplace=True)  # append input_ to the column name
        self.output_df.to_csv(self.output_df_path)  # dataset.csv

        shutil.rmtree(pathlib.Path(self.output_directory, ".temp").as_posix())

        if self.is_nnunet: 
            train_dir = ((pathlib.Path(self.output_directory)) / 'imagesTr')
            num_training_cases = sum( # This can be different from len(self.train) if regex of ROI not matched
                1 for file in train_dir.iterdir() 
                if file.suffixes == ['.nii', '.gz']
                )
            test_dir = ((pathlib.Path(self.output_directory)) / 'imagesTs')
            num_test_cases = sum( # This can be different from len(self.test) if regex of ROI not matched
                1 for file in test_dir.iterdir() 
                if file.suffixes == ['.nii', '.gz']
                ) if test_dir.exists() else 0 # no testing data
            
            channel_names_mapping = { # Earlier generated as {"CT": ""0000"} now needed as {"0": "CT"}
                self.nnunet_info["modalities"][k].lstrip('0') or '0': k  
                for k in self.nnunet_info["modalities"].keys()
            }
            generate_dataset_json(
                output_folder=pathlib.Path(self.output_directory), 
                channel_names=channel_names_mapping,
                labels=self.existing_roi_indices,     
                file_ending='.nii.gz',
                num_training_cases=num_training_cases
            )
            create_train_script(self.output_directory, self.dataset_id)
            markdown_report_images(
                self.output_directory, 
                self.total_modality_counter, 
                num_training_cases, 
                num_test_cases
            )
        
        # Save summary info (factor into different file)
        markdown_path = pathlib.Path(self.output_directory, "report.md").as_posix()
        with open(markdown_path, "w", newline="\n") as f:
            output = "# Dataset Report\n\n"
            if not self.is_nnunet:
                output += "## Patients with broken DICOM references\n\n"
                output += "<details>\n"
                output += "\t<summary>Click to see the list of patients with broken DICOM references</summary>\n\n\t"
                formatted_list = "\n\t".join(self.broken_patients)
                output += f"{formatted_list}\n"
                output += "</details>\n\n"

            if self.is_nnunet:
                output += "## Train Test Split\n\n"
                # pie_path = pathlib.Path(self.output_directory, "markdown_images", "nnunet_train_test_pie.png").as_posix()
                pie_path = pathlib.Path("markdown_images", "nnunet_train_test_pie.png").as_posix()
                output += f"![Pie Chart of Train Test Split]({pie_path})\n\n"
                output += "## Image Modality Distribution\n\n"
                # bar_path = pathlib.Path(self.output_directory, "markdown_images", "nnunet_modality_count.png").as_posix()
                bar_path = pathlib.Path("markdown_images", "nnunet_modality_count.png").as_posix()
                output += f"![Pie Chart of Image Modality Distribution]({bar_path})\n\n"
            f.write(output)

    def run(self):
        """Execute the pipeline, possibly in parallel.
        """
        # Joblib prints progress to stdout if verbose > 50
        verbose = 51 if self.v or self.show_progress else 0

        subject_ids = self._get_loader_subject_ids()
        patient_ids = []
        if not self.dry_run:
            for subject_id in subject_ids:
                if subject_id.split("_")[1::] not in patient_ids:
                    patient_ids.append("_".join(subject_id.split("_")[1::]))
            if self.is_nnunet:
                custom_train = []
                custom_test = []
                if self.custom_train_test_split:
                    patient_ids = [item for item in patient_ids if item not in self.custom_split["train"] and item not in self.custom_split["test"]]
                    custom_test = self.custom_split["test"]
                    custom_train = self.custom_split["train"]
                if self.train_size == 1:
                    self.train = patient_ids
                    self.test = []
                    self.train.extend(custom_train)
                    self.test.extend(custom_test)
                else:
                    self.train, self.test = train_test_split(sorted(patient_ids), train_size=self.train_size, random_state=self.random_state)
                    self.train.extend(custom_train)
                    self.test.extend(custom_test)
            else:
                self.train, self.test = [], []
            # Note that returning any SimpleITK object in process_one_subject is
            # not supported yet, since they cannot be pickled
            if os.path.exists(self.output_df_path) and not self.overwrite:
                print("Dataset already processed...")
                logger.info("Dataset already processed...")
                shutil.rmtree(pathlib.Path(self.output_directory, ".temp").as_posix())
            else:
                Parallel(n_jobs=self.n_jobs, verbose=verbose, require='sharedmem')(
                        delayed(self._process_wrapper)(subject_id) for subject_id in subject_ids)
                # for subject_id in subject_ids:
                #     self._process_wrapper(subject_id)
                self.broken_patients = []
                if not self.is_nnunet:
                    all_patient_names = glob.glob(pathlib.Path(self.input_directory, "*", " ").as_posix()[0:-1])
                    all_patient_names = [os.path.split(os.path.split(x)[0])[1] for x in all_patient_names]
                    for e in all_patient_names:
                        if e not in patient_ids:
                            warnings.warn(f"Patient {e} does not have proper DICOM references")
                            self.broken_patients.append(e)
                self.save_data()


def main():
    args = parser()
    args_dict = vars(args)
    
    if args.continue_processing:
        try:
            with open(pathlib.Path(args.output_directory, ".temp", "init_parameters.pkl").as_posix(), "rb") as f:
                args_dict = dill.load(f)
        except:
            logger.info("Could not resume processing. Starting processing from the beginning.")
    logger.debug("Starting main:", args=args_dict)
    logger.info('Initializing AutoPipeline...')
    pipeline = AutoPipeline(**args_dict)

    if not args.dry_run:
        logger.info('Starting AutoPipeline...')
        pipeline.run()
        logger.info('Finished AutoPipeline!')
    else:
        logger.info('Dry run complete, no processing done')

    """Print general summary info"""

    """Print nnU-Net specific info here:
    * dataset.json can be found at /path/to/dataset/json
    * You can train nnU-Net by cloning /path/to/nnunet/repo and run `nnUNet_plan_and_preprocess -t taskID` to let the nnU-Net package prepare
    """
    logger.info(f"Outputted data to {args.output_directory}")
    csv_path = pathlib.Path(args.output_directory, "dataset.csv").as_posix()
    logger.info(f"Dataset info found at {csv_path}")
    if args.nnunet:
        json_path = pathlib.Path(args.output_directory, "dataset.json").as_posix()
        logger.info(f"dataset.json for nnU-net can be found at {json_path}")
        logger.info("You can train nnU-net by cloning https://github.com/MIC-DKFZ/nnUNet/ and run `nnUNet_plan_and_preprocess -t taskID` to let the nnU-Net package prepare")


if __name__ == "__main__":
    main()