import json
import math
from pathlib import Path
import tempfile
import unittest

from models.watch_kinematic.watch_kinematic.gear_visual_reference import (
    _make_open_spoked_wheel,
    _reference_gear,
    _spoke_width_mm,
    run_spoked_gear_reference,
)
from models.watch_kinematic.watch_kinematic.power_chain_mvp import _z_cylinder
from build123d import Location


class GearVisualReferenceTests(unittest.TestCase):
    def test_spoked_gear_reference_generates_two_to_five_spoke_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_spoked_gear_reference(Path(tmp), seed=731)

            self.assertEqual("pass", result["status"])
            step_path = Path(result["artifacts"]["step"])
            contract_path = Path(result["artifacts"]["visual_contract_json"])
            self.assertTrue(step_path.exists())
            self.assertGreater(step_path.stat().st_size, 0)
            step_text = step_path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("_hub", step_text)
            self.assertNotIn("_spoke_", step_text)
            self.assertNotIn("_tooth_rim", step_text)

            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            variants = contract["variants"]
            self.assertEqual([2, 3, 4, 5], [variant["spoke_count"] for variant in variants])

            for variant in variants:
                with self.subTest(spoke_count=variant["spoke_count"]):
                    self.assertEqual("open_spoked_watch_wheel", variant["role_contract"]["visual_role"])
                    self.assertIn("tooth_rim", variant["features"])
                    self.assertIn("hub", variant["features"])
                    self.assertIn("open_cutouts", variant["features"])
                    self.assertEqual(
                        variant["spoke_count"],
                        len([feature for feature in variant["features"] if feature.startswith("spoke_")]),
                    )
                    self.assertGreater(variant["rim_inner_radius_mm"], variant["hub_outer_radius_mm"])
                    self.assertGreater(variant["spoke_outer_overlap_mm"], 0.0)
                    self.assertGreaterEqual(
                        variant["rim_inner_radius_mm"] / variant["root_radius_mm"],
                        0.84,
                        "watch wheel should have a large open window near the tooth-root rim",
                    )
                    self.assertLessEqual(
                        variant["hub_outer_radius_mm"] / variant["root_radius_mm"],
                        0.19,
                        "watch wheel hub should be visually compact, not a large solid web",
                    )
                    self.assertGreater(variant["spoke_width_at_hub_mm"], variant["spoke_width_at_mid_mm"])
                    self.assertGreater(variant["spoke_width_at_rim_mm"], variant["spoke_width_at_mid_mm"])

    def test_open_spoked_wheel_has_clear_air_between_hub_and_rim(self):
        gear = _reference_gear(3, seed=731)
        wheel = _make_open_spoked_wheel(gear, label="test_three_spoke_open_wheel")
        self.assertEqual(
            0,
            len(wheel.children),
            "wheel must be one cutout gear body, not a STEP assembly of hub/spokes/rim subparts",
        )
        open_sector_angle = math.radians(gear["phase_deg"] + 60.0)
        probe_radius_from_center = (gear["hub_outer_radius"] + gear["rim_inner_radius"]) / 2.0
        probe = _z_cylinder(0.08, gear["height"] + 0.2).located(
            Location(
                (
                    math.cos(open_sector_angle) * probe_radius_from_center,
                    math.sin(open_sector_angle) * probe_radius_from_center,
                    gear["height"] / 2.0,
                )
            )
        )

        overlap = wheel & probe

        self.assertLess(
            overlap.volume,
            1e-5,
            "open sector between adjacent spokes must be a through-window, not a retained solid web",
        )

    def test_spoke_width_is_broader_at_hub_and_rim_than_midspan(self):
        gear = _reference_gear(3, seed=731)
        hub_width = _spoke_width_mm(gear, 0.0)
        mid_width = _spoke_width_mm(gear, 0.5)
        rim_width = _spoke_width_mm(gear, 1.0)

        self.assertGreater(hub_width, mid_width)
        self.assertGreater(rim_width, mid_width)
        self.assertGreaterEqual(hub_width / mid_width, 1.6)
