from pathlib import Path
import unittest

from models.watch_kinematic.watch_kinematic.cases import load_watch_case


CASE_DIR = Path(__file__).resolve().parents[1] / "cases"


class WatchKinematicCaseTests(unittest.TestCase):
    def test_balanced_case_declares_drive_and_three_outputs(self):
        case = load_watch_case(CASE_DIR / "case_leap_style_balanced.json")

        self.assertEqual(case["case_id"], "leap_style_balanced")
        self.assertEqual(case["mechanism_type"], "watch_style_kinematic_demo")
        self.assertEqual(case["drive_axis"]["id"], "drive_spiral_right")
        self.assertEqual(len(case["output_axes"]), 3)
        self.assertIn("real_escapement", case["excluded_systems"])
        self.assertIn("keyless_works", case["excluded_systems"])

    def test_all_reference_cases_have_local_frame_and_acceptance(self):
        case_names = [
            "case_leap_style_balanced.json",
            "case_leap_style_low_dense.json",
            "case_leap_style_vertical_offset.json",
        ]

        for case_name in case_names:
            with self.subTest(case_name=case_name):
                case = load_watch_case(CASE_DIR / case_name)

                self.assertEqual(case["local_frame"]["plane"], "movement_xy")
                self.assertEqual(case["local_frame"]["axis"], "movement_z")
                self.assertIn(
                    "animated_motion_sidecar_exists",
                    case["acceptance_criteria"],
                )
                self.assertIn(
                    "every_visible_axis_has_support_semantics",
                    case["acceptance_criteria"],
                )
                self.assertEqual(case["style"]["visual_family"], "leap71_watch_style")
                self.assertIn("visible_gear_train", case["style"]["motifs"])


if __name__ == "__main__":
    unittest.main()
