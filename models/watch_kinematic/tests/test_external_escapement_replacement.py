import json
from pathlib import Path
import re
import tempfile
import unittest

from models.watch_kinematic.watch_kinematic.external_escapement_replacement import (
    build_external_escapement_bridge_stage,
    build_external_escapement_replacement,
)
from models.watch_kinematic.watch_kinematic.power_chain_mvp import run_power_chain_mvp


class ExternalEscapementReplacementTests(unittest.TestCase):
    def test_replacement_step_removes_self_made_escapement_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            run_power_chain_mvp(output_dir, seed=731)

            result = build_external_escapement_replacement(output_dir, seed=731)

            step_text = Path(result["artifacts"]["step"]).read_text(encoding="utf-8", errors="ignore")
            for forbidden in [
                "pallet_placeholder_disc",
                "balance_placeholder_disc",
                "escapement_to_balance_placeholder_envelope",
            ]:
                self.assertNotIn(forbidden, step_text)
            self.assertIsNone(re.search(r"PRODUCT\('escape_wheel'", step_text))
            self.assertIn("external_escape_wheel", step_text)
            self.assertIn("external_pallet_fork", step_text)
            self.assertIn("external_balance_wheel", step_text)
            self.assertIn("external_hairspring", step_text)
            self.assertIn("external_escape_staff", step_text)
            self.assertNotIn("external_balance_staff", step_text)
            self.assertNotIn("external_balance_upper_cap", step_text)
            self.assertNotIn("external_balance_upper_fixed_hardware", step_text)
            self.assertIn("external_balance_replacement_staff", step_text)
            self.assertIn("external_balance_upper_jewel_bearing", step_text)
            self.assertIn("external_escape_upper_cap", step_text)
            self.assertIn("external_escapement_reference_plate", step_text)

    def test_replacement_report_maps_every_external_solid_to_a_retained_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            run_power_chain_mvp(output_dir, seed=731)

            result = build_external_escapement_replacement(output_dir, seed=731)

            report = json.loads(Path(result["artifacts"]["role_map_json"]).read_text(encoding="utf-8"))
            self.assertEqual("pass", report["status"])
            by_role = {entry["role"]: entry for entry in report["included_source_solids"]}
            self.assertTrue({"escape_wheel", "pallet_fork", "balance_wheel", "hairspring"}.issubset(set(by_role)))
            self.assertEqual(0, by_role["escape_wheel"]["source_solid_index"])
            self.assertEqual(1, by_role["pallet_fork"]["source_solid_index"])
            self.assertEqual(2, by_role["balance_wheel"]["source_solid_index"])
            self.assertEqual(3, by_role["hairspring"]["source_solid_index"])
            self.assertEqual([11, 14, 18], report["excluded_source_solid_indices"])
            self.assertEqual(32, len(report["included_source_solids"]))
            self.assertIn("external_escape_staff", {entry["occurrence_id"] for entry in report["included_source_solids"]})
            self.assertNotIn("external_balance_staff", {entry["occurrence_id"] for entry in report["included_source_solids"]})
            self.assertIn("external_balance_replacement_staff", {entry["occurrence_id"] for entry in report["generated_replacement_solids"]})
            self.assertIn("external_balance_upper_jewel_bearing", {entry["occurrence_id"] for entry in report["generated_replacement_solids"]})
            self.assertIn("external_escapement_reference_plate", {entry["occurrence_id"] for entry in report["included_source_solids"]})

            validation = json.loads(Path(result["artifacts"]["validation_json"]).read_text(encoding="utf-8"))
            self.assertEqual("pass", validation["status"])
            for check in [
                "self_made_escapement_placeholders_removed",
                "generated_escape_wheel_removed",
                "external_role_solids_present",
                "external_escape_staff_and_upper_hardware_present",
                "external_balance_source_staff_hardware_removed",
                "generated_balance_staff_and_upper_bearing_present",
                "external_source_solids_retained_except_replaced_balance_hardware",
                "external_reference_plate_retained",
                "external_reference_plate_lower_face_mated_to_mainplate",
                "same_layer_fourth_wheel_external_balance_clearance",
            ]:
                self.assertEqual("pass", validation["checks"][check])

    def test_external_reference_plate_lower_face_mates_to_mainplate_top(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            run_power_chain_mvp(output_dir, seed=731)

            result = build_external_escapement_replacement(output_dir, seed=731)

            report = json.loads(Path(result["artifacts"]["role_map_json"]).read_text(encoding="utf-8"))
            validation = json.loads(Path(result["artifacts"]["validation_json"]).read_text(encoding="utf-8"))
            fit = report["fit"]
            self.assertEqual(
                "reference_plate_lower_face_flush_to_mainplate_top",
                fit["target_z_origin_policy"],
            )
            self.assertIn("plate_to_mainplate_mate", fit)
            mate = fit["plate_to_mainplate_mate"]
            self.assertEqual("external_escapement_reference_plate", mate["occurrence_id"])
            self.assertAlmostEqual(0.0, mate["z_gap_mm"], places=4)
            self.assertLessEqual(abs(mate["z_gap_mm"]), mate["tolerance_mm"])

            plate_entry = next(
                entry
                for entry in report["included_source_solids"]
                if entry["occurrence_id"] == "external_escapement_reference_plate"
            )
            self.assertAlmostEqual(
                mate["mainplate_top_z_mm"],
                plate_entry["transformed_bounds_mm"]["min"][2],
                places=4,
            )
            self.assertEqual("pass", validation["checks"]["external_reference_plate_lower_face_mated_to_mainplate"])
            self.assertEqual(
                "under_reference_plate_imported_geometry_may_overlap_mainplate",
                validation["allowed_interference_exceptions"][0]["exception_id"],
            )

    def test_replacement_writes_step_module_motion_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            run_power_chain_mvp(output_dir, seed=731)

            result = build_external_escapement_replacement(output_dir, seed=731)

            sidecar = Path(result["artifacts"]["step_module_js"])
            motion = json.loads(Path(result["artifacts"]["motion_json"]).read_text(encoding="utf-8"))
            self.assertTrue(sidecar.exists())
            self.assertGreater(sidecar.stat().st_size, 0)
            self.assertEqual("pass", motion["status"])
            self.assertEqual("external_swiss_lever_static_pallet_and_balance", motion["escapement_animation_policy"])
            self.assertEqual(
                {"seconds_hand": 720.0, "minute_hand": 12.0, "hour_hand": 1.0},
                motion["physical_hand_angular_velocity_ratio_to_hour_hand"],
            )
            self.assertEqual(
                {"seconds_unit": 3600.0, "minute_unit": 60.0, "hour_unit": 1.0},
                motion["requested_time_unit_ratio"],
            )
            moving_features = {
                feature_id
                for group in motion["moving_groups"]
                for feature_id in group["feature_ids"]
            }
            groups = {group["group_id"]: group for group in motion["moving_groups"]}
            self.assertEqual("clockwise", motion["direction_contract"]["required_display_hand_direction_viewed_from_dial_side"])
            self.assertEqual("pass", motion["checks"]["display_hands_clockwise_viewed_from_dial_side"])
            self.assertLess(groups["hour_display_rotation"]["angular_velocity_ratio_to_hour_hand"], 0)
            self.assertLess(groups["minute_display_rotation"]["angular_velocity_ratio_to_hour_hand"], 0)
            self.assertLess(groups["fourth_train_and_seconds_rotation"]["angular_velocity_ratio_to_hour_hand"], 0)
            self.assertGreater(groups["external_escape_wheel_rotation"]["angular_velocity_ratio_to_hour_hand"], 0)
            self.assertIn("external_escape_wheel", moving_features)
            self.assertIn("escape_pinion", moving_features)
            self.assertIn("seconds_hand", moving_features)
            self.assertIn("minute_hand", moving_features)
            self.assertIn("hour_hand", moving_features)
            self.assertNotIn("external_pallet_fork", moving_features)
            self.assertNotIn("external_balance_wheel", moving_features)
            self.assertIn("external_pallet_fork", motion["fixed_features"])
            self.assertIn("external_balance_wheel", motion["fixed_features"])

            sidecar_text = sidecar.read_text(encoding="utf-8")
            self.assertIn("watch_train_motion", sidecar_text)
            self.assertIn("watch_direction_review", sidecar_text)
            self.assertIn("external_escape_wheel", sidecar_text)
            self.assertIn("escape_pinion", sidecar_text)
            self.assertIn("physicalHandRatio", sidecar_text)

    def test_bridge_stage_external_replacement_writes_three_bridge_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            result = build_external_escapement_bridge_stage(output_dir, seed=864)

            self.assertEqual("pass", result["status"])
            step_path = Path(result["artifacts"]["step"])
            self.assertTrue(step_path.exists())
            self.assertEqual("watch_power_chain_with_bridges_and_scaled_swiss_lever_reference.step", step_path.name)
            step_text = step_path.read_text(encoding="utf-8", errors="ignore")
            for label in ["barrel_bridge", "train_bridge", "escapement_bridge"]:
                self.assertIn(label, step_text)

            validation = json.loads(Path(result["artifacts"]["validation_json"]).read_text(encoding="utf-8"))
            self.assertEqual("pass", validation["checks"]["bridge_stage_three_bridge_plates_present"])


if __name__ == "__main__":
    unittest.main()

