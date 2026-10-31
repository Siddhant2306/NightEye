"""Preserved algorithm-independent comparison checks from the retired linear module."""
import unittest
import numpy as np
import pandas as pd
from src.helper.benchmark import align_reference


class BenchmarkAlignmentTests(unittest.TestCase):
    def fixture(self):
        frame=pd.DataFrame({"ticker":["A","B"],"group":["seen","unseen"],"close":[100.,200.],
                            "target":[.01,-.02],"target_date":pd.to_datetime(["2025-02-03","2025-02-04"])},
                           index=pd.to_datetime(["2025-01-02","2025-01-03"]))
        frame.index.name="Date"
        reference=frame.reset_index(); reference["xgboost"]=[.03,-.04]
        return frame,reference

    def test_aligns_stock_dates_not_row_order(self):
        frame,reference=self.fixture()
        np.testing.assert_allclose(align_reference(frame,reference.iloc[::-1]).xgboost,[.03,-.04])

    def test_rejects_changed_labels_or_membership(self):
        frame,reference=self.fixture(); reference.loc[0,"target"]=.4
        with self.assertRaises(ValueError): align_reference(frame,reference)
        frame,reference=self.fixture(); reference.loc[0,"ticker"]="OTHER"
        with self.assertRaises(ValueError): align_reference(frame,reference)

    def test_rejects_duplicate_or_different_target_date(self):
        frame,reference=self.fixture()
        with self.assertRaises(ValueError): align_reference(frame,pd.concat([reference,reference.iloc[:1]]))
        reference.loc[0,"target_date"]=pd.Timestamp("2025-02-05")
        with self.assertRaises(ValueError): align_reference(frame,reference)
