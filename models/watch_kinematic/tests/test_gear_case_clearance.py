import unittest

from models.watch_kinematic.watch_kinematic.pattern_cards.gear_case_clearance import (
    GEAR_CASE_INNER_WALL_SAFETY_MM,
    prove_gear_case_inner_wall_clearance,
)


class GearCaseClearanceTests(unittest.TestCase):
    def test_rejects_gear_tip_with_less_than_0_8mm_case_clearance(self):
        proof = prove_gear_case_inner_wall_clearance(
            [{"gear_id": "near_wall_gear", "axis_id": "near_wall_axis", "outer_radius": 3.0}],
            {"near_wall_axis": {"x": 16.21, "y": 0.0}},
            case_inner_radius_mm=20.0,
        )

        self.assertEqual(GEAR_CASE_INNER_WALL_SAFETY_MM, proof["required_safety_margin_mm"])
        self.assertEqual(0.79, proof["minimum_margin_mm"])
        self.assertEqual("fail", proof["status"])
        self.assertEqual(["near_wall_gear"], [record["gear_id"] for record in proof["violations"]])


if __name__ == "__main__":
    unittest.main()
