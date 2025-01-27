import csv
import json
import os
import pathlib
import pickle
import shutil
from datetime import datetime, timezone

import h5py # type: ignore
import nrrd # type: ignore
import numpy as np
import SimpleITK as sitk
from skimage.measure import regionprops

from imgtools.utils import image_to_array

# ruff: noqa
class BaseWriter:
    def __init__(self, root_directory, filename_format, create_dirs=True):
        self.root_directory = root_directory
        self.filename_format = filename_format
        self.create_dirs = create_dirs
        if create_dirs and not os.path.exists(self.root_directory):
            os.makedirs(self.root_directory)

    def put(self, *args, **kwargs):
        raise NotImplementedError

    def _get_path_from_subject_id(self, subject_id, **kwargs):
        now = datetime.now(timezone.utc)
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H%M%S")
        date_time = date + "_" + time
        out_filename = self.filename_format.format(
            subject_id=subject_id, date=date, time=time, date_time=date_time, **kwargs
        )
        out_path = pathlib.Path(self.root_directory, out_filename).as_posix()
        out_dir = os.path.dirname(out_path)
        if self.create_dirs and not os.path.exists(out_dir):
            os.makedirs(
                out_dir, exist_ok=True
            )  # create subdirectories if specified in filename_format

        return out_path


class BaseSubjectWriter(BaseWriter):
    def __init__(
        self,
        root_directory,
        filename_format="{subject_id}.nii.gz",
        create_dirs=True,
        compress=True,
    ):
        super().__init__(root_directory, filename_format, create_dirs)
        self.root_directory = root_directory
        self.filename_format = filename_format
        self.create_dirs = create_dirs
        self.compress = compress
        if os.path.exists(self.root_directory):
            # delete the folder called {subject_id} that was made in the original BaseWriter / the one named {label_or_image}
            if os.path.basename(os.path.dirname(self.root_directory)) == "{subject_id}":
                shutil.rmtree(os.path.dirname(self.root_directory))
            elif "{label_or_image}{train_or_test}" in os.path.basename(self.root_directory):
                shutil.rmtree(self.root_directory)

    def put(
        self,
        subject_id,
        image,
        is_mask=False,
        nnunet_info=None,
        label_or_image: str = "images",
        mask_label: str = "",
        train_or_test: str = "Tr",
        **kwargs,
    ):
        if is_mask:
            # remove illegal characters for Windows/Unix
            badboys = r'<>:"/\|?*'
            for char in badboys:
                mask_label = mask_label.replace(char, "")

            # filename_format eh
            self.filename_format = (
                mask_label + ".nii.gz"
            )  # save the mask labels as their rtstruct names

        if nnunet_info:
            if label_or_image == "labels":
                filename = f"{subject_id}.nii.gz"  # naming convention for labels
            else:
                filename = self.filename_format.format(
                    subject_id=subject_id,
                    modality_index=nnunet_info["modalities"][nnunet_info["current_modality"]],
                )  # naming convention for images
            out_path = self._get_path_from_subject_id(
                filename, label_or_image=label_or_image, train_or_test=train_or_test
            )
        else:
            out_path = self._get_path_from_subject_id(self.filename_format, subject_id=subject_id)
        sitk.WriteImage(image, out_path, self.compress)

    def _get_path_from_subject_id(self, filename, **kwargs):
        root_directory = self.root_directory.format(
            **kwargs
        )  # replace the {} with the kwargs passed in from .put() (above)
        out_path = pathlib.Path(root_directory, filename).as_posix()
        out_dir = os.path.dirname(out_path)
        if self.create_dirs and not os.path.exists(out_dir):
            os.makedirs(
                out_dir, exist_ok=True
            )  # create subdirectories if specified in filename_format
        return out_path


class ImageFileWriter(BaseWriter):
    def __init__(
        self,
        root_directory,
        filename_format="{subject_id}.nii.gz",
        create_dirs=True,
        compress=True,
    ):
        super().__init__(root_directory, filename_format, create_dirs)
        self.compress = compress

    def put(self, subject_id, image, **kwargs):
        out_path = self._get_path_from_subject_id(subject_id, **kwargs)
        sitk.WriteImage(image, out_path, self.compress)


class SegNrrdWriter(BaseWriter):
    def __init__(
        self,
        root_directory,
        filename_format="{subject_id}.seg.nrrd",
        create_dirs=True,
        compress=True,
    ):
        super().__init__(root_directory, filename_format, create_dirs)
        if compress:
            self.compression_level = 9
        else:
            self.compression_level = 1

    def put(self, subject_id, mask, **kwargs):
        out_path = self._get_path_from_subject_id(subject_id, **kwargs)
        labels = [k for k in mask.roi_names]
        print(labels)

        origin = mask.GetOrigin()
        spacing = mask.GetSpacing()
        # direction = mask.GetDirection()

        space = "left-posterior-superior"  # everything is ITK read/write

        # fix reverted somewhere.... :''''(
        space_directions = [
            [spacing[0], 0.0, 0.0],
            [0.0, spacing[1], 0.0],
            [0.0, 0.0, spacing[2]],
        ]
        kinds = ["domain", "domain", "domain"]
        dims = 3

        # permute axes to original orientations
        if len(labels) > 1:
            arr = np.transpose(sitk.GetArrayFromImage(mask), [-1, -2, -3, -4])

            # add extra dimension to metadata
            space_directions.insert(0, [float("nan"), float("nan"), float("nan")])
            kinds.insert(0, "vector")
            dims += 1
        else:
            arr = np.transpose(sitk.GetArrayFromImage(mask), [-1, -2, -3])

        # ensure proper conversion to array
        assert mask.GetSize() == arr.shape[-3:]

        segment_info = {}
        for n, i in enumerate(labels):
            try:
                if len(labels) > 1:
                    props = regionprops(arr[n])[0]
                else:
                    props = regionprops(arr)[0]
                bbox = props["bbox"]
                bbox_segment = [bbox[0], bbox[3], bbox[1], bbox[4], bbox[2], bbox[5]]
            except IndexError:  # mask is empty
                assert arr[n].sum() == 0, "Mask not empty but 'skimage.measure.regionprops' failed."
                bbox_segment = [0, 0, 0, 0, 0, 0]

            segment_info[f"Segment{n}_Color"] = list(np.random.random(3))
            segment_info[f"Segment{n}_ColorAutoGenerated"] = "1"
            segment_info[f"Segment{n}_Extent"] = bbox_segment
            segment_info[f"Segment{n}_ID"] = str(n)
            segment_info[f"Segment{n}_Name"] = i
            segment_info[f"Segment{n}_NameautoGenerated"] = "0"

        header = {
            "dimension": dims,
            "space": space,
            "sizes": mask.GetSize(),
            "space directions": space_directions,
            "kinds": kinds,
            "endian": "little",
            "space origin": origin,
            "roi_names": labels,
            **segment_info,
        }

        nrrd.write(
            out_path,
            arr,
            header=header,
            compression_level=self.compression_level,
            **kwargs,
        )


class NumpyWriter(BaseWriter):
    def __init__(self, root_directory, filename_format="{subject_id}.npy", create_dirs=True):
        super().__init__(root_directory, filename_format, create_dirs)
        self.root_directory = root_directory
        self.filename_format = filename_format

    def put(self, subject_id, image, **kwargs):
        out_path = self._get_path_from_subject_id(subject_id, **kwargs)
        if isinstance(image, sitk.Image):
            array, *_ = image_to_array(image)  # TODO (Michal) optionally save the image geometry
        np.save(out_path, array)


class HDF5Writer(BaseWriter):
    def __init__(
        self,
        root_directory,
        filename_format="{subject_id}.h5",
        create_dirs=True,
        save_geometry=True,
    ):
        super().__init__(root_directory, filename_format, create_dirs)
        self.save_geometry = save_geometry

    def put(self, subject_id, images, metadata=None, **kwargs):
        out_path = self._get_path_from_subject_id(subject_id, **kwargs)
        with h5py.File(out_path, "w") as f:
            if not isinstance(images, dict):
                images = {"image": images}
            for k, v in images.items():
                array, origin, direction, spacing = image_to_array(v)
                dataset = f.create_dataset(k, data=array)
                dataset.attrs.create("subject_id", subject_id)
                if self.save_geometry:
                    dataset.attrs.create("origin", data=origin)
                    dataset.attrs.create("direction", data=direction)
                    dataset.attrs.create("spacing", data=spacing)
            if metadata:
                for k, attrs in metadata.items():
                    for name, v in attrs:
                        f[subject_id].attrs.create(name, data=v)


class MetadataWriter(BaseWriter):
    def __init__(
        self,
        root_directory,
        filename_format="{subject_id}.json",
        create_dirs=True,
        remove_existing=True,
    ):
        super().__init__(root_directory, filename_format, create_dirs)
        self.file_format = os.path.splitext(filename_format)[1].lstrip(".")
        self.remove_existing = remove_existing
        if self.file_format not in ["json", "csv", "pkl"]:
            raise ValueError(
                f"File format {self.file_format} not supported. Supported formats: JSON (.json), CSV (.csv), Pickle (.pkl)."
            )

        if self.file_format == "csv" and self.remove_existing:
            out_path = pathlib.Path(self.root_directory, self.filename_format).as_posix()
            if os.path.exists(out_path):
                os.remove(out_path)  # remove existing CSV instead of appending

    def _put_json(self, out_path, **kwargs):
        with open(out_path, "w") as f:
            json.dump(kwargs, f)

    def _put_csv(self, out_path, **kwargs):
        with open(out_path, "a+") as f:
            writer = csv.DictWriter(f, fieldnames=kwargs.keys())
            pos = f.tell()
            f.seek(0)
            sample = "\n".join([f.readline() for _ in range(2)])
            if sample == "\n" or not csv.Sniffer().has_header(sample):
                writer.writeheader()
            f.seek(pos)
            writer.writerow(kwargs)

    def _put_pickle(self, out_path, **kwargs):
        with open(out_path, "wb") as f:
            pickle.dump(kwargs, f)

    def put(self, subject_id, **kwargs):
        out_path = self._get_path_from_subject_id(subject_id)

        if "subject_id" not in kwargs:
            kwargs["subject_id"] = subject_id

        if self.file_format == "json":
            self._put_json(out_path, **kwargs)
        elif self.file_format == "csv":
            self._put_csv(out_path, **kwargs)
        elif self.file_format == "pkl":
            self._put_pickle(out_path, **kwargs)
