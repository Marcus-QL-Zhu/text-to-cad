from pathlib import Path
import unittest

from build123d import Box, Location

from models.watch_kinematic.watch_kinematic import power_chain_mvp as p
from models.watch_kinematic.watch_kinematic.pattern_card_checklist import (
    ChecklistItem,
    REQUIRED_PATTERN2_BRIDGE_IDS,
    _bridge_plate_seams_have_real_gap,
    _build_pattern2_design_and_bridge_stage,
    run_pattern2_bridge_checklist,
    write_pattern2_checklist_artifacts,
)
from models.watch_kinematic.watch_kinematic.partitioned_bridge_stage import _make_analytic_bridge_stage
from models.watch_kinematic.watch_kinematic.partitioned_bridge_stage import _angular_span_inside_domain
from models.watch_kinematic.watch_kinematic.partitioned_bridge_stage import _clip_final_bridge_solids_to_case


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
        for seed in [36627, 14869]:
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

        report = run_pattern2_bridge_checklist(seed=62525, generate_step=False)
        failure_ids = {item["check_id"] for item in report["failed_items"]}

        self.assertEqual("fail", report["status"])
        self.assertIn("final_bridge_solids_have_volume", failure_ids)

    def test_bridge_seam_gap_rule_rejects_a_narrow_gap(self):
        left = {
            "bridge_id": "left_bridge",
            "footprint": {"points": [(0, 0), (1, 0), (1, 1), (0, 1)]},
            "support_pads": [],
        }
        right = {
            "bridge_id": "right_bridge",
            "footprint": {"points": [(2, 0), (3, 0), (3, 1), (2, 1)]},
            "support_pads": [],
        }

        result = _bridge_plate_seams_have_real_gap([left, right])

        self.assertEqual("fail", result.status)
        self.assertLess(result.evidence["pairs"][0]["minimum_gap_mm"], p.BRIDGE_SEAM_GAP_WIDTH_MM)

    def test_pattern2_seed_8459_service_pads_attach_to_bridge_body(self):
        report = run_pattern2_bridge_checklist(seed=8459, generate_step=False)

        failure_ids = {item["check_id"] for item in report["failed_items"]}
        item_by_id = {item["check_id"]: item for item in report["items"]}

        self.assertNotIn("screws_inside_service_pads", failure_ids)
        self.assertNotIn("bridge_plate_seams_have_real_gap", failure_ids)
        self.assertEqual("pass", item_by_id["screws_inside_service_pads"]["status"])
        self.assertEqual("pass", item_by_id["supported_bearings_covered_by_bridge_footprints"]["status"])
        self.assertEqual("pass", report["status"])
        for pair in item_by_id["bridge_plate_seams_have_real_gap"]["evidence"]["pairs"]:
            self.assertGreaterEqual(pair["minimum_gap_mm"] + 0.01, pair["required_gap_mm"])


    def test_pattern2_seed_8459_final_bridge_solids_are_preserved_and_inside_case(self):
        with self.assertRaisesRegex(ValueError, "case clip removed an entire bridge solid"):
            _clip_final_bridge_solids_to_case(
                [Box(1.0, 1.0, 1.0).located(Location((100.0, 0.0, 0.0)))],
                support_top=0.0,
                z_max=1.0,
            )

        design, bridge_stage = _build_pattern2_design_and_bridge_stage(8459)
        stage_bridges = {bridge["bridge_id"]: bridge for bridge in bridge_stage["bridges"]}
        for bridge in bridge_stage["bridges"]:
            for pad in bridge["support_pads"]:
                self.assertTrue(
                    _angular_span_inside_domain(
                        float(pad["angular_start_deg"]),
                        float(pad["angular_end_deg"]),
                        float(pad["domain_start_deg"]),
                        float(pad["domain_end_deg"]),
                    )
                )
        bridge_children = {
            str(getattr(child, "label", "")): child
            for child in _make_analytic_bridge_stage(design)
            if str(getattr(child, "label", "")) in REQUIRED_PATTERN2_BRIDGE_IDS
        }

        self.assertEqual(set(REQUIRED_PATTERN2_BRIDGE_IDS), set(bridge_children))
        for bridge_id, bridge in bridge_children.items():
            with self.subTest(bridge_id=bridge_id):
                solids = list(bridge.solids())
                aggregate_volume = sum(float(solid.volume) for solid in solids)
                self.assertTrue(solids)
                self.assertGreaterEqual(len(solids), len(stage_bridges[bridge_id]["support_pads"]) + 1)
                self.assertGreater(aggregate_volume, 2.0)
                self.assertEqual(bridge_id, bridge.label)
                expected_rgba = p._review_material_for_label(bridge_id)["rgba"]
                for actual, expected in zip(tuple(bridge.color), expected_rgba):
                    self.assertAlmostEqual(actual, expected, places=5)

                bbox = bridge.bounding_box()
                self.assertLess(float(bbox.min.Z), float(stage_bridges[bridge_id]["z_min_mm"]))
                clip_height = float(bbox.max.Z) - float(bbox.min.Z) + 0.2
                case_cylinder = p._z_cylinder(p.CASE_RADIUS_MM, clip_height).located(
                    Location((0, 0, (float(bbox.min.Z) + float(bbox.max.Z)) / 2.0))
                )
                outside_volume = sum(
                    sum(float(outside_solid.volume) for outside_solid in (solid - case_cylinder).solids())
                    for solid in solids
                )
                self.assertLessEqual(outside_volume, 1e-9)


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
