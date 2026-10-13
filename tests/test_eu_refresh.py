"""Offline safety checks for the EU source-snapshot workflow."""
import json
from pathlib import Path
import tempfile
import unittest

from rd_bridge import eu_refresh


def residue(identifier=10, **extra):
    return {"pesticide_residue_id": identifier,
            "pesticide_residue_name": "Acetamiprid",
            "pesticide_residue_version_nbr": 2,
            **extra}


def active(identifier=1, **extra):
    return {"substance_id": identifier, "substance_name": "Example",
            "substance_status": "Approved",
            "pesticide_residue_linked": "Acetamiprid",
            "cas_number": "123-45-6", **extra}


class FetchPagesTest(unittest.TestCase):
    def test_fetches_all_pages_and_preserves_extra_fields_and_duplicates(self):
        first = eu_refresh.RESIDUES_API
        next_url = first + "&skip=2"
        pages = {
            first: {"value": [residue(application_date="2027-04-01"),
                              residue(application_date="2027-04-01")],
                    "nextLink": next_url},
            next_url: {"value": [residue(11, another_future_field={"a": 1})]},
        }
        rows, count = eu_refresh.fetch_pages(first, eu_refresh.REQUIRED["residues"],
                                              pages.__getitem__)
        self.assertEqual((len(rows), count), (3, 2))
        self.assertEqual(sum("application_date" in x for x in rows), 2)
        self.assertTrue(any("another_future_field" in x for x in rows))

    def test_empty_result_fails(self):
        with self.assertRaisesRegex(RuntimeError, "empty"):
            eu_refresh.fetch_pages(eu_refresh.RESIDUES_API,
                                   eu_refresh.REQUIRED["residues"],
                                   lambda u: {"value": []})

    def test_missing_required_key_fails(self):
        with self.assertRaisesRegex(RuntimeError, "required"):
            eu_refresh.fetch_pages(eu_refresh.RESIDUES_API,
                                   eu_refresh.REQUIRED["residues"],
                                   lambda u: {"value": [{"pesticide_residue_id": 1}]})

    def test_malformed_payload_fails(self):
        for payload in (None, [], {}, {"value": {}}, {"value": ["bad"]}):
            with self.subTest(payload=payload), self.assertRaises(RuntimeError):
                eu_refresh.fetch_pages(eu_refresh.RESIDUES_API,
                                       eu_refresh.REQUIRED["residues"],
                                       lambda u: payload)

    def test_pagination_loop_and_page_limit_are_errors(self):
        url = eu_refresh.RESIDUES_API
        with self.assertRaisesRegex(RuntimeError, "loop"):
            eu_refresh.fetch_pages(url, eu_refresh.REQUIRED["residues"],
                                   lambda u: {"value": [residue()], "nextLink": url})
        with self.assertRaisesRegex(RuntimeError, "limit"):
            eu_refresh.fetch_pages(url, eu_refresh.REQUIRED["residues"],
                                   lambda u: {"value": [residue()],
                                              "nextLink": u + "&page=next"},
                                   max_pages=1)

    def test_nextlink_must_stay_on_source_host(self):
        with self.assertRaisesRegex(RuntimeError, "outside"):
            eu_refresh.fetch_pages(
                eu_refresh.RESIDUES_API, eu_refresh.REQUIRED["residues"],
                lambda u: {"value": [residue()],
                           "nextLink": "https://example.invalid/exfiltrate"})

    def test_bad_active_fields_fails(self):
        with self.assertRaisesRegex(RuntimeError, "required"):
            eu_refresh.fetch_pages(eu_refresh.ACTIVE_API,
                                   eu_refresh.REQUIRED["active_substances"],
                                   lambda u: {"value": [{"substance_id": 1,
                                                         "substance_name": "Example"}]})


class FullSourceStageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.approved = self.root / "data"
        self.approved.mkdir()
        (self.approved / "residues_en.json").write_text(
            json.dumps([residue()]), encoding="utf-8")
        (self.approved / "active_substances.json").write_text(
            json.dumps([{"substance_id": 1, "name": "Example", "cas": "123-45-6",
                         "approval_status": "Approved",
                         "pesticide_residue_linked": "Acetamiprid"}]), encoding="utf-8")
        self.staging = self.approved / "eu_sources"
        self.report = self.root / "report.md"

    def get_page(self, url):
        if url == eu_refresh.RESIDUES_API:
            return {"value": [residue(application_date="2027-04-01",
                                      new_opaque={"keep": True})]}
        if url == eu_refresh.ACTIVE_API:
            # Preserve the source's duplicated records and unknown attributes.
            return {"value": [active(extra_status_field="future"),
                              active(extra_status_field="future")]}
        raise AssertionError(url)

    def test_full_rows_staged_without_overwriting_approved_reference(self):
        original_residues = (self.approved / "residues_en.json").read_bytes()
        original_active = (self.approved / "active_substances.json").read_bytes()
        manifest = eu_refresh.stage(self.approved, self.staging, self.report,
                                    get_page=self.get_page)
        staged_residues = json.loads((self.staging / "residues_full.json").read_text())
        staged_active = json.loads((self.staging / "active_substances_full.json").read_text())
        self.assertEqual(staged_residues[0]["application_date"], "2027-04-01")
        self.assertEqual(staged_residues[0]["new_opaque"], {"keep": True})
        self.assertEqual(len(staged_active), 2)  # Full raw records, no deduplication.
        self.assertEqual(staged_active[0]["extra_status_field"], "future")
        self.assertEqual(manifest["legal_applicability"], "unverified")
        self.assertIn("application_date",
                      manifest["source"]["residues"]["date_field_candidates"])
        self.assertEqual((self.approved / "residues_en.json").read_bytes(), original_residues)
        self.assertEqual((self.approved / "active_substances.json").read_bytes(), original_active)
        self.assertFalse((self.approved / "residue_param_map.json").exists())
        self.assertIn("remains **unverified**", self.report.read_text())
        self.assertIn("| pesticide-residues | 1 | 1 | 1 | 0 | 0 |", self.report.read_text())

    def test_same_data_produces_stable_committed_snapshot(self):
        eu_refresh.stage(self.approved, self.staging, self.report, self.get_page)
        files = [p for p in self.staging.iterdir() if p.is_file()]
        before = {p.name: p.read_bytes() for p in files}
        eu_refresh.stage(self.approved, self.staging, self.report, self.get_page)
        self.assertEqual(before, {p.name: p.read_bytes() for p in files})

    def test_downsized_response_fails_before_writing_any_snapshot(self):
        old = [residue(i) for i in range(10)]
        (self.approved / "residues_en.json").write_text(json.dumps(old), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "suspiciously incomplete"):
            eu_refresh.stage(self.approved, self.staging, self.report, self.get_page)
        self.assertFalse(self.staging.exists())

    def test_second_endpoint_failure_does_not_write_partial_snapshot(self):
        def failed_active(url):
            if url == eu_refresh.ACTIVE_API:
                raise ConnectionError("EU API unavailable")
            return self.get_page(url)

        with self.assertRaises(ConnectionError):
            eu_refresh.stage(self.approved, self.staging, self.report, failed_active)
        self.assertFalse(self.staging.exists())

    def test_compatibility_projection_is_not_raw_snapshot(self):
        raw = [active(foo=1), active(foo=2), active(foo=1)]
        projection = eu_refresh.project_active_substances(raw)
        self.assertEqual(len(projection), 1)
        self.assertNotIn("foo", projection[0])
        self.assertEqual(len(raw), 3)


if __name__ == "__main__":
    unittest.main()
