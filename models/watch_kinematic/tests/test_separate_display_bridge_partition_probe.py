import copy
import tempfile
import unittest
from pathlib import Path

from models.watch_kinematic.watch_kinematic.bridge_partition_loop import _candidate_validation
from models.watch_kinematic.watch_kinematic.bridge_xy_partition import solve_bridge_xy_partition
from models.watch_kinematic.watch_kinematic.power_chain_mvp import CASE_RADIUS_MM, _build_separate_display_design
from models.watch_kinematic.watch_kinematic.separate_display_bridge_probe import (
    SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS,
    run_separate_display_bridge_partition_probe,
)
from models.watch_kinematic.watch_kinematic.separate_display_axis_voronoi_probe import (
    _axis_voronoi,
    _axis_voronoi_seam_plan,
    run_separate_display_axis_voronoi_probe,
    run_separate_display_axis_voronoi_seam_probe,
)
from models.watch_kinematic.watch_kinematic.separate_display_pattern import solve_separate_display_layout


class SeparateDisplayBridgePartitionProbeTests(unittest.TestCase):
    def test_axis_voronoi_probe_uses_each_axis_as_seed_and_groups_by_axis_system(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_separate_display_axis_voronoi_probe(
                base_seed=20260628,
                layout_count=5,
                output_dir=Path(tmp),
                grid_resolution=81,
            )

            expected_axis_count = sum(len(axis_ids) for axis_ids in SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS.values())
            self.assertEqual("watch_separate_display_axis_voronoi_probe", report["kind"])
            self.assertEqual("pass", report["status"])
            self.assertEqual(5, len(report["layouts"]))
            for layout in report["layouts"]:
                with self.subTest(seed=layout["seed"]):
                    self.assertEqual(expected_axis_count, layout["axis_seed_count"])
                    self.assertEqual(
                        sorted(SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS),
                        sorted(layout["axis_groups"]),
                    )
                    self.assertEqual("axis_seed_voronoi_group_coloring", layout["method"])

            for artifact_name in ["contact_sheet", "review_html", "report_json"]:
                artifact_path = Path(report["artifacts"][artifact_name])
                self.assertTrue(artifact_path.exists(), artifact_name)
                self.assertGreater(artifact_path.stat().st_size, 1000, artifact_name)

    def test_axis_voronoi_seam_probe_reconstructs_polyline_filleted_and_native_smooth_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_separate_display_axis_voronoi_seam_probe(
                base_seed=20260629,
                layout_count=5,
                output_dir=Path(tmp),
                grid_resolution=91,
            )

            self.assertEqual("watch_separate_display_axis_voronoi_seam_probe", report["kind"])
            self.assertEqual("pass", report["status"])
            self.assertEqual(5, len(report["layouts"]))
            for layout in report["layouts"]:
                with self.subTest(seed=layout["seed"]):
                    self.assertEqual("pass", layout["seam_status"])
                    self.assertEqual({"polyline", "filleted", "native_smooth"}, set(layout["variants"]))
                    self.assertEqual("native_smooth", layout["selected_variant"])
                    self.assertGreaterEqual(layout["seam_count"], 2)
                    self.assertGreaterEqual(layout["minimum_polyline_point_count"], 3)
                    self.assertGreater(layout["minimum_filleted_point_count"], layout["minimum_polyline_point_count"])
                    self.assertGreater(layout["minimum_native_smooth_point_count"], layout["minimum_polyline_point_count"])
                    self.assertEqual([], layout["hard_failures"])
                    for seam in layout["seams"]:
                        self.assertEqual("voronoi_boundary_path_fit", seam["fit_source"])
                        self.assertLessEqual(seam["checks"]["mean_boundary_fit_error_mm"], 0.85)
                        self.assertLessEqual(seam["checks"]["max_boundary_fit_error_mm"], 2.25)
                        self.assertLessEqual(seam["checks"]["native_smooth_mean_boundary_fit_error_mm"], 0.85)
                        self.assertLessEqual(seam["checks"]["max_filleted_turn_deg"], 62.0)
                        self.assertLessEqual(seam["checks"]["max_native_smooth_turn_deg"], 62.0)
                        self.assertGreater(
                            seam["checks"]["filleted_point_count"],
                            seam["checks"]["polyline_point_count"],
                        )
                        self.assertGreater(
                            seam["checks"]["native_smooth_point_count"],
                            seam["checks"]["polyline_point_count"],
                        )
                        self.assertGreaterEqual(seam["checks"]["raw_boundary_point_count"], 8)

            for artifact_name in [
                "contact_sheet",
                "filleted_contact_sheet",
                "native_smooth_contact_sheet",
                "review_html",
                "report_json",
            ]:
                artifact_path = Path(report["artifacts"][artifact_name])
                self.assertTrue(artifact_path.exists(), artifact_name)
                self.assertGreater(artifact_path.stat().st_size, 1000, artifact_name)

    def test_native_smooth_keeps_interior_voronoi_junction_endpoints_inside_case(self):
        seed = 6550
        design = _build_separate_display_design(seed, solve_separate_display_layout(seed=seed))
        seam_plan = _axis_voronoi_seam_plan(design, _axis_voronoi(design, 121))
        seam = next(
            seam
            for seam in seam_plan["seams"]
            if seam["seam_id"] == "barrel_bridge__escapement_bridge"
        )

        endpoint_radii = [
            (point[0] ** 2 + point[1] ** 2) ** 0.5
            for point in [seam["native_smooth"][0], seam["native_smooth"][-1]]
        ]

        self.assertLess(min(endpoint_radii), CASE_RADIUS_MM - 2.0)
        self.assertLessEqual(sum(radius > CASE_RADIUS_MM - 0.6 for radius in endpoint_radii), 1)

    def test_scheme_b_rejects_overlapping_functional_envelopes(self):
        seed = next(
            candidate_seed
            for candidate_seed in range(1, 500)
            if solve_separate_display_layout(seed=candidate_seed)["status"] == "pass"
        )
        design = _build_separate_display_design(seed, solve_separate_display_layout(seed=seed))
        partition = solve_bridge_xy_partition(
            design,
            grid_resolution=81,
            axis_groups=SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS,
        )
        partition["envelopes"]["escapement_bridge"] = copy.deepcopy(partition["envelopes"]["train_bridge"])

        scheme_b = _candidate_validation(partition, "service_island_power_partition", "B")

        self.assertEqual("fail", scheme_b["hard_status"])
        self.assertIn("functional_envelope_overlap", scheme_b["hard_failures"])

    def test_scheme_b_exposes_arc_bridge_footprints_not_full_partition_fields(self):
        seed = next(
            candidate_seed
            for candidate_seed in range(1, 500)
            if solve_separate_display_layout(seed=candidate_seed)["status"] == "pass"
        )
        design = _build_separate_display_design(seed, solve_separate_display_layout(seed=seed))
        partition = solve_bridge_xy_partition(
            design,
            grid_resolution=81,
            axis_groups=SEPARATE_DISPLAY_BRIDGE_AXIS_GROUPS,
        )
        candidate = partition["candidates"]["service_island_power_partition"]
        scheme_b = _candidate_validation(partition, "service_island_power_partition", "B")

        self.assertEqual("pass", scheme_b["bridge_footprint_status"])
        self.assertIn("bridge_plate_footprints", candidate)
        self.assertEqual(
            ["barrel_bridge", "escapement_bridge", "train_bridge"],
            sorted(footprint["bridge_id"] for footprint in candidate["bridge_plate_footprints"]),
        )
        for footprint in candidate["bridge_plate_footprints"]:
            with self.subTest(bridge_id=footprint["bridge_id"]):
                self.assertTrue(footprint["empty_mainplate_area_allowed"])
                self.assertEqual("case_concentric_arc", footprint["outer_edge_kind"])
                self.assertEqual("bounded_bridge_plate_footprint", footprint["footprint_kind"])
                self.assertGreaterEqual(len(footprint["points"]), 6)
                self.assertGreater(float(footprint["area_mm2"]), 0.0)
                self.assertLess(float(footprint["area_mm2"]), 0.45 * 3.14159 * CASE_RADIUS_MM * CASE_RADIUS_MM)
                for service_pad in footprint["service_pads"]:
                    self.assertEqual("outer_annular_service_pad", service_pad["footprint_type"])
                    self.assertEqual("case_concentric_arc", service_pad["outer_edge_kind"])
                    self.assertTrue(service_pad["empty_mainplate_area_allowed"])

    def test_probe_generates_five_random_layouts_with_scheme_a_and_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_separate_display_bridge_partition_probe(
                base_seed=20260628,
                layout_count=5,
                output_dir=Path(tmp),
                grid_resolution=81,
            )

            self.assertEqual("watch_separate_display_bridge_partition_probe", report["kind"])
            self.assertEqual("pass", report["status"])
            self.assertEqual("pass", report["layout_diversity_status"])
            self.assertGreaterEqual(
                report["layout_diversity"]["minimum_normalized_pairwise_distance"],
                report["layout_diversity"]["threshold"],
            )
            self.assertGreaterEqual(
                report["layout_diversity"]["axis_angle_spans_deg"]["train_stage_1_axis"],
                25.0,
            )
            self.assertGreaterEqual(
                report["layout_diversity"]["axis_angle_spans_deg"]["hour_display_axis"],
                25.0,
            )
            self.assertEqual(5, len(report["layouts"]))
            self.assertEqual(5, len(set(report["selected_seeds"])))
            self.assertEqual({"A": 5, "B": 5}, report["scheme_render_counts"])

            for layout in report["layouts"]:
                with self.subTest(seed=layout["seed"]):
                    self.assertEqual("pass", layout["solver_status"])
                    self.assertIn("A", layout["scheme_results"])
                    self.assertIn("B", layout["scheme_results"])
                    self.assertEqual("pass", layout["scheme_results"]["B"]["hard_status"])
                    self.assertEqual("pass", layout["scheme_results"]["B"]["functional_envelope_overlap"]["status"])
                    self.assertEqual("service_island_power_partition", layout["scheme_results"]["B"]["candidate_id"])
                    self.assertEqual(
                        ["barrel_bridge", "escapement_bridge", "train_bridge"],
                        sorted(layout["axis_groups"]),
                    )

            for artifact_name in [
                "axis_layout_contact_sheet",
                "scheme_a_contact_sheet",
                "scheme_b_contact_sheet",
                "ab_review_contact_sheet",
                "review_html",
                "report_json",
            ]:
                artifact_path = Path(report["artifacts"][artifact_name])
                self.assertTrue(artifact_path.exists(), artifact_name)
                self.assertGreater(artifact_path.stat().st_size, 1000, artifact_name)


if __name__ == "__main__":
    unittest.main()
