from pathlib import Path
import unittest

from models.watch_kinematic.watch_kinematic.pattern_card_checklist import (
    ChecklistItem,
    run_pattern2_bridge_checklist,
    write_pattern2_checklist_artifacts,
)


class PatternCardChecklistTests(unittest.TestCase):
    def test_checklist_items_have_checkbox_fields(self):
        item = ChecklistItem(
            check_id="example",
            label="Example",
            status="pass",
            evidence={"ok": True},
        )

        payload = item.to_dict()

        self.assertIs(True, payload["checked"])
        self.assertEqual("pass", payload["status"])
        self.assertEqual("example", payload["check_id"])


    def test_pattern2_checklist_reports_required_bridge_checks(self):
        report = run_pattern2_bridge_checklist(seed=8459, generate_step=False)

        check_ids = {item["check_id"] for item in report["items"]}

        self.assertIn("required_bridge_entities_exist", check_ids)
        self.assertIn("supported_bearings_covered_by_bridge_footprints", check_ids)
        self.assertIn("lightening_windows_required_and_valid", check_ids)
        self.assertIn("screws_inside_service_pads", check_ids)


    def test_bad_review_seeds_are_no_longer_false_passes(self):
        for seed in [36627, 14869, 62525]:
            with self.subTest(seed=seed):
                report = run_pattern2_bridge_checklist(seed=seed, generate_step=False)
                self.assertEqual("fail", report["status"])
                self.assertTrue(report["failed_items"])
                failure_ids = {item["check_id"] for item in report["failed_items"]}
                self.assertTrue(
                    {
                        "supported_bearings_covered_by_bridge_footprints",
                        "screws_inside_service_pads",
                        "final_bridge_solids_have_volume",
                    }
                    & failure_ids
                )

    def test_pattern2_seed_8459_service_pads_attach_to_bridge_body(self):
        report = run_pattern2_bridge_checklist(seed=8459, generate_step=False)

        failure_ids = {item["check_id"] for item in report["failed_items"]}

        self.assertNotIn("screws_inside_service_pads", failure_ids)
        self.assertEqual("pass", report["status"])


    def test_pattern2_checklist_artifacts_write_json_and_html(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            report = write_pattern2_checklist_artifacts(Path(tmp), seed=8459, generate_step=False)

            json_path = Path(report["artifacts"]["checklist_json"])
            html_path = Path(report["artifacts"]["checklist_html"])

            self.assertTrue(json_path.exists())
            self.assertTrue(html_path.exists())
            html = html_path.read_text(encoding="utf-8")
            self.assertIn('type="checkbox"', html)
            self.assertIn("required_bridge_entities_exist", html)


if __name__ == "__main__":
    unittest.main()
