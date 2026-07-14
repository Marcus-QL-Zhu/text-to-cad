import tempfile
import unittest
from pathlib import Path

from models.watch_kinematic.watch_kinematic.bridge_partition_loop import (
    run_bridge_partition_loop,
)


class WatchBridgePartitionLoopTests(unittest.TestCase):
    def test_loop_solves_two_batches_with_scheme_b_only(self):
        report = run_bridge_partition_loop(axis_seeds=[42, 314], target_count_per_seed=5, output_dir=None)

        self.assertEqual("watch_bridge_partition_loop_report", report["kind"])
        self.assertEqual("pass", report["status"])
        self.assertEqual([42, 314], report["axis_seeds"])
        self.assertEqual(10, len(report["layouts"]))
        self.assertEqual([], report["hard_failures"])
        self.assertEqual({"A": 0, "B": 10}, report["scheme_counts"])

        for layout in report["layouts"]:
            with self.subTest(layout=layout["layout_id"]):
                self.assertEqual("pass", layout["selected_status"])
                self.assertEqual("B", layout["selected_scheme"])
                self.assertIn("A", layout["scheme_results"])
                self.assertIn("B", layout["scheme_results"])
                self.assertEqual("pass", layout["scheme_results"]["B"]["hard_status"])

    def test_selected_partitions_have_required_validation_facts(self):
        report = run_bridge_partition_loop(axis_seeds=[42, 314], target_count_per_seed=5, output_dir=None)

        for layout in report["layouts"]:
            selected = layout["selected_result"]
            with self.subTest(layout=layout["layout_id"]):
                self.assertEqual("pass", selected["hard_status"])
                self.assertEqual([], selected["hard_failures"])
                self.assertIn("coverage", selected)
                self.assertIn("seam_checks", selected)
                self.assertIn("connectivity", selected)
                self.assertIn("fastener_service", selected)
                for bridge_id in ["barrel_bridge", "train_bridge", "escapement_bridge"]:
                    self.assertEqual("pass", selected["coverage"][bridge_id])
                    self.assertIn(bridge_id, selected["connectivity"])
                    self.assertIn(bridge_id, selected["fastener_service"])

    def test_loop_writes_review_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_bridge_partition_loop(
                axis_seeds=[42, 314],
                target_count_per_seed=5,
                output_dir=Path(tmp),
            )

            self.assertEqual("pass", report["status"])
            for artifact_name in [
                "axis_layout_contact_sheet",
                "selected_partition_contact_sheet",
                "scheme_a_contact_sheet",
                "scheme_b_contact_sheet",
                "bridge_partition_loop_report",
                "subagent_review_prompt",
            ]:
                self.assertIn(artifact_name, report["artifacts"])
                self.assertTrue(Path(report["artifacts"][artifact_name]).exists())

            prompt = Path(report["artifacts"]["subagent_review_prompt"]).read_text(encoding="utf-8")
            self.assertIn("visual_status: pass | fail", prompt)
            self.assertIn("selected scheme is B-only weighted Voronoi", prompt)

            for image_name in [
                "axis_layout_contact_sheet",
                "selected_partition_contact_sheet",
                "scheme_a_contact_sheet",
                "scheme_b_contact_sheet",
            ]:
                image_path = Path(report["artifacts"][image_name])
                self.assertGreater(image_path.stat().st_size, 10_000)
                self.assertEqual(b"\x89PNG\r\n\x1a\n", image_path.read_bytes()[:8])

    def test_scheme_a_and_b_report_distinct_topology_rules(self):
        report = run_bridge_partition_loop(axis_seeds=[42, 314], target_count_per_seed=5, output_dir=None)

        for layout in report["layouts"]:
            with self.subTest(layout=layout["layout_id"]):
                scheme_a = layout["scheme_results"]["A"]
                scheme_b = layout["scheme_results"]["B"]
                self.assertEqual("A", scheme_a["scheme"])
                self.assertEqual("B", scheme_b["scheme"])
                self.assertIn("scheme_a_multiple_outer_arcs", scheme_a["known_failure_reasons"])
                self.assertIn("scheme_b_invalid_short_island_pad", scheme_b["known_failure_reasons"])
                for service_list in scheme_b["fastener_service"].values():
                    for service in service_list:
                        if service["span_deg"] < 40.0:
                            self.assertEqual("full_span_under_40_deg", service["pad_policy"])
                            self.assertEqual(1, service["screw_count"])

    def test_scheme_a_is_report_only_even_when_it_passes(self):
        report = run_bridge_partition_loop(axis_seeds=[42, 314], target_count_per_seed=5, output_dir=None)

        a_pass_layouts = [
            layout for layout in report["layouts"]
            if layout["scheme_results"]["A"]["hard_status"] == "pass"
        ]
        self.assertGreaterEqual(len(a_pass_layouts), 1)
        for layout in a_pass_layouts:
            self.assertEqual("B", layout["selected_scheme"])

    def test_scheme_b_fallbacks_have_valid_service_islands(self):
        report = run_bridge_partition_loop(axis_seeds=[42, 314], target_count_per_seed=5, output_dir=None)

        for layout in report["layouts"]:
            selected = layout["selected_result"]
            with self.subTest(layout=layout["layout_id"]):
                self.assertEqual("pass", selected["hard_status"])
                self.assertEqual("B", layout["selected_scheme"])
                self.assertEqual(
                    "weighted_voronoi_partition_with_envelope_priority_and_service_islands",
                    selected["topology"],
                )
                policy = selected["service_island_policy"]
                self.assertEqual("full_span_under_40_deg", policy["short_island_pad"])
                self.assertEqual("local_bridge_boundary", policy["pad_side_reference"])
                self.assertEqual(
                    [
                        {"max_exclusive": 40.0, "screw_count": 1},
                        {"min_inclusive": 40.0, "max_inclusive": 90.0, "screw_count": 2},
                        {"min_exclusive": 90.0, "screw_count": 3},
                    ],
                    policy["screw_count_by_span_deg"],
                )
                for bridge_id, services in selected["fastener_service"].items():
                    self.assertGreaterEqual(len(services), 1, bridge_id)
                    for service in services:
                        self.assertGreater(service["span_deg"], 0.0)
                        self.assertIn(service["screw_count"], {1, 2, 3})
                        self.assertEqual("local_bridge_boundary", service["pad_side_reference"])
                    if service["span_deg"] < 40.0:
                        self.assertEqual("full_span_under_40_deg", service["pad_policy"])
                        self.assertEqual(1, service["screw_count"])

    def test_scheme_b_has_exactly_one_functional_envelope_per_bridge(self):
        report = run_bridge_partition_loop(axis_seeds=[42, 314], target_count_per_seed=5, output_dir=None)

        for layout in report["layouts"]:
            selected = layout["selected_result"]
            with self.subTest(layout=layout["layout_id"]):
                self.assertEqual("B", layout["selected_scheme"])
                self.assertEqual("pass", selected["envelope_assignment_status"])
                for bridge_id, facts in selected["envelope_assignment"].items():
                    self.assertEqual([bridge_id], facts["owned_envelopes"])
                    self.assertEqual([], facts["foreign_envelopes"])

    def test_scheme_b_reports_manufacturable_boundaries(self):
        report = run_bridge_partition_loop(axis_seeds=[42, 314], target_count_per_seed=5, output_dir=None)

        for layout in report["layouts"]:
            selected = layout["selected_result"]
            with self.subTest(layout=layout["layout_id"]):
                self.assertEqual("B", layout["selected_scheme"])
                self.assertEqual("pass", selected["manufacturing_boundary_status"])
                self.assertEqual(2, len(selected["manufacturing_boundaries"]))
                for boundary in selected["manufacturing_boundaries"]:
                    self.assertLessEqual(boundary["control_point_count"], 3)
                    self.assertGreaterEqual(boundary["minimum_turn_angle_deg"], 75.0)
                    self.assertGreaterEqual(boundary["offset_from_reference_mm"], 0.35)
                    self.assertEqual("offset_away_from_protected_envelope", boundary["offset_policy"])
                    self.assertEqual("pass", boundary["envelope_crossing_status"])
                    self.assertEqual([], boundary["crossed_envelopes"])
                    self.assertEqual("pass", boundary["status"])

    def test_selected_partitions_do_not_cover_wrong_envelope_group(self):
        report = run_bridge_partition_loop(axis_seeds=[42, 314], target_count_per_seed=5, output_dir=None)

        for layout in report["layouts"]:
            selected = layout["selected_result"]
            with self.subTest(layout=layout["layout_id"]):
                self.assertEqual("pass", selected["envelope_ownership_status"])
                self.assertNotIn("bridge_region_covers_wrong_envelope_group", selected["hard_failures"])
                self.assertIn("bridge_region_covers_wrong_envelope_group", selected["known_failure_reasons"])
                for bridge_id in ["barrel_bridge", "train_bridge", "escapement_bridge"]:
                    ownership = selected["envelope_ownership"][bridge_id]
                    self.assertEqual(bridge_id, ownership["expected_bridge"])
                    self.assertEqual("pass", ownership["status"])
                    self.assertEqual([], ownership["wrong_bridge_hits"])

    def test_selected_partitions_only_cover_matching_functional_envelopes(self):
        report = run_bridge_partition_loop(axis_seeds=[42, 314], target_count_per_seed=5, output_dir=None)

        for layout in report["layouts"]:
            selected = layout["selected_result"]
            with self.subTest(layout=layout["layout_id"]):
                self.assertIn(
                    "bridge_region_covers_wrong_envelope_group",
                    selected["known_failure_reasons"],
                )
                self.assertIn("envelope_ownership", selected)
                for bridge_id in ["barrel_bridge", "train_bridge", "escapement_bridge"]:
                    facts = selected["envelope_ownership"][bridge_id]
                    self.assertEqual(bridge_id, facts["expected_bridge_id"])
                    self.assertGreater(facts["sample_count"], 0)
                    self.assertEqual(0, facts["wrong_label_count"])
                    self.assertEqual([], facts["wrong_label_bridge_ids"])


if __name__ == "__main__":
    unittest.main()
