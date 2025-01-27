import datetime
import tempfile
from pathlib import Path

import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import UID, ExplicitVRLittleEndian

from imgtools.dicom.sort.sorter_base import resolve_path


@pytest.fixture(scope='module')
def dicom_test_file():
    """Pytest fixture to create a DICOM file for testing."""
    ds = Dataset()
    # Patient and instance-related metadata
    ds.PatientName = 'Test^Firstname'
    ds.PatientID = '123456'

    # Dates and times
    datetime.datetime.now()
    ds.ContentDate = '20021114'
    ds.ContentTime = '111131'  # Updated time format

    # Other metadata
    ds.SpecificCharacterSet = 'ISO_IR 100'
    ds.ImageType = ['ORIGINAL', 'PRIMARY', 'AXIAL']
    ds.StudyDate = '20021114'
    ds.SeriesDate = '20021114'
    ds.AcquisitionDate = '20021114'
    ds.StudyTime = '105444'
    ds.SeriesTime = '110039'
    ds.AcquisitionTime = '110234.982284'
    ds.Modality = 'CT'
    ds.Manufacturer = 'GE MEDICAL SYSTEMS'
    ds.StudyDescription = 'CT ABD & PELVIS W/O &'
    ds.SeriesDescription = '2.5SOFT + 30%ASIR'
    ds.ManufacturerModelName = 'LightSpeed VCT'
    ds.SeriesInstanceUID = UID('1.2.840.113619.2.55.3.604688.12345678.1234567890')
    ds.StudyInstanceUID = UID('1.2.840.113619.2.55.3.604688.98765432.9876543210')
    # File meta information
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = UID('1.2.840.10008.5.1.4.1.1.2')
    file_meta.MediaStorageSOPInstanceUID = UID(
        '1.3.6.1.4.1.14519.5.2.1.1706.4016.292639580813240923432069920621'
    )
    file_meta.ImplementationClassUID = UID('1.2.3.4')
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds.file_meta = file_meta

    # Create a temporary file
    temp_file = Path(tempfile.NamedTemporaryFile(suffix='.dcm', delete=False).name)
    ds.save_as(temp_file, write_like_original=False)

    yield temp_file

    # Cleanup
    temp_file.unlink()


class TestResolvePath:


    def test_resolve_path_with_absolute_path_no_truncate(self, dicom_test_file) -> None:
        path = dicom_test_file
        keys = {'PatientID', 'StudyInstanceUID'}
        format_str = '/resolved/path/%(PatientID)s/%(StudyInstanceUID)s'
        result = resolve_path(path, keys, format_str, truncate=False)
        assert result[0].resolve() == path.resolve()
        assert result[1].resolve() == Path(
            format_str
            % {
                'PatientID': '123456',
                'StudyInstanceUID': '1.2.840.113619.2.55.3.604688.98765432.9876543210',
            },
            path.name,
        ).resolve()

        # try again after explicitly touching the expected path
        format_str = '/tmp/path/%(PatientID)s/%(StudyInstanceUID)s'
        expected_path = Path(
            format_str
            % {
                'PatientID': '123456',
                'StudyInstanceUID': '1.2.840.113619.2.55.3.604688.98765432.9876543210',
            },
            path.name,
        )
        expected_path.parent.mkdir(parents=True, exist_ok=True)
        expected_path.touch()
        with pytest.raises(FileExistsError):
            result = resolve_path(path, keys, format_str, truncate=False)

    def test_resolve_path_with_absolute_path(self, dicom_test_file) -> None:
        path = dicom_test_file
        keys = {'PatientID', 'StudyInstanceUID'}
        format_str = '/resolved/path/%(PatientID)s/%(StudyInstanceUID)s'
        result = resolve_path(path, keys, format_str, truncate=True)
        assert result[0] == path
        assert (
            result[1]
            == Path(
                format_str % {'PatientID': '123456', 'StudyInstanceUID': '43210'}, path.name
            ).resolve()
        )

    def test_resolve_path_with_nonexistent_path(self, dicom_test_file) -> None:
        path = Path('/nonexistent/path/to/file.dcm')
        keys = {'PatientID', 'StudyInstanceUID'}
        format_str = '/resolved/path/%(PatientID)s/%(StudyInstanceUID)s'
        with pytest.raises(FileNotFoundError):
            resolve_path(path, keys, format_str)
