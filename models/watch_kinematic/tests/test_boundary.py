from pathlib import Path
import unittest

from models.watch_kinematic.watch_kinematic.boundary import build_boundary_package
from models.watch_kinematic.watch_kinematic.cases import load_watch_case


CASE_DIR = Path(__file__).resolve().parents[1] / "cases"


class WatchKinematicBoundaryTests(unittest.TestCase):
    def test_boundary_declares_watch_domain_functions_and_scope(self):
        case = load_watch_case(CASE_DIR / "case_leap_style_balanced.json")

        boundary = build_boundary_package(case)

        self.assertEqual(boundary["domain"], "watch_kinematic")
        self.assertIn("transmit_rotation", boundary["required_functions"])
        self.assertIn("display_motion", boundary["required_functions"])
        self.assertIn("support_rotating_axes", boundary["required_functions"])
        self.assertIn("decorate_watch_case", boundary["required_functions"])
        self.assertIn("real_escapement", boundary["not_in_v1_scope"])
        self.assertIn(
            "all_motion_axes_have_local_frames",
            boundary["acceptance_criteria"],
        )

    def test_boundary_includes_master_plan_structures(self):
        case = load_watch_case(CASE_DIR / "case_leap_style_balanced.json")

        boundary = build_boundary_package(case)

        expected_structures = [
            "task_statement",
            "object_and_environment_list",
            "function_flow_graph",
            "interface_graph",
            "hard_constraints",
            "soft_preferences",
            "operating_modes",
            "acceptance_criteria",
            "open_questions",
            "not_in_v1_scope",
        ]
        for key in expected_structures:
            with self.subTest(key=key):
                self.assertIn(key, boundary)

    def test_boundary_preserves_case_design_inputs(self):
        case = load_watch_case(CASE_DIR / "case_leap_style_balanced.json")

        boundary = build_boundary_package(case)

        self.assertEqual(boundary["case_id"], case["case_id"])
        self.assertEqual(boundary["drive_axis"], case["drive_axis"])
        self.assertEqual(boundary["output_axes"], case["output_axes"])
        self.assertEqual(boundary["local_frame"], case["local_frame"])
        self.assertEqual(boundary["not_in_v1_scope"], case["excluded_systems"])
        self.assertEqual(boundary["style_motifs"], case["style"]["motifs"])
        for criterion in case["acceptance_criteria"]:
            with self.subTest(criterion=criterion):
                self.assertIn(criterion, boundary["acceptance_criteria"])
        self.assertIn(
            "all_motion_axes_have_local_frames",
            boundary["acceptance_criteria"],
        )

    def test_boundary_defines_required_hard_constraints(self):
        case = load_watch_case(CASE_DIR / "case_leap_style_balanced.json")

        boundary = build_boundary_package(case)

        expected_constraints = [
            "input_drive_axis_exists",
            "gear_train_connects_drive_to_each_output_axis",
            "each_visible_axis_has_support_path",
            "mesh_pairs_have_center_distance_match",
            "no_unexplained_overlapping_gears",
            "animation_sidecar_covers_all_moving_groups",
        ]
        for constraint in expected_constraints:
            with self.subTest(constraint=constraint):
                self.assertIn(constraint, boundary["hard_constraints"])

    def test_domain_note_declares_sections_and_promotion_boundary(self):
        path = Path("docs/domain_semantics/domain_watch_kinematic.md")
        text = path.read_text(encoding="utf-8")

        expected_sections = [
            "# Scope",
            "# V1 Object Types",
            "# V1 Relations",
            "# V1 Motion Concepts",
            "# V1 Exclusions",
            "# Promotion Rules",
            "# Validation Mapping",
        ]
        for section in expected_sections:
            with self.subTest(section=section):
                self.assertIn(section, text)
        self.assertIn("cannot be promoted to `mech_core`", text)
        self.assertIn("non-watch domain reuses the same term", text)
        self.assertIn("deterministic validation", text)


if __name__ == "__main__":
    unittest.main()
