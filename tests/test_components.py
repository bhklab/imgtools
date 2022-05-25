import os, pathlib
import shutil
import urllib.request as request
from zipfile import ZipFile
import torchio as tio
from torch.utils.data import DataLoader
import pytest
import pandas as pd
import nrrd
import torch
from typing import List
import re
from imgtools.autopipeline import AutoPipeline
from imgtools.io import file_name_convention, Dataset
 
@pytest.fixture(scope="session")
def dataset_path():
    curr_path = pathlib.Path(__file__).parent.parent.resolve()
    quebec_path = pathlib.Path(os.path.join(curr_path, "data", "Head-Neck-PET-CT"))
    
    if not os.path.exists(quebec_path):
        pathlib.Path(quebec_path).mkdir(parents=True, exist_ok=True)
        # Download QC dataset
        print("Downloading the test dataset...")
        quebec_data_url = "https://github.com/bhklab/tcia_samples/blob/main/Head-Neck-PET-CT.zip?raw=true"
        quebec_zip_path = os.path.join(quebec_path, "Head-Neck-PET-CT.zip")
        request.urlretrieve(quebec_data_url, quebec_zip_path) 
        with ZipFile(quebec_zip_path, 'r') as zipfile:
            zipfile.extractall(quebec_path)
        os.remove(quebec_zip_path)
    else:
        print("Data already downloaded...")
    output_path = pathlib.Path(os.path.join(curr_path, 'tests','temp')).as_posix()
    quebec_path = quebec_path.as_posix()
    
    #Dataset name
    dataset_name = os.path.basename(quebec_path)

    #Defining paths for autopipeline and dataset component
    crawl_path = os.path.join(os.path.dirname(quebec_path), f"imgtools_{dataset_name}.csv")
    json_path =  os.path.join(os.path.dirname(quebec_path), f"imgtools_{dataset_name}.json")
    edge_path = os.path.join(os.path.dirname(quebec_path), f"imgtools_{dataset_name}_edges.csv")
    yield quebec_path, output_path, crawl_path, edge_path
    #Deleting all the temporary files
    os.remove(crawl_path)
    os.remove(json_path)
    os.remove(edge_path)
    shutil.rmtree(output_path)

#Defining for test_dataset method in Test_components class
def collate_fn(data):
    """
       data: is a tio.subject with multiple columns
             Need to return required data
    """
    mod_names = [items for items in data[0].keys() if items.split("_")[0]=="mod"]
    temp_stack = {}
    for names in mod_names:
        temp_stack[names] = torch.stack(tuple(items[names].data for items in data))
    return temp_stack

class select_roi_names(tio.LabelTransform):
    """
    Based on the given roi names, selects from the given set
    """
    def __init__(
            self,
            roi_names: List[str] = None,
            **kwargs
            ) -> None:
        super().__init__(**kwargs)
        self.kwargs = kwargs
        self.roi_names = roi_names
    
    def apply_transform(self,subject):
        #list of roi_names
        for image in self.get_images(subject):
            #For only applying to labelmaps
            metadata = subject["metadata_RTSTRUCT_CT"]
            patterns = self.roi_names
            mask = torch.empty_like(image.data)[:len(patterns)]
            for j,pat in enumerate(patterns):
                k = []
                for i,col in enumerate(metadata):
                    if re.match(pat,col,flags=re.IGNORECASE):
                        k.append(i)
                if len(k)==0:
                    mask[j] = mask[j]*0
                else:  
                    mask[j] = (image.data[k].sum(axis=0)>0)*1    
            image.set_data(mask)
        return subject
    
    def is_invertible(self):
        return False


# @pytest.mark.parametrize("modalities",["PT", "CT,RTSTRUCT", "CT,RTDOSE", "CT,PT,RTDOSE", "CT,RTSTRUCT,RTDOSE", "CT,RTSTRUCT,RTDOSE,PT"])
@pytest.mark.parametrize("modalities", ["CT,RTDOSE,PT"])
class Test_components:
    """
    For testing the autopipeline and dataset components of the med-imagetools package
    It has two methods:
    test_pipeline:
        1) Checks if there is any crawler and edge table output generated by autopipeline
        2) Checks if for the test data, the lengths of the crawler and edge table matches the actual length of what should be ideally created
        3) Checks if the length of component table(dataset.csv) is correct or not
        4) Checks for every component, the shape of all different modalities matches or not
    test_dataset:
        1) Checks if the length of the dataset matches
        2) Checks if the items in the subject object is correct and present
        3) Checks if you are able to load it via load_nrrd and load_directly, and checks if the subjects generated matches
        4) Checks if torch data loader can load the formed dataset and get atleast 1 iteration
        5) Checks if the transforms are happening by checking the size
    """
    @pytest.fixture(autouse=True)
    def _get_path(self, dataset_path):
        self.input_path, self.output_path, self.crawl_path, self.edge_path = dataset_path
    
    def test_pipeline(self, modalities):
        """
        Testing the Autopipeline for processing the DICOMS and saving it as nrrds
        """
        n_jobs = 2
        output_path_mod = os.path.join(self.output_path, str("temp_folder_" + ("_").join(modalities.split(","))))
        #Initialize pipeline for the current setting
        pipeline = AutoPipeline(self.input_path, output_path_mod, modalities, n_jobs=n_jobs,spacing=(5,5,5))
        #Run for different modalities
        comp_path = os.path.join(output_path_mod, "dataset.csv")
        pipeline.run()

        #Check if the crawl and edges exist
        assert os.path.exists(self.crawl_path) & os.path.exists(self.edge_path), "There was no crawler output"

        #for the test example, there are 6 files and 4 connections
        crawl_data = pd.read_csv(self.crawl_path, index_col=0)
        edge_data = pd.read_csv(self.edge_path)
        assert (len(crawl_data) == 12) & (len(edge_data) == 8), "There was an error in crawling or while making the edge table"

        #Check if the dataset.csv is having the correct number of components and has all the fields
        comp_table = pd.read_csv(comp_path, index_col=0)
        assert len(comp_table) == 2, "There was some error in making components, check datagraph.parser"

        #Check the nrrd files
        subject_id_list = list(comp_table.index)
        output_streams = [("_").join(cols.split("_")[1:]) for cols in comp_table.columns if cols.split("_")[0]=="folder"]
        file_names = file_name_convention()
        for subject_id in subject_id_list:
            shapes = []
            for col in output_streams:
                extension = file_names[col]
                mult_conn = col.split("_")[-1].isnumeric()
                if mult_conn:
                    extra = col.split("_")[-1] + "_"
                else:
                    extra = ""
                print(subject_id, extension, extra)
                path_mod = os.path.join(output_path_mod, extension.split(".")[0],f"{subject_id}_{extra}{extension}.nrrd")
                #All modalities except RTSTRUCT should be of type torchIO.ScalarImage
                temp_dicom,_ = nrrd.read(path_mod)
                if col.split("_")[0]=="RTSTRUCT":
                    shapes.append(temp_dicom.shape[1:])
                else:
                    shapes.append(temp_dicom.shape)
            A = [item == shapes[0] for item in shapes]
            print(shapes)
            assert all(A)
    
    def test_dataset(self,modalities):
        """
        Testing the Dataset class
        Note that test is not for 
        """
        output_path_mod = os.path.join(self.output_path, str("temp_folder_" + ("_").join(modalities.split(","))))
        comp_path = os.path.join(output_path_mod, "dataset.csv")
        comp_table = pd.read_csv(comp_path, index_col=0)
        
        #Loading from nrrd files
        subjects_nrrd = Dataset.load_from_nrrd(output_path_mod,ignore_multi=True)
        #Loading files directly
        subjects_direct = Dataset.load_directly(self.input_path,modalities=modalities,ignore_multi=True)
        
        #The number of subjects is equal to the number of components which is 2 for this dataset
        assert len(subjects_nrrd) == len(subjects_direct) == 2, "There was some error in generation of subject object"
        assert subjects_nrrd[0].keys() == subjects_direct[0].keys()

        del subjects_direct
        #To check if there are all items present in the keys
        temp_nrrd = subjects_nrrd[0]
        columns_shdbe_present = set([col if col.split("_")[0]=="metadata" else "mod_"+("_").join(col.split("_")[1:]) for col in list(comp_table.columns) if col.split("_")[0] in ["folder","metadata"]])
        assert set(temp_nrrd.keys()).issubset(columns_shdbe_present), "Not all items present in dictionary, some fault in going through the different columns in a single component"

        transforms = tio.Compose([tio.Resample(4),tio.CropOrPad((96,96,40)),select_roi_names(["larynx"]),tio.OneHot()])

        #Forming dataset and dataloader
        test_set = tio.SubjectsDataset(subjects_nrrd, transform=transforms)
        test_loader = torch.utils.data.DataLoader(test_set,batch_size=2,shuffle=True,collate_fn = collate_fn)

        #Check test_set is correct
        assert len(test_set)==2

        #Get items from test loader
        #If this function fails , there is some error in formation of test
        data = next(iter(test_loader))
        A = [item[1].shape == (2,1,96,96,40) if not "RTSTRUCT" in item[0] else item[1].shape == (2,2,96,96,40) for item in data.items()]
        assert all(A), "There is some problem in the transformation/the formation of subject object"