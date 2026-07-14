import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from models.watch_kinematic.watch_kinematic.separate_display_pattern import (
    build_separate_display_pattern_card,
    render_separate_display_pattern_markdown,
    solve_separate_display_layout,
    write_separate_display_review,
    write_separate_display_pattern_card,
)


class SeparateDisplayPatternTests(unittest.TestCase):
    def test_separate_display_pattern_card_declares_no_center_axis_requirement(self):
        card = build_separate_display_pattern_card()

        self.assertEqual("separate_hour_minute_no_seconds_v1", card["id"])
        self.assertIn("minute_display_axis", card["required_roles"])
        self.assertIn("hour_display_axis", card["required_roles"])
        self.assertIn("seconds_hand", card["forbidden_roles"])
        self.assertIn("display_center_axis", card["forbidden_required_axes"])
        self.assertIn("center_axis", card["forbidden_required_axes"])
        self.assertIn("movement_geometric_center", card["construction_references"])

    def test_separate_display_pattern_card_has_dedicated_package_entrypoint(self):
        from models.watch_kinematic.watch_kinematic.pattern_cards.separate_hour_minute_no_seconds import (
            PATTERN_CARD_ID as package_pattern_card_id,
            build_separate_display_pattern_card as package_build_card,
            solve_separate_display_layout as package_solve_layout,
        )

        self.assertEqual("separate_hour_minute_no_seconds_v1", package_pattern_card_id)
        self.assertEqual(package_pattern_card_id, package_build_card()["id"])
        self.assertEqual("pass", package_solve_layout(seed=731)["status"])

    def test_separate_display_pattern_card_requires_ratio_and_negative_cases(self):
        card = build_separate_display_pattern_card()
        checks = set(card["validation_checks"])

        self.assertIn("separate_minute_and_hour_axes", checks)
        self.assertIn("hour_to_minute_ratio_1_to_12", checks)
        self.assertIn("all_gear_tip_envelopes_inside_case", checks)
        self.assertIn("minute_motion_chain_closed", checks)
        self.assertIn("hour_motion_chain_closed", checks)
        self.assertIn("no_seconds_hand", checks)
        self.assertIn("collapse_minute_hour_axes_must_fail", card["negative_cases"])
        self.assertIn(
            "for every gear: axis_center_distance + gear_tip_radius + 0.80 mm <= case_inner_radius",
            card["hard_constraints"],
        )
        self.assertIn("remove_hour_display_relay_must_fail", card["negative_cases"])

    def test_render_separate_display_pattern_markdown_names_contract_sections(self):
        card = build_separate_display_pattern_card()

        markdown = render_separate_display_pattern_markdown(card)

        self.assertIn("# Separate Hour And Minute Display Without Seconds", markdown)
        self.assertIn("## Required Roles", markdown)
        self.assertIn("- `minute_display_axis`", markdown)
        self.assertIn("## Forbidden Required Axes", markdown)
        self.assertIn("- `display_center_axis`", markdown)

    def test_write_separate_display_pattern_card_writes_json_and_markdown(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            written_paths = write_separate_display_pattern_card(output_dir)

            self.assertEqual(
                [
                    output_dir / "separate_hour_minute_no_seconds_v1.json",
                    output_dir / "separate_hour_minute_no_seconds_v1.md",
                ],
                written_paths,
            )
            self.assertTrue(written_paths[0].exists())
            self.assertTrue(written_paths[1].exists())
            self.assertIn(
                '"id": "separate_hour_minute_no_seconds_v1"',
                written_paths[0].read_text(encoding="utf-8"),
            )
            self.assertIn(
                "# Separate Hour And Minute Display Without Seconds",
                written_paths[1].read_text(encoding="utf-8"),
            )

    def test_separate_display_solver_outputs_free_axes(self):
        report = solve_separate_display_layout(seed=731)

        self.assertEqual("pass", report["status"])
        self.assertIn("movement_geometric_center", report["construction_references"])
        self.assertEqual("separate_hour_minute_no_seconds_v1", report["pattern_card_id"])

        candidate = report["selected_candidate"]
        axes = {axis["axis_id"]: axis for axis in candidate["axes"]}

        self.assertIn("minute_display_axis", axes)
        self.assertIn("hour_display_axis", axes)
        self.assertIn("display_relay_axis", axes)
        self.assertNotIn("display_center_axis", axes)
        self.assertNotIn("center_axis", axes)
        self.assertNotIn("seconds_axis", axes)
        self.assertNotEqual(
            (axes["minute_display_axis"]["x"], axes["minute_display_axis"]["y"]),
            (axes["hour_display_axis"]["x"], axes["hour_display_axis"]["y"]),
        )

    def test_separate_display_solver_proves_ratio_and_no_seconds(self):
        report = solve_separate_display_layout(seed=731)
        candidate = report["selected_candidate"]
        checks = candidate["checks"]

        self.assertEqual("pass", checks["no_seconds_hand"])
        self.assertEqual("pass", checks["separate_minute_and_hour_axes"])
        self.assertEqual("pass", checks["hour_to_minute_ratio_1_to_12"])
        self.assertEqual("pass", checks["display_relay_meshes_valid"])
        self.assertAlmostEqual(1 / 12, candidate["display_ratio_proof"]["hour_to_minute_ratio"])
        self.assertEqual([], candidate["forbidden_generated_roles"])

    def test_separate_display_solver_reports_geometry_proofs(self):
        report = solve_separate_display_layout(seed=731)
        candidate = report["selected_candidate"]

        self.assertEqual("pass", candidate["geometry_proofs"]["case_boundary_margin"]["status"])
        self.assertEqual("pass", candidate["geometry_proofs"]["display_axis_separation"]["status"])
        self.assertEqual("pass", candidate["geometry_proofs"]["same_layer_non_mesh_clearance"]["status"])
        self.assertEqual("pass", candidate["geometry_proofs"]["foreign_axis_to_gear_keepout"]["status"])
        self.assertEqual("pass", candidate["sweep_envelopes"]["minute_hand"]["status"])
        self.assertEqual("pass", candidate["sweep_envelopes"]["hour_hand"]["status"])

    def test_separate_display_solver_keeps_every_gear_tip_0_8mm_inside_case_wall(self):
        candidate = solve_separate_display_layout(seed=731)["selected_candidate"]
        proof = candidate["geometry_proofs"]["gear_case_inner_wall_clearance"]

        self.assertEqual(0.8, proof["required_safety_margin_mm"])
        self.assertEqual("pass", proof["status"])
        self.assertEqual("pass", candidate["checks"]["all_gear_tip_envelopes_inside_case"])
        self.assertTrue(proof["records"])
        self.assertTrue(
            all(record["margin_to_case_inner_wall_mm"] >= proof["required_safety_margin_mm"] for record in proof["records"])
        )

    def test_separate_display_solver_rejects_train_escape_layouts_without_bridge_seam_corridor(self):
        report = solve_separate_display_layout(seed=8459)
        candidate = report["selected_candidate"]

        self.assertEqual("pass", report["status"])
        proof = candidate["geometry_proofs"]["train_escapement_bridge_seam_corridor"]

        self.assertEqual("pass", proof["status"])
        self.assertGreaterEqual(proof["available_corridor_mm"], proof["required_corridor_mm"])
        self.assertEqual("train_stage_3_wheel", proof["train_gear_id"])
        self.assertEqual("escape_axis", proof["escapement_axis_id"])

    def test_separate_display_solver_keeps_barrel_and_first_train_axes_separate(self):
        report = solve_separate_display_layout(seed=731)
        axes = {axis["axis_id"]: axis for axis in report["selected_candidate"]["axes"]}

        separation = math.dist(
            (axes["barrel_axis"]["x"], axes["barrel_axis"]["y"]),
            (axes["train_stage_1_axis"]["x"], axes["train_stage_1_axis"]["y"]),
        )

        self.assertGreaterEqual(separation, 2.0)

    def test_write_separate_display_review_writes_gate1_html(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            review_path = write_separate_display_review(output_dir, seed=731)

            self.assertEqual(output_dir / "separate_display_2d_review.html", review_path)
            html = review_path.read_text(encoding="utf-8")
            self.assertIn("Separate Hour/Minute No-Seconds 2D Review", html)
            self.assertIn("minute_display_axis", html)
            self.assertIn("hour_display_axis", html)
            self.assertIn("movement_geometric_center", html)
            self.assertIn("No seconds hand", html)

    def test_write_separate_display_review_offsets_overlapping_axis_labels(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            review_path = write_separate_display_review(output_dir, seed=731)

            html = review_path.read_text(encoding="utf-8")
            self.assertNotIn(
                '<text x="189.24" y="297.04" class="small">barrel_axis</text>'
                '<circle cx="183.24" cy="303.04" r="4" class="axis" />'
                '<text x="189.24" y="297.04" class="small">train_stage_1_axis</text>',
                html,
            )


if __name__ == "__main__":
    unittest.main()
