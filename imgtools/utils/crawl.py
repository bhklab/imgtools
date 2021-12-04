from argparse import ArgumentParser
import os
import glob
import json

import pandas as pd
from pydicom import dcmread
from tqdm import tqdm

from joblib import Parallel, delayed

def crawl_one(folder):
    database = {}
    for path, _, _ in os.walk(folder):
        # find dicoms
        dicoms = glob.glob(os.path.join(path, "*.dcm"))

        # instance (slice) information
        for dcm in dicoms:
            meta = dcmread(dcm)
            patient  = meta.PatientID
            study    = meta.StudyInstanceUID
            series   = meta.SeriesInstanceUID
            instance = meta.SOPInstanceUID

            reference_ct, reference_rs, reference_pl = "", "", ""
            try: #RTSTRUCT
                reference_ct = meta.ReferencedFrameOfReferenceSequence[0].RTReferencedStudySequence[0].RTReferencedSeriesSequence[0].SeriesInstanceUID 
            except: 
                try: #RTDOSE
                    reference_rs = meta.ReferencedStructureSetSequence[0].ReferencedSOPInstanceUID
                except:
                    pass
                try:
                    reference_ct = meta.ReferencedImageSequence[0].ReferencedSOPInstanceUID
                except:
                    pass
                try:
                    reference_pl = meta.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID
                except:
                    pass

            try:
                study_description = meta.StudyDescription
            except:
                study_description = ""

            try:
                series_description = meta.SeriesDescription
            except:
                series_description = ""

            if patient not in database:
                database[patient] = {}
            if study not in database[patient]:
                database[patient][study] = {'description': study_description}
            if series not in database[patient][study]:
                database[patient][study][series] = {'instances': [],
                                                    'instance_uid': instance,
                                                    'modality': meta.Modality,
                                                    'description': series_description,
                                                    'reference_ct': reference_ct,
                                                    'reference_rs': reference_rs,
                                                    'reference_pl': reference_pl,
                                                    'folder': path}
            database[patient][study][series]['instances'].append(instance)
    
    return database

def to_df(database_dict):
    df = pd.DataFrame()
    for pat in database_dict:
        for study in database_dict[pat]:
            for series in database_dict[pat][study]:
                if series != 'description':
                    df = df.append({'patient_ID': pat,
                                    'study': study,
                                    'study_description': database_dict[pat][study]['description'],
                                    'series': series,
                                    'series_description': database_dict[pat][study][series]['description'],
                                    'modality': database_dict[pat][study][series]['modality'],
                                    'instances': len(database_dict[pat][study][series]['instances']),
                                    'instance_uid': database_dict[pat][study][series]['instance_uid'],
                                    'reference_ct': database_dict[pat][study][series]['reference_ct'],
                                    'reference_rs': database_dict[pat][study][series]['reference_rs'],
                                    'reference_pl': database_dict[pat][study][series]['reference_pl'],
                                    'folder': database_dict[pat][study][series]['folder']}, ignore_index=True)
    return df

def crawl(top, n_jobs=1):
    database_list = []
    folders = glob.glob(os.path.join(top, "*"))
    
    # crawl folder-by-folder
    if n_jobs == 1:
        for n, folder in enumerate(tqdm(folders)):
            database_list.append(crawl_one(folder))
    else:
        database_list = Parallel(n_jobs=n_jobs)(delayed(crawl_one)(os.path.join(top, folder)) for folder in tqdm(folders))

    # convert list to dictionary
    database_dict = {}
    for db in database_list:
        for key in db:
            database_dict[key] = db[key]
    
    # save one level above imaging folders
    parent  = os.path.dirname(top)
    dataset = os.path.split(top)[-1]
    
    # save as json
    with open(os.path.join(parent, f'imgtools_{dataset}.json'), 'w') as f:
        json.dump(database_dict, f, indent=4)
    
    # save as dataframe
    df = to_df(database_dict)
    df_path = os.path.join(parent, f'imgtools_{dataset}.csv')
    df.to_csv(df_path)
    
    return database_dict

if __name__ == "__main__":
    parser = ArgumentParser("Dataset DICOM Crawler")
    parser.add_argument("directory",
                         type=str,
                         help="Top-level directory of the dataset.")
    parser.add_argument("--n_jobs",
                         type=int,
                         default=32,
                         help="Number of parallel processes for multiprocessing.")

    args = parser.parse_args()
    db = crawl(args.directory, n_jobs=args.n_jobs)
    print("# patients:", len(db))