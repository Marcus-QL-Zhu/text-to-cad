from pathlib import Path
import tempfile
import unittest

from models.watch_kinematic.watch_kinematic.gate_a_review import write_gate_a_review


class GateAReviewTests(unittest.TestCase):
    def test_gate_a_review_page_is_human_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "gate_a_review.html"

            written = write_gate_a_review(output_path)

            self.assertEqual(output_path, written)
            html = output_path.read_text(encoding="utf-8")
            for case_id in [
                "leap_style_balanced",
                "leap_style_low_dense",
                "leap_style_vertical_offset",
            ]:
                self.assertIn(case_id, html)
            for pattern_id in [
                "watch_case_and_mainplate_frame",
                "visible_output_hand_axis",
                "compound_gear_train_between_axes",
                "pivot_supported_by_plate_and_bridge",
                "screw_fastened_bridge_to_mainplate",
                "spiral_visual_drive_or_regulator",
                "decorative_bezel_facets",
            ]:
                self.assertIn(pattern_id, html)
            self.assertIn("reference_images/leap_style_balanced.png", html)
            self.assertIn("reference_images/leap_style_low_dense.png", html)
            self.assertIn("reference_images/leap_style_vertical_offset.png", html)
            self.assertIn("不是真实机械表机芯", html)
            self.assertIn("real_escapement", html)
            self.assertIn("draft_pattern", html)


if __name__ == "__main__":
    unittest.main()
