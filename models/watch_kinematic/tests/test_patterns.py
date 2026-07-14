import json
import tempfile
from pathlib import Path
import unittest

from models.watch_kinematic.watch_kinematic.patterns import (
    build_watch_pattern_cards,
    write_watch_pattern_cards,
)


REQUIRED_PATTERN_IDS = {
    "watch_case_and_mainplate_frame",
    "visible_output_hand_axis",
    "compound_gear_train_between_axes",
    "pivot_supported_by_plate_and_bridge",
    "screw_fastened_bridge_to_mainplate",
    "spiral_visual_drive_or_regulator",
    "decorative_bezel_facets",
}

REQUIRED_FIELDS = {
    "id",
    "name",
    "pattern_class",
    "lifecycle_state",
    "solved_function",
    "required_interfaces",
    "generated_components",
    "generated_features",
    "parameter_variables",
    "hard_constraints",
    "soft_preferences",
    "validation_checks",
    "known_failure_modes",
    "repair_strategies",
    "evidence_sources",
    "formal_model_refs",
    "rule_space_refs",
    "promotion_notes",
}

EXPECTED_LIFECYCLE_STATES = {
    "watch_case_and_mainplate_frame": "executable_candidate",
    "visible_output_hand_axis": "executable_candidate",
    "compound_gear_train_between_axes": "executable_candidate",
    "pivot_supported_by_plate_and_bridge": "executable_candidate",
    "screw_fastened_bridge_to_mainplate": "executable_candidate",
    "spiral_visual_drive_or_regulator": "draft_pattern",
    "decorative_bezel_facets": "draft_pattern",
}

REQUIRED_EVIDENCE = {
    ("WK001_ciechanowski_mechanical_watch", "watchmaking_reference"),
    ("WK003_eta_technical_communication", "watchmaking_reference"),
    ("A1_formal_transmission_assembly_model", "formal_model"),
    ("A1_5_rule_space_sampler", "rule_space_validation"),
}

ENGINEERING_PATTERN_IDS = {
    "watch_case_and_mainplate_frame",
    "visible_output_hand_axis",
    "compound_gear_train_between_axes",
    "pivot_supported_by_plate_and_bridge",
    "screw_fastened_bridge_to_mainplate",
}

VISUAL_PATTERN_IDS = {
    "spiral_visual_drive_or_regulator",
    "decorative_bezel_facets",
}


class WatchPatternCardTests(unittest.TestCase):
    def test_central_hour_minute_pattern_has_dedicated_package_entrypoint(self):
        from models.watch_kinematic.watch_kinematic.pattern_cards.central_hour_minute_offcenter_seconds import (
            PATTERN_CARD_ID,
            build_current_pattern_card,
            solve_current_pattern_layout,
        )

        self.assertEqual("central_hour_minute_with_off_center_seconds_v1", PATTERN_CARD_ID)
        self.assertEqual(PATTERN_CARD_ID, build_current_pattern_card()["id"])
        self.assertEqual("pass", solve_current_pattern_layout(seed=731)["status"])

    def test_build_watch_pattern_cards_declares_required_ids_and_states(self):
        cards = build_watch_pattern_cards()

        cards_by_id = {card["id"]: card for card in cards}
        self.assertTrue(REQUIRED_PATTERN_IDS.issubset(cards_by_id))
        for pattern_id, lifecycle_state in EXPECTED_LIFECYCLE_STATES.items():
            with self.subTest(pattern_id=pattern_id):
                self.assertEqual(
                    lifecycle_state,
                    cards_by_id[pattern_id]["lifecycle_state"],
                )

    def test_every_pattern_card_has_required_schema_fields(self):
        cards = build_watch_pattern_cards()

        for card in cards:
            with self.subTest(pattern_id=card["id"]):
                self.assertTrue(REQUIRED_FIELDS.issubset(card))

    def test_pattern_cards_include_required_evidence_sources(self):
        cards = build_watch_pattern_cards()

        evidence = {
            (source["id"], source["type"])
            for card in cards
            for source in card["evidence_sources"]
        }
        self.assertTrue(REQUIRED_EVIDENCE.issubset(evidence))

    def test_engineering_patterns_are_not_screenshot_driven(self):
        cards_by_id = {card["id"]: card for card in build_watch_pattern_cards()}

        for pattern_id in ENGINEERING_PATTERN_IDS:
            with self.subTest(pattern_id=pattern_id):
                card = cards_by_id[pattern_id]
                self.assertEqual("executable_engineering_pattern", card["pattern_class"])
                evidence_ids = {source["id"] for source in card["evidence_sources"]}
                evidence_types = {source["type"] for source in card["evidence_sources"]}
                self.assertNotIn("user_supplied_leap71_reference_images", evidence_ids)
                self.assertIn("watchmaking_reference", evidence_types)
                self.assertIn("formal_model", evidence_types)
                self.assertIn("rule_space_validation", evidence_types)
                self.assertGreaterEqual(len(card["formal_model_refs"]), 2)
                self.assertGreaterEqual(len(card["rule_space_refs"]), 1)

    def test_visual_patterns_are_separated_from_engineering_rules(self):
        cards_by_id = {card["id"]: card for card in build_watch_pattern_cards()}

        for pattern_id in VISUAL_PATTERN_IDS:
            with self.subTest(pattern_id=pattern_id):
                card = cards_by_id[pattern_id]
                self.assertEqual("visual_style_pattern", card["pattern_class"])
                evidence_ids = {source["id"] for source in card["evidence_sources"]}
                self.assertIn("user_supplied_leap71_reference_images", evidence_ids)
                self.assertTrue(
                    all(
                        "not imply real" in constraint or "visual-only" in constraint
                        for constraint in card["hard_constraints"]
                    )
                )

    def test_write_watch_pattern_cards_creates_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            written_paths = write_watch_pattern_cards(output_dir)

            self.assertEqual(len(REQUIRED_PATTERN_IDS) * 2, len(written_paths))
            for pattern_id in REQUIRED_PATTERN_IDS:
                with self.subTest(pattern_id=pattern_id):
                    json_path = output_dir / f"{pattern_id}.json"
                    markdown_path = output_dir / f"{pattern_id}.md"
                    self.assertTrue(json_path.exists())
                    self.assertTrue(markdown_path.exists())
                    self.assertEqual(
                        pattern_id,
                        json.loads(json_path.read_text(encoding="utf-8"))["id"],
                    )

            markdown_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in output_dir.glob("*.md")
            )
            self.assertIn("Lifecycle State", markdown_text)
            self.assertIn("Validation Checks", markdown_text)
            self.assertIn("Formal Model References", markdown_text)
            self.assertIn("Rule-Space References", markdown_text)


if __name__ == "__main__":
    unittest.main()
