import json
from pathlib import Path
import tempfile
import unittest

from models.watch_kinematic.watch_kinematic.escapement_reference import (
    REQUIRED_ESCAPEMENT_ROLES,
    run_escapement_reference_semantics,
)


class WatchEscapementReferenceTests(unittest.TestCase):
    def test_builds_role_axes_envelope_and_motion_contracts_from_scaled_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_escapement_reference_semantics(Path(tmp), seed=123)

            self.assertEqual("pass", result["status"])
            for artifact_name in [
                "reference_semantic_json",
                "role_contract_json",
                "axes_json",
                "envelopes_json",
                "motion_constraints_json",
                "validation_json",
            ]:
                path = Path(result["artifacts"][artifact_name])
                self.assertTrue(path.exists(), f"{artifact_name} missing")
                self.assertGreater(path.stat().st_size, 0, f"{artifact_name} is empty")

            semantic = json.loads(Path(result["artifacts"]["reference_semantic_json"]).read_text(encoding="utf-8"))
            self.assertEqual("watch_swiss_lever_escapement_reference", semantic["pattern_card_id"])
            self.assertEqual("pass", semantic["status"])
            self.assertEqual(set(REQUIRED_ESCAPEMENT_ROLES), set(semantic["roles"]))
            self.assertEqual("axis_distance_and_direction_fit", semantic["reference_fit"]["method"])
            self.assertLessEqual(semantic["reference_fit"]["max_matched_axis_error_mm"], 0.01)
            self.assertEqual("reference_only", semantic["integration_status"])

            axes = json.loads(Path(result["artifacts"]["axes_json"]).read_text(encoding="utf-8"))
            axes_by_id = {axis["axis_id"]: axis for axis in axes["axes"]}
            self.assertEqual({"escape_axis", "pallet_axis", "balance_axis", "hairspring_axis"}, set(axes_by_id))
            self.assertEqual("escape_wheel_arbor", axes_by_id["escape_axis"]["role"])
            self.assertEqual("pallet_fork_pivot", axes_by_id["pallet_axis"]["role"])
            self.assertEqual("balance_staff", axes_by_id["balance_axis"]["role"])
            self.assertEqual("balance_axis", axes_by_id["hairspring_axis"]["coaxial_with"])
            self.assertLessEqual(axes["axis_checks"]["escape_axis_match_error_mm"], 0.01)
            self.assertLessEqual(axes["axis_checks"]["balance_axis_match_error_mm"], 0.01)

            envelopes = json.loads(Path(result["artifacts"]["envelopes_json"]).read_text(encoding="utf-8"))
            envelope_by_id = {envelope["envelope_id"]: envelope for envelope in envelopes["envelopes"]}
            self.assertEqual(
                {
                    "escape_wheel_tip_envelope",
                    "pallet_fork_sweep_envelope",
                    "balance_wheel_sweep_envelope",
                    "hairspring_placeholder_envelope",
                },
                set(envelope_by_id),
            )
            for envelope in envelope_by_id.values():
                self.assertEqual("pass", envelope["case_boundary_check"]["status"])
                self.assertGreater(envelope["radius_mm"], 0.0)
                self.assertLess(envelope["outer_distance_from_case_center_mm"], envelopes["case_inner_radius_mm"])

            motion = json.loads(Path(result["artifacts"]["motion_constraints_json"]).read_text(encoding="utf-8"))
            self.assertEqual("pass", motion["status"])
            links = {(link["source"], link["target"], link["interface_type"]) for link in motion["motion_links"]}
            self.assertIn(("escape_wheel", "pallet_fork", "locking_impulse_contact"), links)
            self.assertIn(("pallet_fork", "balance_wheel", "impulse_pin_contact"), links)
            self.assertIn(("hairspring", "balance_wheel", "restoring_torque_placeholder"), links)
            self.assertEqual("report_only_until_real_escape_geometry_replaces_placeholder", motion["timing_status"])

            roles = json.loads(Path(result["artifacts"]["role_contract_json"]).read_text(encoding="utf-8"))
            contracts = {contract["occurrence_id"]: contract for contract in roles["contracts"]}
            for role_id in REQUIRED_ESCAPEMENT_ROLES:
                with self.subTest(role_id=role_id):
                    self.assertIn(role_id, contracts)
                    self.assertEqual("pass", contracts[role_id]["validation"]["status"])
                    self.assertIn("geometry_constraint", contracts[role_id])
                    self.assertIn("motion_chain", contracts[role_id])
                    self.assertIn("mount_chain", contracts[role_id])
                    self.assertIn("constraint_chain", contracts[role_id])

            validation = json.loads(Path(result["artifacts"]["validation_json"]).read_text(encoding="utf-8"))
            self.assertEqual("pass", validation["status"])
            self.assertEqual([], validation["failed_checks"])


if __name__ == "__main__":
    unittest.main()
