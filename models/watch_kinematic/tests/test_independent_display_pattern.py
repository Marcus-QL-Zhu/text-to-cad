import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from models.watch_kinematic.watch_kinematic.independent_display_pattern import (
    build_independent_display_pattern_card,
    render_independent_display_pattern_markdown,
    solve_independent_display_layout,
    write_independent_display_pattern_card,
    write_independent_display_review,
)


class IndependentDisplayPatternTests(unittest.TestCase):
    def test_independent_display_pattern_card_declares_parallel_display_branches(self):
        card = build_independent_display_pattern_card()

        self.assertEqual("independent_hour_minute_no_seconds_v1", card["id"])
        self.assertIn("minute_display_branch", card["required_roles"])
        self.assertIn("hour_display_branch", card["required_roles"])
        self.assertIn("no_seconds_hand", card["hard_constraints"])
        self.assertIn("hour_branch_does_not_depend_on_minute_branch", card["validation_checks"])
        self.assertIn("all_gear_tip_envelopes_inside_case", card["validation_checks"])
        self.assertIn(
            "for every gear: axis_center_distance + gear_tip_radius + 0.80 mm <= case_inner_radius",
            card["hard_constraints"],
        )
        self.assertIn("hour_from_minute_serial_chain_must_fail", card["negative_cases"])

    def test_render_independent_display_pattern_markdown_names_parallel_contract(self):
        card = build_independent_display_pattern_card()

        markdown = render_independent_display_pattern_markdown(card)

        self.assertIn("# Independent Hour And Minute Display Without Seconds", markdown)
        self.assertIn("- `minute_display_branch`", markdown)
        self.assertIn("- `hour_display_branch`", markdown)
        self.assertIn("hour_branch_does_not_depend_on_minute_branch", markdown)

    def test_write_independent_display_pattern_card_writes_json_and_markdown(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            written_paths = write_independent_display_pattern_card(output_dir)

            self.assertEqual(
                [
                    output_dir / "independent_hour_minute_no_seconds_v1.json",
                    output_dir / "independent_hour_minute_no_seconds_v1.md",
                ],
                written_paths,
            )
            self.assertTrue(written_paths[0].exists())
            self.assertTrue(written_paths[1].exists())

    def test_independent_display_solver_outputs_independent_branches(self):
        report = solve_independent_display_layout(seed=731)

        self.assertEqual("pass", report["status"])
        self.assertEqual("independent_hour_minute_no_seconds_v1", report["pattern_card_id"])

        candidate = report["selected_candidate"]
        axes = {axis["axis_id"]: axis for axis in candidate["axes"]}
        self.assertIn("minute_input_relay_axis", axes)
        self.assertIn("minute_display_axis", axes)
        self.assertIn("hour_input_relay_axis", axes)
        self.assertIn("hour_reduction_relay_axis", axes)
        self.assertIn("hour_display_axis", axes)
        self.assertNotEqual(
            (axes["minute_display_axis"]["x"], axes["minute_display_axis"]["y"]),
            (axes["hour_display_axis"]["x"], axes["hour_display_axis"]["y"]),
        )

        minute_branch = candidate["power_branches"]["minute_display_branch"]
        hour_branch = candidate["power_branches"]["hour_display_branch"]
        self.assertEqual("train_stage_3_wheel", minute_branch["source"])
        self.assertEqual("train_stage_3_wheel", hour_branch["source"])
        self.assertEqual("minute_display_member", minute_branch["output"])
        self.assertEqual("hour_display_member", hour_branch["output"])
        self.assertNotIn("minute_display_member", hour_branch["nodes"])
        self.assertEqual("pass", candidate["checks"]["hour_branch_does_not_depend_on_minute_branch"])

    def test_independent_display_solver_proves_parallel_ratios(self):
        report = solve_independent_display_layout(seed=731)
        candidate = report["selected_candidate"]

        self.assertEqual("pass", candidate["checks"]["train_to_minute_ratio_1_to_1"])
        self.assertEqual("pass", candidate["checks"]["train_to_hour_ratio_1_to_12"])
        self.assertEqual("pass", candidate["checks"]["hour_to_minute_ratio_1_to_12"])
        self.assertAlmostEqual(1.0, candidate["display_ratio_proof"]["train_to_minute_display_ratio"])
        self.assertAlmostEqual(1 / 12, candidate["display_ratio_proof"]["train_to_hour_display_ratio"])
        self.assertAlmostEqual(1 / 12, candidate["display_ratio_proof"]["hour_to_minute_ratio"])

        serial_meshes = [
            mesh
            for mesh in candidate["display_meshes"]
            if mesh["driver"] == "minute_display_member" or mesh["driven"] == "minute_display_member" and mesh["branch_id"] == "hour_display_branch"
        ]
        self.assertEqual([], serial_meshes)

    def test_independent_display_solver_reports_geometry_proofs(self):
        report = solve_independent_display_layout(seed=731)
        candidate = report["selected_candidate"]

        self.assertEqual("pass", candidate["geometry_proofs"]["case_boundary_margin"]["status"])
        self.assertEqual("pass", candidate["geometry_proofs"]["display_axis_separation"]["status"])
        self.assertEqual("pass", candidate["geometry_proofs"]["same_layer_non_mesh_clearance"]["status"])
        self.assertEqual("pass", candidate["geometry_proofs"]["foreign_axis_to_gear_keepout"]["status"])

    def test_independent_display_solver_keeps_every_gear_tip_0_8mm_inside_case_wall(self):
        candidate = solve_independent_display_layout(seed=731)["selected_candidate"]
        proof = candidate["geometry_proofs"]["gear_case_inner_wall_clearance"]

        self.assertEqual(0.8, proof["required_safety_margin_mm"])
        self.assertEqual("pass", proof["status"])
        self.assertEqual("pass", candidate["checks"]["all_gear_tip_envelopes_inside_case"])
        self.assertTrue(
            all(record["margin_to_case_inner_wall_mm"] >= proof["required_safety_margin_mm"] for record in proof["records"])
        )

    def test_write_independent_display_review_writes_gate1_html(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            review_path = write_independent_display_review(output_dir, seed=731)

            self.assertEqual(output_dir / "independent_display_2d_review.html", review_path)
            html = review_path.read_text(encoding="utf-8")
            self.assertIn("Independent Hour/Minute No-Seconds 2D Review", html)
            self.assertIn("minute_display_branch", html)
            self.assertIn("hour_display_branch", html)
            self.assertIn("hour branch independent from minute branch", html)


if __name__ == "__main__":
    unittest.main()
