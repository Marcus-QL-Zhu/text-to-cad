import unittest

from models.watch_kinematic.watch_kinematic.current_pattern_solver import (
    BRIDGE_PERIMETER_RESERVED_BAND_MM,
    CURRENT_PATTERN_ID,
    DEFAULT_CASE_INNER_RADIUS_MM,
    REQUIRED_AXIS_IDS,
    solve_current_pattern,
)


class CurrentWatchPatternSolverTests(unittest.TestCase):
    def test_solves_current_pattern_with_formula_backed_candidate(self):
        report = solve_current_pattern(seed=731)

        self.assertEqual("pass", report["status"])
        self.assertEqual(CURRENT_PATTERN_ID, report["pattern_card_id"])
        self.assertGreaterEqual(report["candidate_count"], 8)
        self.assertEqual([], report["failed_reasons"])
        self.assertEqual("chain_solve_then_score_feasible_candidates", report["selection_strategy"])
        self.assertIn("center_distance = module * (driver_teeth + driven_teeth) / 2", report["geometry_equations"])
        self.assertIn(
            "bridge_plate_thickness = countersunk_head_depth + minimum_residual_material_below_countersink",
            report["geometry_equations"],
        )
        self.assertIn(
            "support_face_height : service_step_height = 2 : 1 below bridge bottom",
            report["geometry_equations"],
        )
        bridge_fastener = report["variables"]["fixed"]["bridge_z_stack_fastener_policy"]
        self.assertEqual("DIN 965 / ISO 7046 countersunk flat head screw", bridge_fastener["standard"])
        self.assertEqual("M1.4", bridge_fastener["thread_size"])
        self.assertAlmostEqual(0.90, bridge_fastener["countersunk_head_depth_mm"])
        self.assertAlmostEqual(0.30, bridge_fastener["minimum_residual_material_below_countersink_mm"])
        self.assertAlmostEqual(1.20, bridge_fastener["minimum_bridge_plate_thickness_mm"])
        self.assertEqual([2, 1], bridge_fastener["support_face_to_service_step_split"])

        selected = report["selected_candidate"]
        self.assertEqual("pass", selected["status"])
        self.assertEqual(set(REQUIRED_AXIS_IDS), {axis["axis_id"] for axis in selected["axes"]})
        self.assertGreater(selected["score"], 0.0)
        self.assertIn("module", selected["variables"])
        self.assertIn("barrel_angle_deg", selected["variables"])
        self.assertIn("third_angle_deg", selected["variables"])
        self.assertIn("fourth_angle_deg", selected["variables"])
        self.assertIn("escape_angle_deg", selected["variables"])
        self.assertIn("balance_angle_deg", selected["variables"])

        axes = {axis["axis_id"]: axis for axis in selected["axes"]}
        self.assertEqual((0.0, 0.0), (axes["display_center_axis"]["x"], axes["display_center_axis"]["y"]))
        self.assertEqual((0.0, 0.0), (axes["center_axis"]["x"], axes["center_axis"]["y"]))
        self.assertEqual("fourth_axis", selected["display_strategy"]["seconds_axis"])
        self.assertEqual("display_center_axis", selected["display_strategy"]["hour_axis"])
        self.assertEqual("display_center_axis", selected["display_strategy"]["minute_axis"])

        for proof in selected["center_distance_proofs"]:
            with self.subTest(mesh=(proof["driver"], proof["driven"])):
                self.assertEqual("pass", proof["status"])
                self.assertAlmostEqual(proof["actual_distance_mm"], proof["expected_distance_mm"], places=6)

        for envelope in selected["envelopes"]:
            with self.subTest(entity=envelope["entity_id"]):
                self.assertEqual("pass", envelope["case_boundary_check"]["status"])
                self.assertGreater(envelope["case_boundary_check"]["margin_mm"], 0.0)
                self.assertEqual("pass", envelope["bridge_perimeter_service_band_check"]["status"])
                self.assertGreaterEqual(
                    envelope["bridge_perimeter_service_band_check"]["margin_mm"],
                    BRIDGE_PERIMETER_RESERVED_BAND_MM,
                )
        self.assertEqual("pass", selected["bridge_perimeter_service_band_proofs"]["status"])
        self.assertGreaterEqual(
            selected["bridge_perimeter_service_band_proofs"]["minimum_margin_mm"],
            BRIDGE_PERIMETER_RESERVED_BAND_MM,
        )

        keepout_by_id = {proof["proof_id"]: proof for proof in selected["external_escapement_keepout_proofs"]}
        self.assertIn("balance_axis_vs_same_layer_fourth_wheel", keepout_by_id)
        balance_keepout = keepout_by_id["balance_axis_vs_same_layer_fourth_wheel"]
        self.assertEqual("pass", balance_keepout["status"])
        self.assertGreaterEqual(balance_keepout["clearance_mm"], balance_keepout["minimum_clearance_mm"])

        self.assertGreater(len(selected["shaft_to_foreign_gear_keepout_proofs"]), 0)
        shaft_keepout_by_id = {
            proof["proof_id"]: proof
            for proof in selected["shaft_to_foreign_gear_keepout_proofs"]
        }
        self.assertIn(
            "minute_work_axis_vs_center_wheel",
            shaft_keepout_by_id,
            "pattern-specific XY/Z solver must prove the minute-work arbor does not cross the rotating center wheel",
        )
        self.assertEqual("pass", shaft_keepout_by_id["minute_work_axis_vs_center_wheel"]["status"])
        self.assertTrue(
            all(proof["status"] == "pass" for proof in selected["shaft_to_foreign_gear_keepout_proofs"]),
            "all through-axis lines must clear non-owning gear envelopes",
        )
        self.assertIn("same_layer_gear_interference_proofs", selected)
        self.assertTrue(
            all(proof["status"] == "pass" for proof in selected["same_layer_gear_interference_proofs"]),
            "pattern-specific solver must reject same-Z non-meshing gear overlaps before CAD generation",
        )

        same_again = solve_current_pattern(seed=731)
        self.assertEqual(selected["candidate_id"], same_again["selected_candidate"]["candidate_id"])

    def test_fails_cleanly_when_case_boundary_has_no_feasible_candidate(self):
        report = solve_current_pattern(seed=123, case_inner_radius_mm=5.0)

        self.assertEqual("fail", report["status"])
        self.assertIsNone(report["selected_candidate"])
        self.assertEqual(0, report["feasible_candidate_count"])
        self.assertIn("case_boundary", report["failed_reasons"])
        self.assertGreater(report["candidate_count"], 0)
        self.assertTrue(any(candidate["status"] == "fail" for candidate in report["candidates"]))

    def test_fails_when_bridge_perimeter_service_band_cannot_be_reserved(self):
        report = solve_current_pattern(
            seed=731,
            bridge_perimeter_reserved_band_mm=DEFAULT_CASE_INNER_RADIUS_MM,
        )

        self.assertEqual("fail", report["status"])
        self.assertIsNone(report["selected_candidate"])
        self.assertEqual(0, report["feasible_candidate_count"])
        self.assertIn("bridge_perimeter_service_band", report["failed_reasons"])
        self.assertTrue(
            all(
                candidate["bridge_perimeter_service_band_proofs"]["status"] == "fail"
                for candidate in report["candidates"]
            )
        )

    def test_chain_solver_preserves_seed_diversity_after_feasibility_filtering(self):
        reports = [solve_current_pattern(seed=seed) for seed in [1, 2, 4, 5, 6]]

        self.assertTrue(all(report["status"] == "pass" for report in reports))
        self.assertTrue(
            all(report["selection_strategy"] == "chain_solve_then_score_feasible_candidates" for report in reports)
        )
        third_angles = {
            round(report["selected_candidate"]["variables"]["third_angle_deg"], 3)
            for report in reports
        }
        self.assertGreaterEqual(
            len(third_angles),
            3,
            "seeded chain solving should not collapse third-axis placement back to one hard-coded safe angle",
        )
        for report in reports:
            with self.subTest(seed=report["seed"]):
                self.assertIn("solver_stages", report)
                stages = report["solver_stages"]
                self.assertEqual(
                    [
                        "display_motion_axis",
                        "barrel_axis",
                        "third_axis",
                        "fourth_axis",
                        "escape_axis",
                        "balance_axis",
                    ],
                    [stage["stage_id"] for stage in stages],
                )
                self.assertTrue(all(stage["accepted_count"] > 0 for stage in stages))


if __name__ == "__main__":
    unittest.main()
