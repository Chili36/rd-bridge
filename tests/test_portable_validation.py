import unittest
from scripts import validate_monitoring
from scripts.portable_validation import reconstruct_baseline

class PortableBaselineTest(unittest.TestCase):
    def test_baseline_indices(self):
        rows = reconstruct_baseline()
        self.assertEqual(len(rows), 684)
        idx = validate_monitoring.indices(rows)
        self.assertEqual(len(idx["whole"]), 623)
        self.assertEqual(len(idx["component"]), 730)
        self.assertEqual(validate_monitoring.category("RF-0014-001-PPP", idx), ("whole", 10))
