from pathlib import Path
import tempfile
import unittest

from models.watch_kinematic.watch_kinematic.gate_a2_review import write_gate_a2_review


class GateA2ReviewTests(unittest.TestCase):
    def test_gate_a2_review_page_explains_literature_derived_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "gate_a2_review.html"

            written = write_gate_a2_review(output_path)

            self.assertEqual(output_path, written)
            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Gate A2", html)
            self.assertIn("文献驱动 Pattern Cards", html)
            self.assertIn("executable_engineering_pattern", html)
            self.assertIn("visual_style_pattern", html)
            self.assertIn("WK001_ciechanowski_mechanical_watch", html)
            self.assertIn("WK003_eta_technical_communication", html)
            self.assertIn("A1_formal_transmission_assembly_model", html)
            self.assertIn("A1_5_rule_space_sampler", html)
            self.assertIn("user_supplied_leap71_reference_images", html)
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


if __name__ == "__main__":
    unittest.main()
