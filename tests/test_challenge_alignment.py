import csv
import unittest
from pathlib import Path

from src.extract import extract_rules
from src.changes import build_changes


ROOT = Path(__file__).resolve().parents[1]


def _address_ids_for_cities(cities):
    with (ROOT / "incial-data" / "data" / "sample_addresses.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row["address_id"] for row in rows if row["postal_city"] in cities]


class ChallengeAlignmentTests(unittest.TestCase):
    def test_extract_rules_are_not_generic(self):
        rules = extract_rules(ROOT / "incial-data" / "corpus")
        self.assertGreaterEqual(len(rules), 5)
        jurisdictions = {rule["jurisdiction"] for rule in rules}
        self.assertIn("Berkeley, CA", jurisdictions)
        self.assertIn("Boston, MA", jurisdictions)
        self.assertIn("NJ", jurisdictions)
        self.assertIn("MA", jurisdictions)
        self.assertTrue(any(rule["status"] == "pending" for rule in rules))
        self.assertTrue(any(rule["conflict_flag"] for rule in rules))

    def test_city_specific_rules_do_not_cross_apply_to_other_cities(self):
        self.assertEqual(
            "unknown",
            __import__("src.apply", fromlist=["_"])._evaluate_rule({"status": "in_force", "jurisdiction": "Boston, MA"}, "Cambridge", "MA", "2026-10-01"),
        )
        self.assertEqual(
            "applies",
            __import__("src.apply", fromlist=["_"])._evaluate_rule({"status": "in_force", "jurisdiction": "MA"}, "Cambridge", "MA", "2026-10-01"),
        )

    def test_change_tracking_uses_real_test_cases(self):
        changes = build_changes(ROOT / "outputs" / "lookups.json", ROOT / "incial-data" / "dev" / "change_tests.json")
        for test_id in ["T1", "T2", "T3", "T4", "T5"]:
            self.assertIn(test_id, changes)
        self.assertFalse(not changes["T3"].get("conflict_flag_address_ids"))
        boston_cambridge_ids = set(_address_ids_for_cities(["Boston", "Cambridge"]))
        self.assertTrue(boston_cambridge_ids.intersection(changes["T4"]["affected_address_ids"]))


if __name__ == "__main__":
    unittest.main()
