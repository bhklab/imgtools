import json
import os
import pathlib
from argparse import ArgumentParser

import click
import pandas as pd
from joblib import Parallel, delayed
from pydicom import dcmread
from tqdm import tqdm

from imgtools.logging import logger


# fmt: off
def crawl_one(folder: pathlib.Path) -> dict:
    folder_path = pathlib.Path(folder)
    database = {}
    for path in folder_path.iterdir():
        # find dicoms
        dicoms = [f for f in path.rglob("*.dcm")]
        logger.info(f"Found {len(dicoms)} dicoms in {path}")

        for dcm in dicoms:
            try:
                dcm_path = pathlib.Path(dcm)

                fname = dcm_path.name

                rel_path = dcm_path.relative_to(
                    folder_path.parent.parent
                )  # rel_path of dicom from folder

                rel_posix = (
                    rel_path.parent.as_posix()
                )  # folder name + until parent folder of dicom

                meta = dcmread(dcm, force=True, stop_before_pixels=True)
                patient = str(meta.PatientID)
                study = str(meta.StudyInstanceUID)
                series = str(meta.SeriesInstanceUID)
                instance = str(meta.SOPInstanceUID)

                (
                    reference_ct,
                    reference_rs,
                    reference_pl,
                ) = "", "", ""
                tr, te, tesla, scan_seq, elem = "", "", "", "", ""
                try:
                    orientation = str(meta.ImageOrientationPatient)  # (0020, 0037)
                except:
                    orientation = ""

                try:
                    orientation_type = str(
                        meta.AnatomicalOrientationType
                    )  # (0010, 2210)
                except:
                    orientation_type = ""

                try:  # RTSTRUCT
                    reference_ct = str(
                        meta.ReferencedFrameOfReferenceSequence[0]
                        .RTReferencedStudySequence[0]
                        .RTReferencedSeriesSequence[0]
                        .SeriesInstanceUID
                    )
                except:
                    try:  # SEGMENTATION
                        reference_ct = str(
                            meta.ReferencedSeriesSequence[0].SeriesInstanceUID
                        )
                    except:
                        try:  # RTDOSE
                            reference_rs = str(
                                meta.ReferencedStructureSetSequence[
                                    0
                                ].ReferencedSOPInstanceUID
                            )
                        except:
                            pass
                        try:
                            reference_ct = str(
                                meta.ReferencedImageSequence[0].ReferencedSOPInstanceUID
                            )
                        except:
                            pass
                        try:
                            reference_pl = str(
                                meta.ReferencedRTPlanSequence[
                                    0
                                ].ReferencedSOPInstanceUID
                            )
                        except:
                            pass

                # MRI Tags
                try:
                    tr = float(meta.RepetitionTime)
                except:
                    pass
                try:
                    te = float(meta.EchoTime)
                except:
                    pass
                try:
                    scan_seq = str(meta.ScanningSequence)
                except:
                    pass
                try:
                    tesla = float(meta.MagneticFieldStrength)
                except:
                    pass
                try:
                    elem = str(meta.ImagedNucleus)
                except:
                    pass

                # Frame of Reference UIDs
                try:
                    reference_frame = str(meta.FrameOfReferenceUID)
                except:
                    try:
                        reference_frame = str(
                            meta.ReferencedFrameOfReferenceSequence[
                                0
                            ].FrameOfReferenceUID
                        )
                    except:
                        reference_frame = ""

                try:
                    study_description = str(meta.StudyDescription)
                except:
                    study_description = ""

                try:
                    series_description = str(meta.SeriesDescription)
                except:
                    series_description = ""

                try:
                    subseries = str(meta.AcquisitionNumber)
                except:
                    subseries = "default"

                if patient not in database:
                    database[patient] = {}
                if study not in database[patient]:
                    database[patient][study] = {"description": study_description}
                if series not in database[patient][study]:
                    rel_crawl_path = rel_posix
                    if meta.Modality == "RTSTRUCT":
                        rel_crawl_path = os.path.join(rel_crawl_path, fname)

                    database[patient][study][series] = {
                        "description": series_description
                    }
                if subseries not in database[patient][study][series]:
                    database[patient][study][series][subseries] = {'instances': {},
                                                                   'instance_uid': instance,
                                                                   'modality': meta.Modality,
                                                                   'reference_ct': reference_ct,
                                                                   'reference_rs': reference_rs,
                                                                   'reference_pl': reference_pl,
                                                                   'reference_frame': reference_frame,
                                                                   'folder': rel_crawl_path,
                                                                   'orientation': orientation,
                                                                   'orientation_type': orientation_type,
                                                                   'repetition_time':tr,
                                                                   'echo_time':te,
                                                                   'scan_sequence': scan_seq,
                                                                   'mag_field_strength': tesla,
                                                                   'imaged_nucleus': elem,
                                                                   'fname': rel_path.as_posix()  # temporary until we switch to json-based loading
                                                                   }
                database[patient][study][series][subseries]["instances"][instance] = (
                    rel_path.as_posix()
                )
            except Exception as e:
                print(folder, e)
                pass

    return database


def to_df(database_dict):
    df = pd.DataFrame()
    columns = ['patient_ID', 'study', 'study_description',  # noqa
                                       'series', 'series_description', 'subseries', 'modality', 
                                       'instances', 'instance_uid', 
                                       'reference_ct', 'reference_rs', 'reference_pl', 'reference_frame', 'folder',
                                       'orientation', 'orientation_type', 'MR_repetition_time', 'MR_echo_time', 
                                       'MR_scan_sequence', 'MR_magnetic_field_strength', 'MR_imaged_nucleus', 'file_path']
    for pat in database_dict:
        for study in database_dict[pat]:
            for series in database_dict[pat][study]:
                if series != "description":  # skip description key in dict
                    for subseries in database_dict[pat][study][series]:
                        if subseries != 'description':  # skip description key in dict
                            
                            values = [pat, study, database_dict[pat][study]['description'], # noqa
                                      series, database_dict[pat][study][series]['description'], 
                                      subseries, database_dict[pat][study][series][subseries]['modality'], 
                                      len(database_dict[pat][study][series][subseries]['instances']), database_dict[pat][study][series][subseries]['instance_uid'], 
                                      database_dict[pat][study][series][subseries]['reference_ct'], database_dict[pat][study][series][subseries]['reference_rs'], 
                                      database_dict[pat][study][series][subseries]['reference_pl'], database_dict[pat][study][series][subseries]['reference_frame'], database_dict[pat][study][series][subseries]['folder'],
                                      database_dict[pat][study][series][subseries]['orientation'], database_dict[pat][study][series][subseries]['orientation_type'],
                                      database_dict[pat][study][series][subseries]['repetition_time'], database_dict[pat][study][series][subseries]['echo_time'],
                                      database_dict[pat][study][series][subseries]['scan_sequence'], database_dict[pat][study][series][subseries]['mag_field_strength'], database_dict[pat][study][series][subseries]['imaged_nucleus'],
                                      database_dict[pat][study][series][subseries]['fname']
                                      ]

                            df_add = pd.DataFrame([values], columns=columns)
                            df = pd.concat([df, df_add], ignore_index=True)
    return df

# fmt: on
def crawl(
    top: pathlib.Path,
    n_jobs: int = -1,
    csv_path: pathlib.Path | None = None,
    json_path: pathlib.Path | None = None,
    imgtools_dir: str = ".imgtools",
) -> dict:
    database_list = []
    # folders = glob.glob(pathlib.Path(top, "*").as_posix())
    folders = [f for f in pathlib.Path(top).iterdir() if f.is_dir()]
    logger.info(f"Crawling {len(folders)} folders in {top}")

    database_list = Parallel(n_jobs=n_jobs)(
        delayed(crawl_one)(folder.as_posix())
        for folder in tqdm(folders, desc="Crawling folders", leave=False)
    )
    logger.info("Converting list to dictionary")
    # convert list to dictionary
    database_dict = {}
    for db in database_list:
        for key in db:
            database_dict[key] = db[key]

    # configure json path
    if json_path is None:
        json_path = top.parent / imgtools_dir / f"imgtools_{top.name}.json"

    json_path.parent.mkdir(parents=True, exist_ok=True)

    # configure csv path
    if csv_path is None:
        csv_path = top.parent / imgtools_dir / f"imgtools_{top.name}.csv"

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # Save as json
    logger.info(f"Saving as json to {json_path}")
    with json_path.open("w") as f:
        json.dump(database_dict, f, indent=4)

    # Save as dataframe
    logger.info(f"Saving as dataframe to {csv_path}")
    df = to_df(database_dict)
    df.to_csv(csv_path)

    return database_dict


# ruff: noqa
if __name__ == "__main__":  # pragma: no cover
    parser = ArgumentParser("Dataset DICOM Crawler")
    parser.add_argument(
        "directory", type=str, help="Top-level directory of the dataset."
    )
    parser.add_argument(
        "--n_jobs",
        type=int,
        default=os.cpu_count() - 2,
        help="Number of parallel processes for multiprocessing.",
    )

    args = parser.parse_args()
    db = crawl(args.directory, n_jobs=args.n_jobs)
    print("# patients:", len(db))
