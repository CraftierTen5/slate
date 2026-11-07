"""Regression tests for gaps found probing PR #15 helpers with untested inputs."""
import os, sys, unittest
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
from slate_core.jobs_curation import normalize_location, cross_source_hint, deadline_passed

NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


def L(source, sid, location, title="Engineer", company="X"):
    return {"source": source, "sourceId": sid, "title": title, "company": company,
            "location": location}


class HintGuards(unittest.TestCase):
    def test_different_remote_regions_are_not_hinted(self):
        self.assertIsNone(cross_source_hint(L("a", "1", "Remote, US"), L("b", "9", "Remote, India")))

    def test_same_first_city_different_extra_locations_not_hinted(self):
        self.assertIsNone(cross_source_hint(L("a", "1", "Pune, Goa"), L("b", "9", "Pune, Maharashtra")))
        self.assertIsNone(cross_source_hint(L("a", "1", "Pune, Mumbai"), L("b", "9", "Pune")))

    def test_different_primary_city_is_not_hinted(self):
        self.assertIsNone(cross_source_hint(L("a", "1", "Pune, Goa"), L("b", "9", "Goa, Pune-x")))

    def test_remote_format_differences_are_not_hinted_conservatively(self):
        # "Remote, US" vs "Remote - US" vs "Remote (US)" are not proven equal: no hint.
        self.assertIsNone(cross_source_hint(L("a", "1", "Remote, US"), L("b", "9", "Remote - US")))
        self.assertIsNone(cross_source_hint(L("a", "1", "Remote, US"), L("b", "9", "Remote (US)")))

    def test_same_source_distinct_requisitions_are_not_hinted(self):
        self.assertIsNone(cross_source_hint(L("a", "1", "Pune"), L("a", "2", "Pune")))

    def test_blank_location_is_not_hinted(self):
        self.assertIsNone(cross_source_hint(L("a", "1", ""), L("b", "9", "")))

    def test_missing_identity_fields_do_not_crash(self):
        self.assertIsNone(cross_source_hint({}, L("b", "9", "Pune")))

    def test_same_full_location_set_still_hinted(self):
        self.assertIsNotNone(cross_source_hint(L("a", "1", "Bangalore, India"), L("b", "9", "Bengaluru, India")))
        self.assertIsNotNone(cross_source_hint(L("a", "1", "Pune, Mumbai"), L("b", "9", "Mumbai / Pune")))

    def test_same_remote_label_still_hinted(self):
        self.assertIsNotNone(cross_source_hint(L("a", "1", "Remote, US"), L("b", "9", "remote,  us")))


class Compat(unittest.TestCase):
    def test_normalize_location_first_city_and_remote_region(self):
        self.assertEqual(normalize_location("Pune/Mumbai"), "pune")
        self.assertEqual(normalize_location("Remote, US"), "remote, us")
        self.assertEqual(normalize_location(5), "")


class NowGuard(unittest.TestCase):
    def test_naive_now_is_rejected_clearly(self):
        with self.assertRaises(ValueError):
            deadline_passed("2026-11-01T00:00:00+00:00", datetime(2026, 11, 8))

    def test_non_string_deadline_is_unknown(self):
        self.assertIsNone(deadline_passed(20261101, NOW))


if __name__ == "__main__":
    unittest.main()
