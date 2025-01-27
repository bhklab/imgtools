from __future__ import annotations

import glob
import json
import os
import pathlib
import re
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Optional, Union

import pandas as pd
import SimpleITK as sitk
from pydicom import dcmread

from imgtools.modules import PET, Dose, Scan, Segmentation, StructureSet
from imgtools.utils.dicomutils import get_modality_metadata


def read_image(path: str) -> sitk.Image:
    """Read an image from the specified file path using SimpleITK.

    Parameters
    ----------
    path : str
        The file path to the image.

    Returns
    -------
    sitk.Image
        The image read from the file.
    """
    return sitk.ReadImage(path)


def read_dicom_series(
    path: str,
    series_id: list[str] | None = None,
    recursive: bool = False,
    file_names: list[str] | None = None,
) -> sitk.Image:
    """Read DICOM series as SimpleITK Image.

    Parameters
    ----------
    path
       Path to directory containing the DICOM series.

    recursive, optional
       Whether to recursively parse the input directory when searching for
       DICOM series,

    series_id, optional
       Specifies the DICOM series to load if multiple series are present in
       the directory. If None and multiple series are present, loads the first
       series found.

    file_names, optional
        If there are multiple acquisitions/"subseries" for an individual series,
        use the provided list of file_names to set the ImageSeriesReader.

    Returns
    -------
    The loaded image.
    """
    reader = sitk.ImageSeriesReader()
    if file_names is None:
        # extract the names of the dicom files that are in the path variable, which is a directory
        file_names = reader.GetGDCMSeriesFileNames(
            path,
            seriesID=series_id if series_id else "",
            recursive=recursive,
        )

    reader.SetFileNames(file_names)

    # Configure the reader to load all of the DICOM tags (public+private):
    # By default tags are not loaded (saves time).
    # By default if tags are loaded, the private tags are not loaded.
    # We explicitly configure the reader to load tags, including the
    # private ones.
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()

    return reader.Execute()


def read_dicom_scan(
    path: str,
    series_id: list[str] | None = None,
    recursive: bool = False,
    file_names: list[str] | None = None,
) -> Scan:
    image = read_dicom_series(
        path,
        series_id=series_id,
        recursive=recursive,
        file_names=file_names,
    )
    return Scan(image, {})


def read_dicom_rtstruct(
    path: str,
    suppress_warnings: bool = False,
    roi_name_pattern: str | None = None,
) -> StructureSet:
    return StructureSet.from_dicom(
        path,
        suppress_warnings=suppress_warnings,
        roi_name_pattern=roi_name_pattern,
    )


def read_dicom_rtdose(path: str) -> Dose:
    return Dose.from_dicom(path=path)


def read_dicom_pet(path: str, series: Optional[str] = None) -> PET:
    return PET.from_dicom(path=path, series_id=series, pet_image_type="SUV")


def read_dicom_seg(
    path: str, meta: dict, series: Optional[str] = None
) -> Segmentation:
    seg_img = read_dicom_series(path, series)
    return Segmentation.from_dicom(seg_img, meta)


auto_dicom_result = Union[Scan, PET, StructureSet, Dose, Segmentation]


def read_dicom_auto(
    path: str, series=None, file_names=None
) -> auto_dicom_result:
    dcms = (
        list(pathlib.Path(path).rglob("*.dcm"))
        if not path.endswith(".dcm")
        else [pathlib.Path(path)]
    )

    for dcm_path in dcms:
        dcm = dcm_path.as_posix()
        meta = dcmread(dcm, stop_before_pixels=True)
        if meta.SeriesInstanceUID != series and series is not None:
            continue

        modality = meta.Modality

        match modality:
            case "CT" | "MR":
                obj = read_dicom_scan(path, series, file_names=file_names)
            case "PT":
                obj = read_dicom_pet(path, series)
            case "RTSTRUCT":
                obj = read_dicom_rtstruct(dcm)
            case "RTDOSE":
                obj = read_dicom_rtdose(dcm)
            case "SEG":
                obj = read_dicom_seg(path, meta, series)
            case _:
                errmsg = (
                    f"Modality {modality} not supported in read_dicom_auto."
                )
                raise NotImplementedError(errmsg)

        obj.metadata.update(get_modality_metadata(meta, modality))
        return obj


# ruff: noqa
class BaseLoader(ABC):
    @abstractmethod
    def __getitem__(self, subject_id):
        pass

    def __len__(self) -> int:
        return len(self.keys())

    @abstractmethod
    def keys(self):
        pass

    def items(self):
        return ((k, self[k]) for k in self.keys())

    def values(self):
        return (self[k] for k in self.keys())

    def get(self, subject_id, default=None):
        try:
            return self[subject_id]
        except KeyError:
            return default


class ImageTreeLoader(BaseLoader):
    def __init__(
        self,
        json_path,
        csv_path_or_dataframe,
        col_names=None,
        study_names=None,
        series_names=None,
        subseries_names=None,
        id_column=None,
        expand_paths=False,
        readers=None,
    ) -> None:
        if subseries_names is None:
            subseries_names = []
        if series_names is None:
            series_names = []
        if study_names is None:
            study_names = []
        if col_names is None:
            col_names = []
        if readers is None:
            readers = [
                read_image
            ]  # no mutable defaults https://florimond.dev/en/posts/2018/08/python-mutable-defaults-are-the-source-of-all-evil/

        self.expand_paths = expand_paths
        self.readers = readers
        self.colnames = col_names
        self.studynames = study_names
        self.seriesnames = series_names
        self.subseriesnames = subseries_names

        if isinstance(csv_path_or_dataframe, str):
            if id_column is not None and id_column not in self.colnames:
                self.colnames.append(id_column)
            self.paths = pd.read_csv(
                csv_path_or_dataframe, index_col=id_column
            )
        elif isinstance(csv_path_or_dataframe, pd.DataFrame):
            self.paths = csv_path_or_dataframe
            if id_column:
                self.paths = self.paths.set_index(id_column)
            if len(self.colnames) == 0:
                self.colnames = self.paths.columns
        else:
            msg = f"Expected a path to csv file or pd.DataFrame, not {type(csv_path_or_dataframe)}."
            raise ValueError(msg)

        if isinstance(json_path, str):
            with open(json_path, "r") as f:
                self.tree = json.load(f)
        else:
            msg = f"Expected a path to a json file, not {type(json_path)}."
            raise ValueError(msg)

        if not isinstance(readers, list):
            readers = [readers] * len(self.colnames)

        self.output_tuple = namedtuple("Output", self.colnames)

    def __getitem__(self, subject_id):
        row = self.paths.loc[subject_id]
        paths = {col: row[col] for col in self.colnames}
        study = {col: row[col] for col in self.studynames}
        series = {col: row[col] for col in self.seriesnames}
        subseries = {col: row[col] for col in self.subseriesnames}
        paths = {k: v if pd.notna(v) else None for k, v in paths.items()}

        if self.expand_paths:
            # paths = {col: glob.glob(path)[0] for col, path in paths.items()}
            paths = {
                col: glob.glob(path)[0] if pd.notna(path) else None
                for col, path in paths.items()
            }

        for i, (col, path) in enumerate(paths.items()):
            files = self.tree[subject_id][
                study["study_" + ("_").join(col.split("_")[1:])]
            ][series["series_" + ("_").join(col.split("_")[1:])]][
                subseries["subseries_" + ("_").join(col.split("_")[1:])]
            ]
            self.readers[i](
                path, series["series_" + ("_").join(col.split("_")[1:])]
            )
        outputs = {
            col: self.readers[i](
                path,
                series["series_" + ("_").join(col.split("_")[1:])],
                file_names=files,
            )
            for i, (col, path) in enumerate(paths.items())
        }
        return self.output_tuple(**outputs)

    def keys(self):
        return list(self.paths.index)

    def items(self):
        return ((k, self[k]) for k in self.keys())


class ImageCSVLoader(BaseLoader):
    def __init__(
        self,
        csv_path_or_dataframe,
        colnames=None,
        seriesnames=None,
        id_column=None,
        expand_paths=False,
        readers=None,
    ) -> None:
        if seriesnames is None:
            seriesnames = []
        if colnames is None:
            colnames = []
        if readers is None:
            readers = [
                read_image
            ]  # no mutable defaults https://florimond.dev/en/posts/2018/08/python-mutable-defaults-are-the-source-of-all-evil/

        self.expand_paths = expand_paths
        self.readers = readers

        self.colnames = colnames
        self.seriesnames = seriesnames
        if isinstance(csv_path_or_dataframe, str):
            if id_column is not None and id_column not in colnames:
                colnames.append(id_column)
            self.paths = pd.read_csv(
                csv_path_or_dataframe, index_col=id_column
            )
        elif isinstance(csv_path_or_dataframe, pd.DataFrame):
            self.paths = csv_path_or_dataframe
            if id_column:
                self.paths = self.paths.set_index(id_column)
            if len(self.colnames) == 0:
                self.colnames = self.paths.columns
        else:
            msg = f"Expected a path to csv file or pd.DataFrame, not {type(csv_path_or_dataframe)}."
            raise ValueError(msg)

        if not isinstance(readers, list):
            readers = [readers] * len(self.colnames)

        self.output_tuple = namedtuple("Output", self.colnames)

    def __getitem__(self, subject_id):
        row = self.paths.loc[subject_id]
        paths = {col: row[col] for col in self.colnames}
        series = {col: row[col] for col in self.seriesnames}
        paths = {k: v if pd.notna(v) else None for k, v in paths.items()}
        if self.expand_paths:
            # paths = {col: glob.glob(path)[0] for col, path in paths.items()}
            paths = {
                col: glob.glob(path)[0] if pd.notna(path) else None
                for col, path in paths.items()
            }

        outputs = {
            col: self.readers[i](
                path, series["series_" + ("_").join(col.split("_")[1:])]
            )
            for i, (col, path) in enumerate(paths.items())
        }
        return self.output_tuple(**outputs)

    def keys(self):
        return list(self.paths.index)

    def items(self):
        return ((k, self[k]) for k in self.keys())


class ImageFileLoader(BaseLoader):
    def __init__(
        self,
        root_directory,
        get_subject_id_from="filename",
        subdir_path=None,
        exclude_paths=None,
        reader=None,
    ) -> None:
        if exclude_paths is None:
            exclude_paths = []
        if reader is None:
            reader = read_image  # no mutable defaults https://florimond.dev/en/posts/2018/08/python-mutable-defaults-are-the-source-of-all-evil/

        self.root_directory = root_directory
        self.get_subject_id_from = get_subject_id_from
        self.subdir_path = subdir_path
        self.exclude_paths = []
        for path in exclude_paths:
            if not path.startswith(self.root_directory):
                full_paths = glob.glob(
                    pathlib.Path(root_directory, path).as_posix()
                )
                self.exclude_paths.extend(full_paths)
            else:
                full_path = path
                self.exclude_paths.append(full_path)
        self.reader = reader

        self.paths = self._generate_paths()

    def _generate_paths(self):
        paths = {}
        for f in os.scandir(self.root_directory):
            if f.path in self.exclude_paths:
                continue
            subject_dir_path = f.path
            if self.subdir_path:
                full_path = pathlib.Path(
                    subject_dir_path, self.subdir_path
                ).as_posix()
            else:
                full_path = subject_dir_path
            try:
                full_path = glob.glob(full_path)[0]
            except IndexError:
                continue
            if os.path.isdir(full_path):
                full_path = pathlib.Path(full_path, "").as_posix()
            subject_dir_name = os.path.basename(
                os.path.normpath(subject_dir_path)
            )
            subject_id = self._extract_subject_id_from_path(
                full_path, subject_dir_name
            )
            paths[subject_id] = full_path
        return paths

    def _extract_subject_id_from_path(self, full_path, subject_dir_name):
        filename, _ = os.path.splitext(os.path.basename(full_path))
        if isinstance(self.get_subject_id_from, str):
            if self.get_subject_id_from == "filename":
                subject_id = filename
            elif self.get_subject_id_from == "subject_directory":
                subject_id = subject_dir_name
            else:
                subject_id = re.search(self.get_subject_id_from, full_path)[0]
        else:
            return self.get_subject_id_from(
                full_path, filename, subject_dir_name
            )
        return subject_id

    def __getitem__(self, subject_id):
        path = self.paths[subject_id]
        return self.reader(path)

    def keys(self):
        return self.paths.keys()
