from typing import Dict, List, Union

import numpy as np
import pytest

from imgtools.modules.structureset.structure_set import (  # type: ignore
    StructureSet,
)


@pytest.fixture
def roi_points() -> Dict[str, List[np.ndarray]]:
    """Fixture for mock ROI points."""
    return {
        "GTV": [np.array([[0, 0, 0], [1, 1, 1]])],
        "PTV": [np.array([[2, 2, 2], [3, 3, 3]])],
        "CTV_0": [np.array([[4, 4, 4], [5, 5, 5]])],
        "CTV_1": [np.array([[6, 6, 6], [7, 7, 7]])],
        "CTV_2": [np.array([[8, 8, 8], [9, 9, 9]])],
        "ExtraROI": [np.array([[10, 10, 10], [11, 11, 11]])],
    }


@pytest.fixture
def metadata() -> Dict[str, str]:
    """Fixture for mock metadata."""
    return {"PatientName": "John Doe"}


"""
test_assign_labels 

- this is essentially the first step of `to_segmentation`
- it assigns labels to the ROIs based on the names provided

main args involved in this step:
- roi_names: str | List[str] | Dict[str, Union[str, List[str]]] | None = None,
    ROI Names to assign labels to. 
- roi_select_first: bool = False,
    Whether to select only the first match for each pattern.
- roi_separate: bool = False,
    If True, assigns separate labels to each matching ROI within a regex pattern, appending
    a numerical suffix to the ROI name (e.g., "CTV_0", "CTV_1"). Default is False.

in these parameters, the first parameter is what you could theoretically pass to `to_segmentation` to get the same result

"""


# Parametrized tests for simple and moderately complex cases
@pytest.mark.parametrize(
    "names, roi_select_first, roi_separate, expected",
    [
        # Case 1: Default behavior with exact matches
        (["GTV", "PTV"], False, False, {"GTV": 0, "PTV": 1}),
        # Case 2: Regex matching
        (["GTV", "P.*"], False, False, {"GTV": 0, "PTV": 1}),
        # Case 3: Select only the first match for each pattern
        (["G.*", "P.*"], True, False, {"GTV": 0, "PTV": 1}),
        # Case 4: Separate matches for regex pattern
        (["P.*"], False, True, {"PTV": 0}),
        # Case 5: Regex pattern with multiple matches (consolidated labels)
        (["CTV.*"], False, False, {"CTV_0": 0, "CTV_1": 0, "CTV_2": 0}),
        # Case 6: Regex pattern with multiple matches (separate labels)
        (["CTV.*"], False, True, {"CTV_0": 0, "CTV_1": 0, "CTV_2": 0}),
        # Case 7: Grouped patterns
        (
            [["GTV", "PTV"], "CTV.*"],
            False,
            False,
            {"GTV": 0, "PTV": 0, "CTV_0": 1, "CTV_1": 1, "CTV_2": 1},
        ),
        # Case 8: Grouped patterns with separate labels for regex matches
        # ([["GTV", "PTV"], "CTV.*"], False, True, {"GTV": 0, "PTV": 0, "CTV_0": 1, "CTV_1": 2, "CTV_2": 3}),
    ],
)
def test_assign_labels(
    names: Union[List[str], List[List[str]]],
    roi_select_first: bool,
    roi_separate: bool,
    expected: Dict[str, int],
    roi_points: Dict[str, List[np.ndarray]],
) -> None:
    """Test _assign_labels method with various cases."""
    structure_set = StructureSet(roi_points)
    result = structure_set._assign_labels(names, roi_select_first, roi_separate)
    assert result == expected


# Parametrized tests for complex scenarios with intricate patterns
@pytest.mark.parametrize(
    "names, roi_select_first, roi_separate, expected",
    [
        # Case 1: Complex regex patterns with partial matches
        (
            ["G.*", "C.*1", "Extra.*"],
            False,
            False,
            {"GTV": 0, "CTV_1": 1, "ExtraROI": 2},
        ),
        # Case 2: Nested regex patterns with grouped and separated labels
        (
            [["GTV", "CTV.*"], "P.*", "Extra.*"],
            False,
            False,
            {"GTV": 0, "CTV_0": 0, "CTV_1": 0, "CTV_2": 0, "PTV": 1, "ExtraROI": 2},
        ),
        # ([["GTV", "CTV.*"], "P.*", "Extra.*"], False, True, {"GTV": 0, "CTV_0_0": 1, "CTV_1_1": 2, "CTV_2_2": 3, "PTV": 4, "ExtraROI": 5}),
        # Case 3: Regex patterns that match all ROIs
        (
            [".*"],
            False,
            False,
            {"GTV": 0, "PTV": 0, "CTV_0": 0, "CTV_1": 0, "CTV_2": 0, "ExtraROI": 0},
        ),
        # ([".*"], False, True, {"GTV_0": 0, "PTV_1": 1, "CTV_0_2": 2, "CTV_1_3": 3, "CTV_2_4": 4, "ExtraROI_5": 5}),
        # Case 4: Overlapping regex patterns
        (
            ["G.*", "C.*", "Extra.*"],
            False,
            False,
            {"GTV": 0, "CTV_0": 1, "CTV_1": 1, "CTV_2": 1, "ExtraROI": 2},
        ),
        # (["G.*", "C.*", "Extra.*"], False, True, {"GTV": 0, "CTV_0_0": 1, "CTV_1_1": 2, "CTV_2_2": 3, "ExtraROI_3": 4}),
        # Case 5: No matches for given patterns
        pytest.param(
            ["NonExistent.*"],
            False,
            False,
            {},
            marks=pytest.mark.xfail(raises=ValueError),
        ),
        # Case 6: Conflicting options (should raise an error)
        # pytest.param(["G.*"], True, True, None, marks=pytest.mark.xfail(raises=ValueError)),
    ],
)
def test_assign_labels_complex(
    names: Union[List[str], List[List[str]]],
    roi_select_first: bool,
    roi_separate: bool,
    expected: Dict[str, int],
    roi_points: Dict[str, List[np.ndarray]],
) -> None:
    """Test _assign_labels method with complex scenarios."""
    structure_set = StructureSet(roi_points)
    result = structure_set._assign_labels(names, roi_select_first, roi_separate)
    assert result == expected


def test_assign_labels_invalid(roi_points: Dict[str, List[np.ndarray]]) -> None:
    """Test _assign_labels method with invalid inputs."""
    structure_set = StructureSet(roi_points)

    # Case: Empty names
    with pytest.raises(ValueError, match="The 'names' list cannot be empty."):
        structure_set._assign_labels([])

    # Case: Conflicting options
    with pytest.raises(
        ValueError,
        match="The options 'roi_select_first' and 'roi_separate' cannot both be True.",
    ):
        structure_set._assign_labels(["G.*"], roi_select_first=True, roi_separate=True)


def test_init(roi_points: Dict[str, List[np.ndarray]], metadata: Dict[str, str]) -> None:
    """Test StructureSet initialization."""
    structure_set = StructureSet(roi_points, metadata)
    assert structure_set.roi_points == roi_points
    assert structure_set.metadata == metadata

    # Test default metadata
    structure_set_no_metadata = StructureSet(roi_points)
    assert structure_set_no_metadata.metadata == {}
