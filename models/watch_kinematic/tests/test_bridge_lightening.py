import unittest

from models.watch_kinematic.watch_kinematic.bridge_lightening import (
    LIGHTENING_MIN_WINDOW_AREA_MM2,
    solve_bridge_lightening_plan,
)
from models.watch_kinematic.watch_kinematic.power_chain_mvp import _build_design, _extrude_xy_points_preserve_frame


class BridgeLighteningTests(unittest.TestCase):
    def test_lightening_plan_preserves_bearing_connectivity_to_outer_band(self):
        design = _build_design(927, include_bridges=False)

        plan = solve_bridge_lightening_plan(design, layout_id="seed_927_lightening_test", grid_resolution=181)

        self.assertEqual("pass", plan["status"])
        for bridge in plan["bridges"]:
            with self.subTest(bridge=bridge["bridge_id"]):
                self.assertEqual("pass", bridge["status"])
                for bearing in bridge["bearing_connectivity"]:
                    self.assertEqual("pass", bearing["status"])
                    self.assertTrue(bearing["connected_to_boundary_band"])

    def test_lightening_plan_creates_real_windows_without_fragmenting_bridge_roles(self):
        design = _build_design(927, include_bridges=False)

        plan = solve_bridge_lightening_plan(design, layout_id="seed_927_lightening_test", grid_resolution=181)

        self.assertEqual(
            ["barrel_bridge", "train_bridge", "escapement_bridge"],
            [bridge["bridge_id"] for bridge in plan["bridges"]],
        )
        for bridge in plan["bridges"]:
            with self.subTest(bridge=bridge["bridge_id"]):
                self.assertGreaterEqual(bridge["window_components"]["large_component_count"], 1)
                self.assertGreaterEqual(
                    bridge["window_components"]["minimum_large_area_mm2"],
                    LIGHTENING_MIN_WINDOW_AREA_MM2,
                )
                self.assertEqual(
                    "solver_and_validation_scratchpad_not_final_cad_boundary",
                    plan["policy"]["grid_role"],
                )

    def test_manufacturing_window_points_extrude_even_when_json_style_lists(self):
        design = _build_design(927, include_bridges=False)
        plan = solve_bridge_lightening_plan(design, layout_id="seed_927_lightening_test", grid_resolution=181)

        window = plan["bridges"][0]["manufacturing_windows"][0]
        self.assertIsInstance(window["points"][0], list)

        cutter = _extrude_xy_points_preserve_frame(window["points"], 1.0)

        self.assertGreater(float(cutter.volume), 1.0)


if __name__ == "__main__":
    unittest.main()
