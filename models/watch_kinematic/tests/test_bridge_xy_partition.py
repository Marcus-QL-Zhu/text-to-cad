import tempfile
import unittest
from pathlib import Path

from models.watch_kinematic.watch_kinematic.bridge_xy_partition import (
    BRIDGE_AXIS_GROUPS,
    AXIS_PROTECTION_RADIUS_MULTIPLIER,
    render_bridge_xy_partition,
    solve_bridge_xy_partition,
)
from models.watch_kinematic.watch_kinematic.power_chain_mvp import _build_design


class BridgeXyPartitionTests(unittest.TestCase):
    def test_partition_builds_axis_protection_envelopes_and_seam_paths(self):
        design = _build_design(864, include_bridges=True)

        partition = solve_bridge_xy_partition(design, grid_resolution=181)

        self.assertEqual("pass", partition["status"])
        self.assertEqual("linked_axis_capsule_envelope_when_links_exist_else_convex_hull", partition["envelope_method"])
        self.assertEqual(set(BRIDGE_AXIS_GROUPS), set(partition["envelopes"]))
        self.assertEqual(
            {"continuous_outer_arc_y", "service_island_power_partition"},
            {"continuous_outer_arc_y", "service_island_power_partition"} & set(partition["candidates"]),
        )
        self.assertEqual(
            "pad_span_equals_full_service_island_span",
            partition["support_island_rules"]["single_screw_island_pad_policy"],
        )
        continuous = partition["candidates"]["continuous_outer_arc_y"]
        service_island = partition["candidates"]["service_island_power_partition"]
        self.assertEqual("review", continuous["status"])
        self.assertEqual("review", service_island["status"])
        self.assertIn(continuous["coverage_status"], {"pass", "needs_optimization"})
        self.assertIn(service_island["coverage_status"], {"pass", "needs_optimization"})
        self.assertEqual("weighted_voronoi_partition_with_envelope_priority_and_service_islands", service_island["topology"])
        self.assertEqual("weighted_voronoi_with_envelope_priority", service_island["line_policy"]["kind"])
        self.assertEqual(2, len(service_island["manufacturing_boundaries"]))
        self.assertEqual(3, len(continuous["seams"]))
        self.assertGreater(abs(continuous["junction"][0]) + abs(continuous["junction"][1]), 1.0)

        axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
        for axis_id, circle in partition["protection_circles"].items():
            upper = axis_by_id[axis_id].get("upper_jewel_bearing")
            if upper:
                self.assertAlmostEqual(
                    float(upper["outer_radius"]) * AXIS_PROTECTION_RADIUS_MULTIPLIER,
                    circle["radius_mm"],
                    places=4,
                )
            else:
                self.assertGreater(circle["radius_mm"], 0.0)

        for bridge_id, envelope in partition["envelopes"].items():
            with self.subTest(bridge=bridge_id):
                self.assertGreaterEqual(len(envelope["points"]), 3)

        for seam in continuous["seams"]:
            with self.subTest(seam=seam["seam_id"]):
                self.assertGreaterEqual(len(seam["path"]), 2)
                self.assertGreater(seam["width_mm"], 0.0)
        for candidate in partition["candidates"].values():
            with self.subTest(candidate=candidate["candidate_id"]):
                self.assertIn("service_island_policy", candidate)
                self.assertIn("regions", candidate)
                for region in candidate["regions"]:
                    self.assertIn("outer_service_islands", region)

    def test_partition_render_writes_review_png(self):
        design = _build_design(864, include_bridges=True)
        partition = solve_bridge_xy_partition(design, grid_resolution=121)
        with tempfile.TemporaryDirectory() as tmp:
            png = render_bridge_xy_partition(partition, Path(tmp) / "partition.png")
            self.assertTrue(png.exists())
            self.assertGreater(png.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
