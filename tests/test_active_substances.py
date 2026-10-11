"""EU active-substances snapshot fetching and API safety checks."""
import unittest

from rd_bridge.fetch_active_substances import fetch_all


class FetchActiveSubstancesTest(unittest.TestCase):
    def test_pages_are_followed_and_identical_rows_deduplicated(self):
        row = {"substance_id": 42, "substance_name": "Azamethiphos",
               "cas_number": "35575-96-3", "substance_status": "Not approved",
               "pesticide_residue_linked": "Default MRL of 0.01 mg/kg according to Art 18(1)(b)"}
        other = {**row, "pesticide_residue_linked": "A different definition"}
        pages = {"start": {"value": [row, row], "nextLink": "page2"},
                 "page2": {"value": [row, other], "nextLink": None}}
        seen = []

        def get(url):
            seen.append(url)
            return pages[url]

        actual = fetch_all(url="start", get_page=get)
        self.assertEqual(seen, ["start", "page2"])
        self.assertEqual(len(actual), 2)  # retain distinct linked definitions
        self.assertEqual(actual[0]["name"], "Azamethiphos")
        self.assertEqual(actual[0]["approval_status"], "Not approved")

    def test_empty_data_fails_closed(self):
        with self.assertRaises(RuntimeError):
            fetch_all(url="start", get_page=lambda u: {"value": [], "nextLink": None})

    def test_schema_change_fails_closed(self):
        with self.assertRaises(RuntimeError):
            fetch_all(url="start", get_page=lambda u: {"value": [{"substance_name": "X"}],
                                                        "nextLink": None})

    def test_pagination_cycle_fails_closed(self):
        row = {"substance_name": "X", "substance_status": "Pending",
               "pesticide_residue_linked": ""}
        with self.assertRaises(RuntimeError):
            fetch_all(url="start", get_page=lambda u: {"value": [row], "nextLink": "start"})


if __name__ == "__main__":
    unittest.main()
