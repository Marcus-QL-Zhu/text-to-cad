from pathlib import Path
import tempfile
import unittest

from models.watch_kinematic.watch_kinematic.rule_space import (
    build_rule_space_report,
    validate_candidate,
    write_rule_space_dashboard,
)


class WatchRuleSpaceTests(unittest.TestCase):
    def test_report_contains_diverse_valid_candidates(self):
        report = build_rule_space_report()

        self.assertGreaterEqual(report["summary"]["candidate_count"], 12)
        self.assertGreaterEqual(report["summary"]["valid_count"], 5)
        self.assertGreaterEqual(report["summary"]["topology_family_count"], 3)
        self.assertGreaterEqual(len(report["summary"]["arbor_count_values"]), 3)
        self.assertGreaterEqual(len(report["summary"]["output_count_values"]), 2)
        self.assertGreaterEqual(len(report["summary"]["bridge_count_values"]), 2)
        self.assertIn("openworked", report["summary"]["visual_style_values"])
        self.assertIn("spiral_visual", report["summary"]["visual_style_values"])

    def test_valid_candidates_satisfy_transmission_and_assembly_checks(self):
        report = build_rule_space_report()
        valid_candidates = [
            candidate
            for candidate in report["candidates"]
            if candidate["validation"]["status"] == "valid"
        ]

        self.assertGreaterEqual(len(valid_candidates), 5)
        for candidate in valid_candidates:
            validation = validate_candidate(candidate)
            self.assertEqual("valid", validation["status"], candidate["candidate_id"])
            self.assertTrue(validation["checks"]["all_outputs_connected"])
            self.assertTrue(validation["checks"]["mesh_equations_satisfied"])
            self.assertTrue(validation["checks"]["compound_axes_satisfied"])
            self.assertTrue(validation["checks"]["all_arbors_supported"])
            self.assertTrue(validation["checks"]["bridge_screws_complete"])

    def test_invalid_candidates_explain_missing_support_and_disconnected_output(self):
        report = build_rule_space_report()
        invalid_reasons = {
            reason
            for candidate in report["candidates"]
            for reason in candidate["validation"]["reasons"]
        }

        self.assertIn("missing_upper_support", invalid_reasons)
        self.assertIn("output_not_connected_to_drive", invalid_reasons)

    def test_dashboard_is_human_readable_and_contains_svg_maps(self):
        report = build_rule_space_report()
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "rule_space_dashboard.html"

            written = write_rule_space_dashboard(report, output_path)

            self.assertEqual(output_path, written)
            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Gate A1.5", html)
            self.assertIn("规则空间采样验证", html)
            self.assertIn("候选拓扑", html)
            self.assertIn("失败原因", html)
            self.assertIn("<svg", html)
            self.assertIn("valid", html)
            self.assertIn("invalid", html)


if __name__ == "__main__":
    unittest.main()
