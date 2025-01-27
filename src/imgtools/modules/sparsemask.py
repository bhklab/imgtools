from typing import Dict

import numpy as np


class SparseMask:
    def __init__(
        self, mask_array: np.ndarray, roi_name_dict: Dict[str, int]
    ) -> None:
        self.mask_array = mask_array
        self.roi_name_dict = roi_name_dict
