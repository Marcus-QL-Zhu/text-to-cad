import copy
import json
from pathlib import Path
import tempfile
import unittest

from models.watch_kinematic.watch_kinematic.power_chain_mvp import (
    BRIDGE_PERIMETER_RESERVED_BAND_MM,
    DISPLAY_CENTER_AXIS,
    GEAR_MESH_PHASE_TOLERANCE_DEG,
    MAINPLATE_RADIUS_MM,
    _axis_by_id,
    _build_design,
    _build_gear_mesh_clearance_report,
    _build_independent_geometry_report,
    _build_separate_display_design,
    _build_separate_display_motion_report,
    _gear_body,
    _gear_tooth_body_with_bore,
    _make_gear,
    _make_hand,
    _build_step_module_motion_report,
    _render_step_module_js,
    _review_material_for_label,
    _step_module_feature_refs,
    _separate_display_step_module_features,
    _separate_display_task4_checks,
    REVIEW_MATERIALS,
    _should_use_watch_wheel_spoke_cutouts,
    named_random,
    run_power_chain_mvp,
)
from models.watch_kinematic.watch_kinematic.separate_display_pattern import solve_separate_display_layout


class WatchPowerChainMvpTests(unittest.TestCase):
    def test_named_random_is_reproducible_and_independent(self):
        self.assertEqual(named_random(123, "module"), named_random(123, "module"))
        self.assertNotEqual(named_random(123, "module"), named_random(124, "module"))
        self.assertNotEqual(named_random(123, "module"), named_random(123, "train_axis_angle"))

    def test_review_materials_follow_part_roles(self):
        self.assertEqual(REVIEW_MATERIALS["jewel"], _review_material_for_label("lower_jewel_center_axis"))
        self.assertEqual(REVIEW_MATERIALS["brass"], _review_material_for_label("third_wheel"))
        self.assertEqual(REVIEW_MATERIALS["brass"], _review_material_for_label("external_escape_wheel"))
        self.assertEqual(REVIEW_MATERIALS["cyan_hand"], _review_material_for_label("minute_hand_blade"))
        self.assertEqual(REVIEW_MATERIALS["cyan_hand"], _review_material_for_label("hour_hand_blade"))
        self.assertEqual(REVIEW_MATERIALS["cyan_hand"], _review_material_for_label("seconds_hand_blade"))
        self.assertEqual(REVIEW_MATERIALS["silver"], _review_material_for_label("minute_hand_hub"))
        self.assertEqual(REVIEW_MATERIALS["silver"], _review_material_for_label("hour_hand_hub"))
        self.assertEqual(REVIEW_MATERIALS["silver"], _review_material_for_label("seconds_hand_hub"))
        self.assertEqual(REVIEW_MATERIALS["silver"], _review_material_for_label("seconds_hand_collet_cap"))
        self.assertEqual(REVIEW_MATERIALS["silver"], _review_material_for_label("fourth_arbor"))
        self.assertEqual(REVIEW_MATERIALS["silver"], _review_material_for_label("cannon_pinion_tube"))
        self.assertEqual(REVIEW_MATERIALS["chrome"], _review_material_for_label("foundation_mainplate"))
        self.assertEqual(REVIEW_MATERIALS["jewel"], _review_material_for_label("external_balance_upper_cap"))
        self.assertEqual(REVIEW_MATERIALS["jewel"], _review_material_for_label("external_balance_upper_fixed_hardware"))
        self.assertEqual(0.80, _review_material_for_label("barrel_bridge")["rgba"][3])
        self.assertEqual(0.80, _review_material_for_label("train_bridge")["rgba"][3])
        self.assertEqual(0.80, _review_material_for_label("escapement_bridge")["rgba"][3])
        self.assertEqual(REVIEW_MATERIALS["neutral"], _review_material_for_label("barrel_bridge_service_1_screw_1"))

    def test_step_module_js_applies_review_material_styles(self):
        design = _build_design(1289, include_bridges=True)
        motion = _build_step_module_motion_report(design, external_escapement=True)
        step_js = _render_step_module_js(motion)

        self.assertEqual(REVIEW_MATERIALS["brass"]["hex"], motion["visual_materials"]["center_wheel"]["hex"])
        self.assertEqual(REVIEW_MATERIALS["silver"]["hex"], motion["visual_materials"]["minute_hand"]["hex"])
        self.assertEqual(REVIEW_MATERIALS["chrome"]["hex"], motion["visual_materials"]["foundation_mainplate"]["hex"])
        self.assertEqual(0.80, motion["visual_materials"]["barrel_bridge"]["rgba"][3])
        self.assertEqual(0.80, motion["visual_materials"]["train_bridge"]["rgba"][3])
        self.assertEqual(0.80, motion["visual_materials"]["escapement_bridge"]["rgba"][3])
        self.assertEqual(REVIEW_MATERIALS["jewel"]["hex"], motion["visual_materials"]["external_balance_upper_cap"]["hex"])
        self.assertEqual(
            REVIEW_MATERIALS["jewel"]["hex"],
            motion["visual_materials"]["external_balance_upper_fixed_hardware"]["hex"],
        )
        self.assertEqual(
            "#o1.2.34.1",
            motion["features"]["external_balance_upper_jewel_leaf"]["ref"],
        )
        self.assertEqual(
            REVIEW_MATERIALS["jewel"]["hex"],
            motion["visual_materials"]["external_balance_upper_jewel_leaf"]["hex"],
        )
        leaf_contract = motion["semantic_material_contracts"]["external_balance_upper_jewel_leaf"]
        self.assertEqual("external_balance_upper_jewel_bearing", leaf_contract["semantic_owner"])
        self.assertEqual("jewel_bearing", leaf_contract["role"])
        self.assertEqual("#o1.2.34.1", leaf_contract["visible_ref"])
        self.assertEqual("ruby_jewel", leaf_contract["material"]["material_id"])
        self.assertEqual("pass", motion["checks"]["semantic_material_contracts_cover_visible_features"])
        self.assertIn("function applyReviewMaterials", step_js)
        self.assertIn("const rawFeature = WATCH_POWER_CHAIN_MOTION.features?.[featureId]", step_js)
        self.assertIn("effects.style(safeMotionTarget(features, featureId, rawFeature)", step_js)
        self.assertIn("rawFeature?.ref", step_js)
        self.assertIn("opacity: material.rgba?.[3] ?? 1.0", step_js)
        self.assertNotIn("applyReviewMaterials(effects, features);", step_js)
        self.assertIn(REVIEW_MATERIALS["brass"]["hex"], step_js)
        self.assertIn(REVIEW_MATERIALS["silver"]["hex"], step_js)
        self.assertIn(REVIEW_MATERIALS["jewel"]["hex"], step_js)
        self.assertIn(REVIEW_MATERIALS["chrome"]["hex"], step_js)

    def test_flat_step_motion_aliases_expand_to_visible_leaf_parts(self):
        design = _build_design(927, include_bridges=False)
        visible_leaf_ids = [
            "barrel_drum",
            "barrel_outer_teeth",
            "center_pinion_tooth_profile",
            "center_pinion_hub",
            "center_wheel",
            "third_pinion_tooth_profile",
            "third_pinion_hub",
            "third_wheel",
            "fourth_pinion_tooth_profile",
            "fourth_pinion_hub",
            "fourth_wheel",
            "fourth_arbor",
            "seconds_arbor_extension",
            "seconds_hand_collet_cap",
            "seconds_hand_hub",
            "seconds_hand_blade",
            "escape_pinion_tooth_profile",
            "escape_pinion_hub",
            "cannon_pinion_display_driver",
            "cannon_pinion_hub",
            "cannon_pinion_tube",
            "minute_hand_hub",
            "minute_hand_blade",
            "minute_wheel",
            "minute_pinion",
            "hour_wheel",
            "hour_tube",
            "hour_hand_hub",
            "hour_hand_blade",
            "external_escape_wheel",
            "external_escape_staff",
            "external_pallet_fork",
            "external_balance_wheel",
            "external_hairspring",
            "external_escapement_reference_plate",
            "external_escape_upper_cap",
            "external_escape_upper_fixed_hardware",
            "external_balance_replacement_staff",
            "external_balance_upper_jewel_bearing",
        ]
        feature_refs = {
            feature_id: {"ref": f"#o1.{index}", "origin": None, "axis": [0, 0, 1]}
            for index, feature_id in enumerate(visible_leaf_ids, start=1)
        }

        motion = _build_step_module_motion_report(
            design,
            external_escapement=True,
            feature_refs_override=feature_refs,
        )

        self.assertEqual("pass", motion["checks"]["all_moving_features_have_refs"])
        self.assertEqual([], motion["missing_features"])
        groups = {group["group_id"]: group["feature_ids"] for group in motion["moving_groups"]}
        self.assertEqual(["barrel_drum", "barrel_outer_teeth"], groups["barrel_rotation"])
        self.assertEqual(["minute_wheel", "minute_pinion"], groups["minute_work_compound_rotation"])
        self.assertEqual(["minute_hand_hub", "minute_hand_blade"], groups["minute_display_rotation"][-2:])
        self.assertEqual(["hour_hand_hub", "hour_hand_blade"], groups["hour_display_rotation"][-2:])
        self.assertEqual(["seconds_hand_hub", "seconds_hand_blade"], groups["fourth_train_and_seconds_rotation"][-2:])

    def test_generates_power_chain_mvp_without_bridges(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_power_chain_mvp(Path(tmp), seed=731)

            self.assertEqual("pass", result["status"])
            self.assertEqual("power_chain_mvp_no_bridges", result["phase"])
            self.assertEqual(731, result["seed"])

            for artifact_name in [
                "step",
                "semantic_json",
                "kinematic_json",
                "validation_json",
                "role_contract_json",
                "solver_json",
                "dashboard_html",
            ]:
                path = Path(result["artifacts"][artifact_name])
                self.assertTrue(path.exists(), f"{artifact_name} missing")
                self.assertGreater(path.stat().st_size, 0, f"{artifact_name} is empty")

            step_text = Path(result["artifacts"]["step"]).read_text(encoding="utf-8", errors="ignore")
            required_step_labels = [
                "foundation_mainplate",
                "mainspring_barrel",
                "mainspring_placeholder",
                "barrel_arbor",
                "center_wheel",
                "center_pinion",
                "third_wheel",
                "third_pinion",
                "fourth_wheel",
                "fourth_pinion",
                "escape_wheel",
                "escape_pinion",
                "pallet_placeholder_disc",
                "balance_placeholder_disc",
                "seconds_hand",
                "minute_hand",
                "hour_hand",
                "cannon_pinion_display_driver",
                "minute_wheel_assembly",
                "minute_wheel",
                "minute_pinion",
            ]
            for label in required_step_labels:
                with self.subTest(label=label):
                    self.assertIn(label, step_text)

            forbidden_step_labels = [
                "case_frame",
                "barrel_bridge",
                "train_bridge",
                "escapement_bridge",
                "bridge_screw",
            ]
            for label in forbidden_step_labels:
                with self.subTest(forbidden_label=label):
                    self.assertNotIn(label, step_text)

            semantic = json.loads(Path(result["artifacts"]["semantic_json"]).read_text(encoding="utf-8"))
            solver = json.loads(Path(result["artifacts"]["solver_json"]).read_text(encoding="utf-8"))
            self.assertEqual("power_chain_mvp_no_bridges", semantic["phase"])
            self.assertFalse(semantic["bridges_generated"])
            self.assertEqual("pass", solver["status"])
            self.assertEqual(solver["selected_candidate"]["candidate_id"], semantic["pattern_solver"]["selected_candidate_id"])
            self.assertGreaterEqual(solver["candidate_count"], 8)
            self.assertTrue(semantic["checks"]["power_chain_connected_to_escape_wheel"])
            self.assertTrue(semantic["checks"]["coaxial_compound_gears_complete"])
            self.assertTrue(semantic["checks"]["gear_mesh_phase_alignment"])
            self.assertTrue(semantic["checks"]["placeholder_escapement_to_balance_envelopes_exist"])
            self.assertTrue(semantic["checks"]["display_hands_exist"])
            self.assertTrue(semantic["checks"]["display_hand_stack_clear"])
            self.assertTrue(semantic["checks"]["three_hand_drive_chains_declared"])
            self.assertTrue(semantic["checks"]["central_hour_minute_axis"])
            self.assertTrue(semantic["checks"]["seconds_hand_length_within_case_clearance"])
            self.assertTrue(semantic["checks"]["seconds_hand_sweep_clear"])
            self.assertTrue(semantic["checks"]["display_hand_mount_stacks_closed"])
            self.assertTrue(semantic["checks"]["display_hand_mount_stacks_xy_connected"])
            self.assertTrue(semantic["checks"]["display_hand_mount_stacks_6dof_constrained"])
            self.assertTrue(semantic["checks"]["display_motion_chain_realized"])
            self.assertTrue(semantic["checks"]["hour_motion_reduction_proven"])
            self.assertTrue(semantic["checks"]["coaxial_display_sleeve_clearance"])
            self.assertTrue(semantic["checks"]["support_axis_geometry_valid"])
            self.assertTrue(semantic["checks"]["internal_work_envelope_clear"])
            self.assertTrue(semantic["checks"]["internal_interference_clear"])
            self.assertTrue(semantic["checks"]["gear_mesh_tip_root_clearance"])
            self.assertTrue(semantic["checks"]["mainplate_flat_round_disk"])
            self.assertTrue(semantic["checks"]["mainplate_outer_raised_support_ring"])
            self.assertTrue(semantic["checks"]["lower_jewel_supports_complete"])
            self.assertTrue(semantic["checks"]["future_upper_jewel_plane_ready"])
            self.assertTrue(semantic["checks"]["jewel_supports_interference_clear"])
            self.assertTrue(semantic["checks"]["bridge_perimeter_service_band_reserved"])
            self.assertTrue(semantic["checks"]["seed_reproducibility_manifest_exists"])

            display = semantic["display"]
            self.assertEqual("separate_display_axis_and_off_center_seconds", display["strategy"])
            self.assertGreaterEqual(display["z_clearance_above_train_mm"], 0.8)
            axes_by_id = {axis["axis_id"]: axis for axis in semantic["layout"]["axes"]}
            self.assertEqual("display_center_axis", display["display_center_axis"])
            self.assertAlmostEqual(0.0, axes_by_id["display_center_axis"]["x"])
            self.assertAlmostEqual(0.0, axes_by_id["display_center_axis"]["y"])
            hands = display["hands"]
            self.assertEqual(["hour_hand", "minute_hand", "seconds_hand"], [hand["hand_id"] for hand in hands])
            self.assertEqual(["display_center_axis", "display_center_axis", "fourth_axis"], [hand["axis_id"] for hand in hands])
            self.assertNotEqual(axes_by_id["display_center_axis"]["x"], axes_by_id["fourth_axis"]["x"])
            self.assertEqual(["fixed_central_hour_hand", "fixed_central_minute_hand", "computed_sub_seconds_hand"], [hand["model_source"] for hand in hands])
            self.assertLess(hands[0]["length_mm"], hands[1]["length_mm"])
            for lower, upper in zip(hands, hands[1:]):
                self.assertGreaterEqual(upper["z_mm"] - lower["z_mm"], 0.18)
            self.assertEqual(["hour_tube", "cannon_pinion_tube"], [tube["tube_id"] for tube in display["tube_stack"]])
            self.assertEqual(["central_display_arbor_extension", "seconds_arbor_extension"], [extension["extension_id"] for extension in display["arbor_extensions"]])
            drive_chains = {chain["hand_id"]: chain for chain in display["drive_chains"]}
            self.assertEqual("center_wheel_to_cannon_pinion", drive_chains["minute_hand"]["source"])
            self.assertEqual("minute_motion_work_reduction", drive_chains["hour_hand"]["source"])
            self.assertEqual("fourth_wheel_direct_sub_seconds", drive_chains["seconds_hand"]["source"])
            self.assertEqual(
                [
                    "cannon_pinion_assembly",
                    "cannon_pinion_display_driver",
                    "minute_wheel_assembly",
                    "minute_pinion",
                    "hour_wheel",
                    "hour_hand",
                ],
                drive_chains["hour_hand"]["path"],
            )
            self.assertEqual("gear_mesh_compound_gear_mesh", drive_chains["hour_hand"]["interface_sequence"])
            self.assertAlmostEqual(1 / 12, drive_chains["hour_hand"]["ratio_proof"]["computed_ratio"])
            motion_works = display["motion_works"]
            self.assertEqual("pass", motion_works["status"])
            self.assertEqual(["cannon_pinion_display_driver", "minute_wheel", "minute_pinion", "hour_wheel"], motion_works["nodes"])
            self.assertAlmostEqual(1 / 12, motion_works["ratio_proof"]["hour_to_minute_ratio"])
            self.assertAlmostEqual(1 / 12, motion_works["ratio_proof"]["expected_hour_to_minute_ratio"])
            self.assertIn(" then ", motion_works["ratio_proof"]["tooth_relation"])

            kinematic = json.loads(Path(result["artifacts"]["kinematic_json"]).read_text(encoding="utf-8"))
            self.assertEqual(
                {"seconds_hand": 720.0, "minute_hand": 12.0, "hour_hand": 1.0},
                kinematic["physical_hand_angular_velocity_ratio_to_hour_hand"],
            )
            self.assertEqual(
                {"seconds_unit": 3600.0, "minute_unit": 60.0, "hour_unit": 1.0},
                kinematic["requested_time_unit_ratio"],
            )
            self.assertEqual("pass", kinematic["checks"]["physical_hand_ratio_720_12_1"])
            self.assertEqual("pass", kinematic["checks"]["requested_time_unit_ratio_3600_60_1"])
            self.assertEqual("clockwise", kinematic["direction_contract"]["required_display_hand_direction_viewed_from_dial_side"])
            self.assertEqual(-1.0, kinematic["direction_contract"]["clockwise_sign_in_step_module"])
            self.assertEqual("external_escape_wheel", kinematic["motion_source_contract"]["source_entity"])
            self.assertEqual("pass", kinematic["checks"]["display_hands_clockwise_viewed_from_dial_side"])
            self.assertEqual("external_mesh", kinematic["direction_propagation_rules"][0]["interface_type"])
            self.assertEqual(-1.0, kinematic["direction_propagation_rules"][0]["direction_multiplier"])

            arbor_specs = semantic["layout"]["arbor_geometry_policy"]
            self.assertEqual("role_based_arbor_body_and_pivot_radii", arbor_specs["kind"])
            self.assertGreater(arbor_specs["axis_specs"]["barrel_axis"]["body_radius_mm"], arbor_specs["axis_specs"]["escape_axis"]["body_radius_mm"])
            self.assertGreater(arbor_specs["axis_specs"]["center_axis"]["body_radius_mm"], 0.16)
            self.assertLessEqual(arbor_specs["axis_specs"]["escape_axis"]["pivot_radius_mm"], 0.12)
            for gear in [*semantic["layout"]["gears"], *semantic["layout"]["display_gears"]]:
                if gear["gear_id"] == "barrel_outer_teeth":
                    continue
                with self.subTest(gear_bore=gear["gear_id"]):
                    self.assertIn("bore_radius", gear)
                    self.assertIn("axis_body_radius", gear)
                    self.assertGreaterEqual(
                        gear["bore_radius"] + 1e-9,
                        gear["axis_body_radius"] + arbor_specs["minimum_bore_clearance_mm"],
                    )
            sleeve_clearance = display["coaxial_sleeve_clearance"]
            self.assertEqual("pass", sleeve_clearance["status"])
            self.assertGreater(sleeve_clearance["radial_clearance_mm"], 0.03)
            seconds_hand = hands[2]
            seconds_envelope = display["sweep_envelopes"]["seconds_hand"]
            self.assertEqual("fourth_axis", seconds_envelope["axis_id"])
            self.assertAlmostEqual(seconds_hand["length_mm"], seconds_envelope["radius_mm"])
            self.assertLess(seconds_hand["length_mm"], seconds_envelope["case_min_clearance_mm"])
            self.assertEqual([], seconds_envelope["interference_failures"])
            self.assertGreater(seconds_envelope["case_safety_margin_mm"], 0.25)
            mount_stacks = {stack["hand_id"]: stack for stack in display["mount_stacks"]}
            self.assertEqual({"hour_hand", "minute_hand", "seconds_hand"}, set(mount_stacks))
            self.assertEqual(["hour_wheel", "hour_tube", "hour_hand_hub"], [segment["component_id"] for segment in mount_stacks["hour_hand"]["segments"]])
            self.assertEqual(["cannon_pinion_assembly", "cannon_pinion_tube", "minute_hand_hub"], [segment["component_id"] for segment in mount_stacks["minute_hand"]["segments"]])
            self.assertEqual(["fourth_arbor", "seconds_arbor_extension", "seconds_hand_hub"], [segment["component_id"] for segment in mount_stacks["seconds_hand"]["segments"]])
            for stack in mount_stacks.values():
                self.assertTrue(stack["closed"])
                self.assertTrue(stack["xy_connected"])
                self.assertTrue(stack["six_dof_constrained"])
                self.assertEqual([], stack["gap_failures"])
                self.assertEqual([], stack["xy_failures"])
                self.assertEqual([], stack["six_dof_failures"])
                self.assertLessEqual(stack["max_positive_gap_mm"], 0.02)
                self.assertLessEqual(stack["max_xy_center_error_mm"], 0.01)
                self.assertLessEqual(stack["unresolved_dof_count"], 0)
                for segment in stack["segments"]:
                    self.assertIn("x_mm", segment)
                    self.assertIn("y_mm", segment)
                    self.assertIn("outer_radius_mm", segment)
                    self.assertIn("inner_radius_mm", segment)
                for interface in stack["interfaces"]:
                    self.assertLessEqual(interface["xy_center_error_mm"], 0.01)
                    self.assertGreater(interface["radial_overlap_mm"], 0.0)
                    self.assertIn("lock_tx", interface["constraints"])

                    self.assertIn("lock_ty", interface["constraints"])
                    self.assertIn("lock_tz", interface["constraints"])
            self.assertEqual(
                ["lock_tx", "lock_ty", "lock_tz", "lock_rx", "lock_ry", "lock_rz"],
                mount_stacks["seconds_hand"]["six_dof_constraints"],
            )

            mesh_phase_records = semantic["layout"]["mesh_phase_records"]
            self.assertEqual(semantic["layout"]["meshes"], [{key: record[key] for key in ("driver", "driven", "kind")} for record in mesh_phase_records])
            for record in mesh_phase_records:
                with self.subTest(mesh=(record["driver"], record["driven"])):
                    self.assertEqual("external_tooth_to_gap_on_center_line", record["strategy"])
                    self.assertLessEqual(abs(record["driver_tooth_error_deg"]), 1e-6)
                    self.assertLessEqual(abs(record["driven_gap_error_deg"]), 1e-6)

            validation = json.loads(Path(result["artifacts"]["validation_json"]).read_text(encoding="utf-8"))
            self.assertEqual("pass", validation["status"])
            self.assertEqual([], validation["failed_checks"])
            independent = validation["independent_geometry_checks"]
            self.assertEqual("pass", independent["support_axes"]["status"])
            self.assertEqual([], independent["support_axes"]["floating_segments"])
            self.assertEqual([], independent["support_axes"]["axis_interference_failures"])
            self.assertEqual("pass", independent["work_envelope"]["status"])
            self.assertEqual([], independent["work_envelope"]["out_of_bounds"])
            self.assertEqual("pass", independent["bridge_perimeter_service_band"]["status"])
            self.assertEqual([], independent["bridge_perimeter_service_band"]["violations"])
            self.assertGreaterEqual(
                independent["bridge_perimeter_service_band"]["minimum_margin_mm"],
                independent["bridge_perimeter_service_band"]["reserved_band_mm"],
            )
            self.assertEqual("pass", independent["interference"]["status"])
            self.assertEqual([], independent["interference"]["failures"])
            self.assertEqual("pass", independent["gear_mesh_clearance"]["status"])
            self.assertEqual([], independent["gear_mesh_clearance"]["failures"])
            self.assertEqual("pass", independent["housing_parent_body"]["status"])
            self.assertTrue(independent["housing_parent_body"]["mainplate_is_flat_round_disk"])
            self.assertFalse(independent["housing_parent_body"]["case_wall_integrated"])
            self.assertEqual("separate_case_or_review_shell_deferred", independent["housing_parent_body"]["case_boundary_policy"])
            support_ring = independent["housing_parent_body"]["outer_raised_support_ring"]
            self.assertEqual("pass", support_ring["status"])
            self.assertAlmostEqual(independent["bridge_perimeter_service_band"]["reserved_band_mm"], support_ring["width_mm"])
            self.assertAlmostEqual(3.13, semantic["layout"]["z_stack"]["future_bridge"]["bridge_bottom_z_mm"], places=3)
            self.assertAlmostEqual(4.33, semantic["layout"]["z_stack"]["future_bridge"]["future_upper_jewel_top_z_mm"], places=3)
            self.assertAlmostEqual(1.20, support_ring["future_bridge_countersunk_plate_thickness_mm"], places=3)
            self.assertAlmostEqual(2.0783, support_ring["top_z_mm"], places=3)
            self.assertAlmostEqual(1.0517, support_ring["future_bridge_service_step_height_mm"], places=3)
            self.assertLess(
                support_ring["top_z_mm"],
                semantic["layout"]["z_stack"]["future_bridge"]["bridge_bottom_z_mm"],
            )
            self.assertAlmostEqual(
                semantic["layout"]["z_stack"]["future_bridge"]["future_upper_jewel_top_z_mm"],
                support_ring["top_z_mm"]
                + support_ring["future_bridge_service_step_height_mm"]
                + support_ring["future_bridge_countersunk_plate_thickness_mm"],
            )
            self.assertEqual("pass", independent["jewel_supports"]["status"])
            self.assertEqual([], independent["jewel_supports"]["missing_lower_jewels"])
            self.assertEqual([], independent["jewel_supports"]["missing_future_upper_jewels"])
            self.assertEqual([], independent["jewel_supports"]["height_failures"])
            self.assertEqual([], independent["jewel_supports"]["interference_failures"])
            self.assertGreater(independent["jewel_supports"]["minimum_hand_clearance_above_future_upper_jewel_mm"], 0.4)

            role_contract = json.loads(Path(result["artifacts"]["role_contract_json"]).read_text(encoding="utf-8"))
            required_roles = {
                "visual_energy_source",
                "speed_transforming_compound_arbor",
                "escapement_release_wheel",
                "placeholder_escapement_link",
                "time_display_chain",
                "fixed_foundation",
                "lower_jewel_support",
                "future_upper_jewel_support_target",
            }
            self.assertTrue(required_roles.issubset(set(role_contract["roles"])))

    def test_central_display_hand_lengths_follow_axis_and_mainplate_constraints(self):
        design = _build_design(1289)
        axes = {axis["axis_id"]: axis for axis in design["axes"]}
        hands = {hand["hand_id"]: hand for hand in design["display"]["hands"]}
        envelopes = design["display"]["sweep_envelopes"]

        display_axis = axes[DISPLAY_CENTER_AXIS]
        seconds_axis = axes["fourth_axis"]
        center_to_seconds_axis = (
            (display_axis["x"] - seconds_axis["x"]) ** 2
            + (display_axis["y"] - seconds_axis["y"]) ** 2
        ) ** 0.5
        expected_minute_length = round(
            min(MAINPLATE_RADIUS_MM * 0.8, center_to_seconds_axis * 0.9),
            4,
        )

        self.assertAlmostEqual(expected_minute_length, hands["minute_hand"]["length_mm"])
        self.assertAlmostEqual(round(expected_minute_length * 0.5, 4), hands["hour_hand"]["length_mm"])
        self.assertAlmostEqual(hands["minute_hand"]["length_mm"], envelopes["minute_hand"]["radius_mm"])
        self.assertAlmostEqual(hands["hour_hand"]["length_mm"], envelopes["hour_hand"]["radius_mm"])

    def test_step_module_animation_filters_ancestor_occurrence_targets(self):
        design = _build_design(1289)
        step_js = _render_step_module_js(_build_step_module_motion_report(design, external_escapement=True))

        self.assertIn("function safeMotionTarget", step_js)
        self.assertIn("partId === selector || partId.startsWith(`${selector}.`)", step_js)
        self.assertIn("function deepestMotionPartIds", step_js)
        self.assertIn("!partIds.some((other) => other !== partId && other.startsWith(`${partId}.`))", step_js)
        self.assertIn("deepestMotionPartIds(partIds)", step_js)
        self.assertIn("rotateAboutZ(effects, safeMotionTarget(features, feature), angleRad", step_js)
        self.assertNotIn("rotateAboutZ(effects, feature, angleRad", step_js)

    def test_external_step_module_refs_follow_generated_assembly_order(self):
        design = _build_design(1289)
        refs = _step_module_feature_refs(design, external_escapement=True)

        expected_refs = {
            "mainspring_barrel": "#o1.1.26",
            "center_pinion": "#o1.1.27",
            "center_wheel": "#o1.1.28",
            "third_pinion": "#o1.1.29",
            "third_wheel": "#o1.1.30",
            "fourth_pinion": "#o1.1.31",
            "fourth_wheel": "#o1.1.32",
            "escape_pinion": "#o1.1.33",
            "cannon_pinion_assembly": "#o1.1.34",
            "minute_wheel_assembly": "#o1.1.35",
            "hour_wheel": "#o1.1.36",
            "central_display_arbor_extension": "#o1.1.37",
            "seconds_arbor_extension": "#o1.1.38",
            "seconds_hand_collet_cap": "#o1.1.39",
            "hour_tube": "#o1.1.40",
            "cannon_pinion_tube": "#o1.1.41",
            "display_center_collet_stack": "#o1.1.42",
            "hour_hand": "#o1.1.43",
            "minute_hand": "#o1.1.44",
            "seconds_hand": "#o1.1.45",
        }
        for feature_id, expected_ref in expected_refs.items():
            with self.subTest(feature_id=feature_id):
                self.assertEqual(expected_ref, refs[feature_id]["ref"])

    def test_step_module_motion_report_declares_6dof_intent(self):
        design = _build_design(1289)
        report = _build_step_module_motion_report(design, external_escapement=True)

        dof = report["dynamic_6dof_intent"]
        moving = {item["group_id"]: item for item in dof["moving_groups"]}
        self.assertEqual({"rz"}, set(moving["center_train_rotation"]["allowed_dof"]))
        self.assertEqual({"tx", "ty", "tz", "rx", "ry"}, set(moving["center_train_rotation"]["locked_dof"]))
        self.assertEqual([0.0, 0.0, 0.0], moving["center_train_rotation"]["axis_origin"])

        fixed = {item["feature_id"]: item for item in dof["fixed_features"]}
        self.assertEqual({"tx", "ty", "tz", "rx", "ry", "rz"}, set(fixed["external_pallet_fork"]["locked_dof"]))
        self.assertEqual("pass", report["checks"]["dynamic_6dof_intent_declared"])

    def test_phase1_uses_validation_first_role_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_power_chain_mvp(Path(tmp), seed=731)

            semantic = json.loads(Path(result["artifacts"]["semantic_json"]).read_text(encoding="utf-8"))
            validation = json.loads(Path(result["artifacts"]["validation_json"]).read_text(encoding="utf-8"))
            role_contract = json.loads(Path(result["artifacts"]["role_contract_json"]).read_text(encoding="utf-8"))

            self.assertEqual("watch_power_chain_phase1_no_bridges", role_contract["pattern_card_id"])
            contracts = {contract["occurrence_id"]: contract for contract in role_contract["contracts"]}
            for hand_id, expected_axis in {
                "hour_hand": "display_center_axis",
                "minute_hand": "display_center_axis",
                "seconds_hand": "fourth_axis",
            }.items():
                with self.subTest(hand_id=hand_id):
                    contract = contracts[hand_id]
                    self.assertEqual("display_hand", contract["role"])
                    self.assertEqual(expected_axis, contract["geometry_constraint"]["axis_id"])
                    self.assertIn("motion_chain", contract)
                    self.assertIn("mount_chain", contract)
                    self.assertIn("feature_attachment_chain", contract)
                    self.assertIn("constraint_chain", contract)
                    self.assertIn("geometry_constraint", contract)
                    self.assertIn("validation_contract", contract)
                    self.assertEqual("pass", contract["validation"]["status"])
                    self.assertEqual([], contract["validation"]["missing_evidence"])
                    self.assertIn(f"{hand_id}_hub", contract["required_features"])
                    self.assertIn(f"{hand_id}_blade", contract["feature_attachment_chain"]["features"])

            independent = validation["independent_geometry_checks"]
            self.assertEqual("pass", independent["status"])
            self.assertEqual("design_geometry_facts_not_generator_narrative", independent["fact_source"])
            self.assertEqual({"hour_hand", "minute_hand", "seconds_hand"}, set(independent["hand_mounts"]))
            for hand_id, report in independent["hand_mounts"].items():
                with self.subTest(independent_mount=hand_id):
                    self.assertEqual("pass", report["status"])
                    self.assertTrue(report["xy_connected"])
                    self.assertTrue(report["z_connected"])
                    self.assertTrue(report["radially_connected"])
                    self.assertTrue(report["six_dof_constrained"])
                    self.assertLessEqual(report["max_xy_center_error_mm"], 0.01)
                    self.assertGreater(report["min_radial_overlap_mm"], 0.03)
            self.assertEqual({"hour_hand", "minute_hand", "seconds_hand"}, set(independent["feature_attachments"]))
            for hand_id, report in independent["feature_attachments"].items():
                with self.subTest(feature_attachment=hand_id):
                    self.assertEqual("pass", report["status"])
                    self.assertTrue(report["blade_attached_to_hub"])
                    self.assertLessEqual(report["blade_to_axis_distance_mm"], report["hub_outer_radius_mm"] + 0.02)
            self.assertEqual("pass", independent["motion_chains"]["status"])
            self.assertEqual("pass", independent["motion_chains"]["hour_hand"]["status"])
            self.assertEqual("geometry_and_ratio_proof", independent["motion_chains"]["hour_hand"]["fact_source"])
            self.assertEqual("pass", independent["coaxial_sleeves"]["status"])
            self.assertEqual("pass", independent["support_axes"]["status"])
            self.assertEqual("pass", independent["work_envelope"]["status"])
            self.assertEqual("pass", independent["interference"]["status"])
            self.assertEqual("pass", independent["gear_mesh_clearance"]["status"])
            self.assertEqual("pass", independent["housing_parent_body"]["status"])
            self.assertEqual("pass", independent["jewel_supports"]["status"])

            self.assertTrue(semantic["checks"]["independent_display_mount_geometry"])
            self.assertTrue(semantic["checks"]["independent_display_feature_attachment_geometry"])
            self.assertTrue(semantic["checks"]["independent_display_motion_chain_geometry"])
            self.assertTrue(semantic["checks"]["independent_coaxial_sleeve_clearance"])
            self.assertTrue(semantic["checks"]["independent_support_axis_geometry"])
            self.assertTrue(semantic["checks"]["independent_work_envelope_geometry"])
            self.assertTrue(semantic["checks"]["independent_bridge_perimeter_service_band_geometry"])
            self.assertTrue(semantic["checks"]["independent_internal_interference_geometry"])
            self.assertTrue(semantic["checks"]["independent_gear_mesh_clearance_geometry"])
            self.assertTrue(semantic["checks"]["independent_housing_parent_body_geometry"])
            self.assertTrue(semantic["checks"]["independent_jewel_support_geometry"])
            self.assertEqual("pass", validation["checks"]["independent_geometry_checks"])

    def test_mainplate_outer_raised_support_ring_owns_bridge_service_band(self):
        design = _build_design(731)
        independent = _build_independent_geometry_report(design)

        housing = independent["housing_parent_body"]
        ring = housing["outer_raised_support_ring"]
        service_band = independent["bridge_perimeter_service_band"]

        self.assertEqual("pass", housing["status"])
        self.assertEqual("pass", ring["status"])
        self.assertEqual("foundation_mainplate", ring["owner"])
        self.assertEqual("parent_body_feature", ring["structure_class"])
        self.assertAlmostEqual(BRIDGE_PERIMETER_RESERVED_BAND_MM, ring["width_mm"])
        self.assertEqual("mainplate_outer_raised_support_ring", ring["feature_id"])
        self.assertIn("mainplate_outer_raised_support_ring", service_band["legal_service_band_owners"])
        self.assertEqual([], service_band["violations"])
        self.assertAlmostEqual(3.13, design["z_stack"]["future_bridge"]["bridge_bottom_z_mm"], places=3)
        self.assertAlmostEqual(4.33, design["z_stack"]["future_bridge"]["future_upper_jewel_top_z_mm"], places=3)
        self.assertAlmostEqual(1.20, ring["future_bridge_countersunk_plate_thickness_mm"], places=3)
        self.assertAlmostEqual(2.0783, ring["top_z_mm"], places=3)
        self.assertAlmostEqual(1.0517, ring["future_bridge_service_step_height_mm"], places=3)
        self.assertEqual([2, 1], ring["support_face_to_service_step_split"])
        self.assertEqual("DIN 965 / ISO 7046 countersunk flat head screw", ring["bridge_fastener_standard"])
        self.assertEqual("M1.4", ring["bridge_fastener_thread_size"])
        self.assertLess(
            ring["top_z_mm"],
            design["z_stack"]["future_bridge"]["bridge_bottom_z_mm"],
        )
        self.assertGreaterEqual(
            ring["future_bridge_countersunk_plate_thickness_mm"],
            ring["countersunk_head_depth_mm"] + ring["minimum_residual_material_below_countersink_mm"],
        )
        self.assertAlmostEqual(
            design["z_stack"]["future_bridge"]["future_upper_jewel_top_z_mm"],
            ring["top_z_mm"]
            + ring["future_bridge_service_step_height_mm"]
            + ring["future_bridge_countersunk_plate_thickness_mm"],
            places=4,
        )

    def test_upper_jewel_bearings_are_on_train_axes_not_hand_axes(self):
        design = _build_design(731)
        independent = _build_independent_geometry_report(design)
        jewel_supports = independent["jewel_supports"]

        expected_axis_ids = sorted(
            {
                gear["axis_id"]
                for gear in [*design["gears"], *design["display_gears"]]
                if gear["axis_id"] != DISPLAY_CENTER_AXIS
            }
        )
        expected_axis_ids.append("center_axis")
        expected_axis_ids = sorted(set(expected_axis_ids))

        self.assertEqual(expected_axis_ids, jewel_supports["upper_jewel_bearing_axis_ids"])
        self.assertNotIn(DISPLAY_CENTER_AXIS, jewel_supports["upper_jewel_bearing_axis_ids"])
        self.assertEqual([], jewel_supports["missing_upper_jewel_bearings"])
        self.assertEqual([], jewel_supports["upper_jewel_display_axis_violations"])
        self.assertEqual([], jewel_supports["upper_pivot_reach_failures"])
        self.assertEqual([], jewel_supports["upper_pivot_overrun_failures"])
        self.assertEqual("pass", jewel_supports["upper_jewel_plane"]["status"])
        self.assertEqual("uniform_future_bridge_upper_jewel_top_plane", jewel_supports["upper_jewel_plane"]["plane_id"])

        top_values = {
            bearing["z_max"]
            for bearing in jewel_supports["upper_jewel_bearings_by_axis"].values()
        }
        self.assertEqual(1, len(top_values))
        self.assertEqual(jewel_supports["future_upper_jewel_top_z_mm"], next(iter(top_values)))
        self.assertGreater(
            min(hand["z_mm"] for hand in design["display"]["hands"]),
            jewel_supports["future_upper_jewel_top_z_mm"],
        )

    def test_bridge_stage_declares_three_supported_bridge_plates(self):
        design = _build_design(864, include_bridges=True)
        independent = _build_independent_geometry_report(design)
        bridge_stage = independent["bridge_stage"]

        self.assertTrue(design["bridges_generated"])
        self.assertEqual("pass", bridge_stage["status"])
        self.assertEqual(
            ["barrel_bridge", "train_bridge", "escapement_bridge"],
            [bridge["bridge_id"] for bridge in bridge_stage["bridges"]],
        )
        self.assertEqual("shared_pitch_circle", bridge_stage["screw_policy"]["placement"])
        self.assertAlmostEqual(0.8, bridge_stage["review_metadata"]["opacity"], places=3)
        self.assertEqual("fixed_width_parallel_seams", bridge_stage["seam_policy"]["kind"])
        self.assertGreater(bridge_stage["seam_policy"]["gap_width_mm"], 0.0)
        self.assertEqual(6.5, bridge_stage["support_pad_policy"]["arc_length_to_screw_head_diameter_ratio"])
        self.assertEqual([], bridge_stage["failures"])

        pitch_radii = {
            screw["pitch_radius_mm"]
            for bridge in bridge_stage["bridges"]
            for screw in bridge["screws"]
        }
        self.assertEqual(1, len(pitch_radii))

        supported_axes = {
            axis_id
            for bridge in bridge_stage["bridges"]
            for axis_id in bridge["supported_axis_ids"]
        }
        self.assertTrue(
            set(independent["jewel_supports"]["upper_jewel_bearing_axis_ids"]).issubset(supported_axes)
        )
        train_bridge = next(bridge for bridge in bridge_stage["bridges"] if bridge["bridge_id"] == "train_bridge")
        self.assertIn("center_axis", train_bridge["supported_axis_ids"])
        self.assertEqual("train_bridge", bridge_stage["central_axis_policy"]["owning_bridge_id"])
        self.assertEqual("covered_by_train_bridge_boss", bridge_stage["central_axis_policy"]["support_strategy"])
        self.assertEqual("center_axis", train_bridge["central_axis_feature"]["axis_id"])
        self.assertGreater(train_bridge["central_axis_feature"]["outer_radius_mm"], 0.0)

        for bridge in bridge_stage["bridges"]:
            with self.subTest(bridge=bridge["bridge_id"]):
                expected_count = 3 if bridge["angular_span_deg"] > 90.0 else 2
                expected_hole_axis_ids = set(bridge["supported_axis_ids"]) & set(
                    independent["jewel_supports"]["upper_jewel_bearing_axis_ids"]
                )
                self.assertEqual(expected_count, bridge["required_screw_count"])
                self.assertEqual(expected_count, len(bridge["screws"]))
                self.assertEqual(expected_count, len(bridge["support_pads"]))
                self.assertAlmostEqual(
                    design["housing"]["outer_raised_support_ring"]["outer_radius_mm"],
                    bridge["outer_radius_mm"],
                    places=4,
                )
                if expected_count > 1:
                    first_offset = (bridge["screws"][0]["angle_deg"] - bridge["angular_start_deg"]) % 360.0
                    last_offset = (bridge["angular_end_deg"] - bridge["screws"][-1]["angle_deg"]) % 360.0
                    self.assertLessEqual(first_offset, bridge_stage["screw_policy"]["edge_margin_deg"] + 1e-6)
                    self.assertLessEqual(last_offset, bridge_stage["screw_policy"]["edge_margin_deg"] + 1e-6)
                for screw in bridge["screws"]:
                    self.assertEqual("countersunk_flat_head_screw", screw["fastener_kind"])
                    self.assertEqual("DIN 965 / ISO 7046 countersunk flat head screw", screw["standard"])
                    self.assertGreater(screw["head_diameter_mm"], screw["nominal_thread_diameter_mm"])
                    self.assertGreater(screw["countersink_depth_mm"], 0.0)
                    self.assertEqual("flush_to_bridge_top", screw["head_top_policy"])
                    self.assertGreater(screw["threaded_engagement_depth_mm"], 0.0)
                    self.assertLess(screw["threaded_hole_bottom_z_mm"], screw["threaded_hole_top_z_mm"])
                self.assertEqual("constant_width_parallel_gap_edges", bridge["seam_boundary_policy"])
                self.assertEqual(bridge_stage["seam_policy"]["gap_width_mm"], bridge["seam_gap_width_mm"])
                self.assertIn("start", bridge["seam_boundary_lines"])
                self.assertIn("end", bridge["seam_boundary_lines"])
                self.assertEqual("parallel_offset_from_seam_centerline", bridge["seam_boundary_lines"]["start"]["construction"])
                self.assertEqual("parallel_offset_from_seam_centerline", bridge["seam_boundary_lines"]["end"]["construction"])
                self.assertEqual(len(expected_hole_axis_ids), len(bridge["clearance_holes"]))
                self.assertEqual(
                    expected_hole_axis_ids,
                    {hole["axis_id"] for hole in bridge["clearance_holes"]},
                )
                self.assertAlmostEqual(
                    design["z_stack"]["future_bridge"]["bridge_bottom_z_mm"],
                    bridge["z_min_mm"],
                    places=4,
                )
                self.assertAlmostEqual(
                    design["z_stack"]["future_bridge"]["future_upper_jewel_top_z_mm"],
                    bridge["z_max_mm"],
                    places=4,
                )
                for pad in bridge["support_pads"]:
                    self.assertEqual("outer_annular_service_pad", pad["footprint_type"])
                    self.assertEqual("mainplate_outer_raised_support_ring", pad["support_face"])
                    self.assertAlmostEqual(
                        design["housing"]["outer_raised_support_ring"]["inner_radius_mm"],
                        pad["inner_radius_mm"],
                        places=4,
                    )
                    self.assertAlmostEqual(
                        design["housing"]["outer_raised_support_ring"]["outer_radius_mm"],
                        pad["outer_radius_mm"],
                        places=4,
                    )
                    self.assertAlmostEqual(
                        pad["target_outer_arc_length_mm"],
                        bridge_stage["support_pad_policy"]["arc_length_to_screw_head_diameter_ratio"]
                        * bridge["screws"][0]["head_diameter_mm"],
                        places=4,
                    )
                    self.assertAlmostEqual(
                        pad["target_angular_span_deg"],
                        (pad["angular_end_deg"] - pad["angular_start_deg"]) % 360.0,
                        places=4,
                    )
                    if pad["pad_position"] == "start_edge":
                        self.assertAlmostEqual(pad["angular_start_deg"], bridge["angular_start_deg"], places=4)
                    if pad["pad_position"] == "end_edge":
                        self.assertAlmostEqual(pad["angular_end_deg"], bridge["angular_end_deg"], places=4)
                    self.assertAlmostEqual(
                        design["housing"]["outer_raised_support_ring"]["top_z_mm"],
                        pad["z_min_mm"],
                        places=4,
                    )
                    self.assertAlmostEqual(bridge["z_min_mm"], pad["z_max_mm"], places=4)

    def test_run_power_chain_mvp_supports_separate_hour_minute_no_seconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_power_chain_mvp(
                Path(tmp) / "separate_display_seed_731",
                seed=731,
                pattern_card_id="separate_hour_minute_no_seconds_v1",
            )

            self.assertEqual("pass", result["status"])
            for artifact_name in [
                "step",
                "step_module_js",
                "semantic_json",
                "validation_json",
                "role_contract_json",
                "solver_json",
                "dashboard_html",
            ]:
                path = Path(result["artifacts"][artifact_name])
                self.assertTrue(path.exists(), f"{artifact_name} missing")
                self.assertGreater(path.stat().st_size, 0, f"{artifact_name} is empty")

            step_text = Path(result["artifacts"]["step"]).read_text(encoding="utf-8", errors="ignore")
            for label in [
                "minute_hand",
                "hour_hand",
                "minute_display_axis",
                "hour_display_axis",
                "external_escape_wheel",
                "external_pallet_fork",
                "external_balance_wheel",
                "external_hairspring",
                "external_escapement_reference_plate",
            ]:
                with self.subTest(required_step_label=label):
                    self.assertIn(label, step_text)
            for label in [
                "seconds_hand",
                "seconds_arbor_extension",
                "display_center_axis",
                "pallet_placeholder_disc",
                "balance_placeholder_disc",
                "escapement_to_balance_placeholder_envelope",
                "pallet_placeholder_axis",
                "balance_placeholder_axis",
            ]:
                with self.subTest(forbidden_step_label=label):
                    self.assertNotIn(label, step_text)

            sidecar_text = Path(result["artifacts"]["step_module_js"]).read_text(encoding="utf-8")
            self.assertIn("minute_display_axis", sidecar_text)
            self.assertIn("hour_display_axis", sidecar_text)
            self.assertIn("minute_display_rotation", sidecar_text)
            self.assertIn("hour_display_rotation", sidecar_text)
            self.assertNotIn("seconds_hand", sidecar_text)

            semantic = json.loads(Path(result["artifacts"]["semantic_json"]).read_text(encoding="utf-8"))
            validation = json.loads(Path(result["artifacts"]["validation_json"]).read_text(encoding="utf-8"))
            for report in [semantic, validation]:
                self.assertEqual("separate_hour_minute_no_seconds_v1", report["pattern_card_id"])
                self.assertEqual("pass", report["checks"]["no_seconds_hand"])
                self.assertEqual("pass", report["checks"]["separate_minute_and_hour_axes"])
                self.assertEqual("pass", report["checks"]["hour_to_minute_ratio_1_to_12"])
                self.assertEqual("pass", report["checks"]["external_escapement_assembly_present"])
                self.assertEqual("pass", report["checks"]["minute_display_power_chain_connected_to_train"])
            self.assertEqual("pass", validation["checks"]["independent_geometry_checks"])
            self.assertEqual("pass", validation["checks"]["independent_gear_mesh_clearance_geometry"])
            self.assertEqual("pass", validation["checks"]["independent_internal_interference_geometry"])
            independent = validation["independent_geometry_checks"]
            self.assertEqual("pass", independent["gear_mesh_clearance"]["status"])
            self.assertEqual([], independent["gear_mesh_clearance"]["failures"])
            mesh_records = {
                (record["driver"], record["driven"]): record
                for record in independent["gear_mesh_clearance"]["records"]
            }
            for mesh_pair in [
                ("train_stage_3_wheel", "escape_pinion"),
                ("train_stage_3_wheel", "display_input_relay_pinion"),
                ("display_input_relay_wheel", "minute_display_member"),
                ("minute_display_member", "display_relay_pinion"),
                ("display_relay_wheel", "hour_display_member"),
            ]:
                with self.subTest(mesh_pair=mesh_pair):
                    record = mesh_records[mesh_pair]
                    self.assertLessEqual(abs(record["pitch_distance_error_mm"]), 0.001)
                    self.assertGreaterEqual(record["driver_tip_to_driven_root_clearance_mm"], 0.0)
                    self.assertGreaterEqual(record["driven_tip_to_driver_root_clearance_mm"], 0.0)

            minute_chain = next(chain for chain in semantic["display"]["drive_chains"] if chain["hand_id"] == "minute_hand")
            self.assertEqual(
                "external_mesh_external_mesh_rigid_display_member",
                minute_chain["interface_sequence"],
            )
            self.assertEqual(
                [
                    "train_stage_3_wheel",
                    "display_input_relay_pinion",
                    "display_input_relay_wheel",
                    "minute_display_member",
                    "minute_hand",
                ],
                minute_chain["path"],
            )
            coupling = semantic["display"]["motion_works"]["train_to_minute_display_coupling"]
            self.assertEqual("pass", coupling["status"])
            self.assertEqual(1.0, coupling["ratio_proof"]["computed_ratio"])
            self.assertIn(
                {"driver": "train_stage_3_wheel", "driven": "display_input_relay_pinion", "kind": "external"},
                semantic["layout"]["display_meshes"],
            )
            self.assertIn(
                {"driver": "display_input_relay_wheel", "driven": "minute_display_member", "kind": "external"},
                semantic["layout"]["display_meshes"],
            )

            contracts = json.loads(Path(result["artifacts"]["role_contract_json"]).read_text(encoding="utf-8"))
            contracts_by_id = {contract["occurrence_id"]: contract for contract in contracts["contracts"]}
            for occurrence_id in [
                "minute_display_axis",
                "minute_display_member",
                "minute_hand",
                "display_input_relay_axis",
                "display_input_relay_compound_member",
                "hour_display_axis",
                "hour_display_member",
                "hour_hand",
                "display_relay_axis",
                "display_relay_compound_member",
            ]:
                with self.subTest(contract=occurrence_id):
                    contract = contracts_by_id[occurrence_id]
                    self.assertIn("motion_chain", contract)
                    self.assertIn("mount_chain", contract)
                    self.assertIn("constraint_chain", contract)
                    self.assertIn("feature_attachment_chain", contract)
                    self.assertIn("geometry_constraint", contract)
                    self.assertIn("validation_contract", contract)

    def test_separate_display_independent_geometry_covers_real_power_chain_meshes(self):
        design = _build_separate_display_design(731, solve_separate_display_layout(seed=731))

        independent = _build_independent_geometry_report(design)

        self.assertEqual("pass", independent["status"])
        self.assertEqual("pass", independent["gear_mesh_clearance"]["status"])
        records = {
            (record["driver"], record["driven"]): record
            for record in independent["gear_mesh_clearance"]["records"]
        }
        for mesh_pair in [
            ("train_stage_3_wheel", "escape_pinion"),
            ("train_stage_3_wheel", "display_input_relay_pinion"),
            ("display_input_relay_wheel", "minute_display_member"),
            ("minute_display_member", "display_relay_pinion"),
            ("display_relay_wheel", "hour_display_member"),
        ]:
            with self.subTest(mesh_pair=mesh_pair):
                record = records[mesh_pair]
                self.assertLessEqual(abs(record["pitch_distance_error_mm"]), 0.001)
                self.assertGreaterEqual(record["driver_tip_to_driven_root_clearance_mm"], 0.0)
                self.assertGreaterEqual(record["driven_tip_to_driver_root_clearance_mm"], 0.0)

        explicit_clearance = _build_gear_mesh_clearance_report(design)
        self.assertEqual("pass", explicit_clearance["status"])

    def test_separate_display_external_escapement_axes_are_owned_by_external_assembly(self):
        design = _build_separate_display_design(731, solve_separate_display_layout(seed=731))

        pallet_axis = _axis_by_id(design, "pallet_axis")
        balance_axis = _axis_by_id(design, "balance_axis")

        self.assertFalse(pallet_axis["support_required"])
        self.assertFalse(balance_axis["support_required"])
        self.assertEqual([], pallet_axis["support_segments"])
        self.assertEqual([], balance_axis["support_segments"])

    def test_separate_display_hand_mount_stacks_include_real_arbor_extensions(self):
        design = _build_separate_display_design(731, solve_separate_display_layout(seed=731))

        stacks = {stack["hand_id"]: stack for stack in design["display"]["mount_stacks"]}
        for hand_id, extension_id in {
            "minute_hand": "minute_hand_arbor_extension",
            "hour_hand": "hour_hand_arbor_extension",
        }.items():
            with self.subTest(hand_id=hand_id):
                segment_ids = [segment["component_id"] for segment in stacks[hand_id]["segments"]]
                self.assertIn(extension_id, segment_ids)
                self.assertGreaterEqual(len(stacks[hand_id]["interfaces"]), 2)
                self.assertEqual("pass", _build_independent_geometry_report(design)["hand_mounts"][hand_id]["status"])

    def test_separate_display_mesh_phase_records_cover_train_and_display_meshes(self):
        design = _build_separate_display_design(731, solve_separate_display_layout(seed=731))

        expected_pairs = {
            (mesh["driver"], mesh["driven"])
            for mesh in [*design["meshes"], *design["display_meshes"]]
        }
        records = [*design["mesh_phase_records"], *design["display_mesh_phase_records"]]

        self.assertEqual(expected_pairs, {(record["driver"], record["driven"]) for record in records})
        for record in records:
            with self.subTest(mesh=(record["driver"], record["driven"])):
                self.assertLessEqual(abs(record["driver_tooth_error_deg"]), GEAR_MESH_PHASE_TOLERANCE_DEG)
                self.assertLessEqual(abs(record["driven_gap_error_deg"]), GEAR_MESH_PHASE_TOLERANCE_DEG)

    def test_separate_display_motion_json_declares_two_real_hand_axes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_power_chain_mvp(
                Path(tmp) / "separate_display_seed_731",
                seed=731,
                pattern_card_id="separate_hour_minute_no_seconds_v1",
            )

            motion = json.loads(Path(result["artifacts"]["motion_json"]).read_text(encoding="utf-8"))
            groups = {group["group_id"]: group for group in motion["moving_groups"]}
            self.assertEqual("minute_display_axis", groups["minute_display_rotation"]["axis_id"])
            self.assertEqual("hour_display_axis", groups["hour_display_rotation"]["axis_id"])
            self.assertEqual(-1.0, groups["hour_display_rotation"]["angular_velocity_ratio_to_hour_hand"])
            self.assertEqual(-12.0, groups["minute_display_rotation"]["angular_velocity_ratio_to_hour_hand"])
            self.assertNotIn("seconds_hand", json.dumps(motion))

            validation = json.loads(Path(result["artifacts"]["validation_json"]).read_text(encoding="utf-8"))
            checks = validation["checks"]
            self.assertEqual("pass", checks["minute_hand_mount_6dof_pass"])
            self.assertEqual("pass", checks["hour_hand_mount_6dof_pass"])
            self.assertEqual("pass", checks["animation_leaf_binding_pass"])

    def test_separate_display_step_module_features_bind_to_step_occurrences(self):
        design = _build_separate_display_design(731, solve_separate_display_layout(seed=731))
        motion = _build_separate_display_motion_report(design)
        features = _separate_display_step_module_features(design)

        required_motion_ids = {
            feature_id
            for group in motion["moving_groups"]
            for feature_id in group["feature_ids"]
        } | set(motion["fixed_features"])

        self.assertTrue(required_motion_ids)
        for feature_id in sorted(required_motion_ids):
            with self.subTest(feature_id=feature_id):
                feature = features.get(feature_id)
                self.assertIsNotNone(feature)
                selectors = feature.get("selectors", [])
                part_ids = feature.get("partIds", [])
                self.assertTrue(selectors, "missing STEP selector")
                self.assertTrue(part_ids, "missing STEP part id")
                self.assertNotEqual([feature_id], selectors)
                self.assertNotEqual([feature_id], part_ids)
                self.assertTrue(all(selector.startswith("#o1.") for selector in selectors))
                self.assertTrue(all(part_id.startswith("#o1.") for part_id in part_ids))

    def test_separate_display_motion_expands_split_visible_gear_features(self):
        design = _build_separate_display_design(731, solve_separate_display_layout(seed=731))
        features = _separate_display_step_module_features(design)
        split_aliases = {
            "train_stage_1_pinion": ["train_stage_1_pinion_tooth_profile", "train_stage_1_pinion_hub"],
            "train_stage_2_pinion": ["train_stage_2_pinion_tooth_profile", "train_stage_2_pinion_hub"],
            "train_stage_3_pinion": ["train_stage_3_pinion_tooth_profile", "train_stage_3_pinion_hub"],
            "display_input_relay_wheel": [
                "display_input_relay_wheel_tooth_profile",
                "display_input_relay_wheel_hub",
            ],
            "display_relay_wheel": ["display_relay_wheel_tooth_profile", "display_relay_wheel_hub"],
        }

        for parent_id, child_ids in split_aliases.items():
            parent_ref = features.pop(parent_id)
            for index, child_id in enumerate(child_ids, start=1):
                child_ref = copy.deepcopy(parent_ref)
                child_ref["ref"] = f"{parent_ref['ref']}.{index}"
                child_ref["selectors"] = [child_ref["ref"]]
                child_ref["partIds"] = [child_ref["ref"]]
                features[child_id] = child_ref

        motion = _build_separate_display_motion_report(design, feature_refs_override=features)
        moving_feature_ids = {
            feature_id
            for group in motion["moving_groups"]
            for feature_id in group["feature_ids"]
        }

        self.assertEqual("pass", motion["checks"]["animation_leaf_binding_pass"])
        for parent_id, child_ids in split_aliases.items():
            self.assertNotIn(parent_id, moving_feature_ids)
            self.assertTrue(set(child_ids) <= moving_feature_ids)

    def test_separate_display_negative_motion_validation_cases_fail(self):
        design = _build_separate_display_design(731, solve_separate_display_layout(seed=731))
        motion = _build_separate_display_motion_report(design)

        collapsed_axes = copy.deepcopy(design)
        minute_axis = next(axis for axis in collapsed_axes["axes"] if axis["axis_id"] == "minute_display_axis")
        hour_axis = next(axis for axis in collapsed_axes["axes"] if axis["axis_id"] == "hour_display_axis")
        hour_axis["x"] = minute_axis["x"]
        hour_axis["y"] = minute_axis["y"]
        self.assertEqual(
            "fail",
            _separate_display_task4_checks(collapsed_axes, motion)["actual_minute_hour_axis_separation_pass"],
        )

        missing_relay = copy.deepcopy(design)
        missing_relay["display_gears"] = [
            gear for gear in missing_relay["display_gears"] if gear["gear_id"] != "display_relay_wheel"
        ]
        self.assertEqual(
            "fail",
            _separate_display_task4_checks(missing_relay, motion)["display_relay_motion_chain_complete"],
        )

        forbidden_hand = copy.deepcopy(design)
        forbidden_hand["display"]["hands"].append({"hand_id": "seconds_hand", "axis_id": "seconds_axis"})
        self.assertEqual(
            "fail",
            _separate_display_task4_checks(forbidden_hand, motion)["display_no_forbidden_seconds_roles"],
        )

        ancestor_bound_motion = copy.deepcopy(motion)
        ancestor_bound_motion["moving_groups"][0]["feature_ids"] = [
            "watch_power_chain_separate_hour_minute_no_seconds_assembly"
        ]
        self.assertEqual(
            "fail",
            _separate_display_task4_checks(design, ancestor_bound_motion)["animation_leaf_binding_pass"],
        )

    def test_z_stack_solver_limits_gears_to_four_valid_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_power_chain_mvp(Path(tmp), seed=731)

            semantic = json.loads(Path(result["artifacts"]["semantic_json"]).read_text(encoding="utf-8"))
            validation = json.loads(Path(result["artifacts"]["validation_json"]).read_text(encoding="utf-8"))

            self.assertIn("z_stack", semantic["layout"])
            z_stack = semantic["layout"]["z_stack"]
            self.assertEqual("pass", z_stack["status"])
            self.assertEqual(4, z_stack["max_gear_layer_count"])
            self.assertEqual(
                "mainplate_top_plus_layer_clearances",
                z_stack["placement_policy"],
            )
            self.assertEqual("pass", z_stack["checks"]["all_gear_layers_declared"])
            self.assertEqual("pass", z_stack["checks"]["max_gear_layer_count"])
            self.assertEqual("pass", z_stack["checks"].get("actual_distinct_gear_z_bands", "missing"))
            self.assertEqual("pass", z_stack["checks"]["gear_z_matches_assignments"])
            self.assertEqual("pass", z_stack["checks"]["display_stack_above_train"])
            self.assertEqual("pass", z_stack["checks"]["future_upper_jewel_plane_below_hands"])
            self.assertEqual("pass", z_stack["checks"]["future_upper_jewel_plane_above_train"])
            self.assertIn("future_bridge", z_stack)
            self.assertEqual("flat_bridge_plate_future_phase", z_stack["future_bridge"]["phase"])
            self.assertGreater(z_stack["future_bridge"]["minimum_hand_clearance_mm"], 0.4)

            assignments = z_stack["assignments"]
            actual_z_bands = {
                round(gear["z"], 3)
                for gear in [*semantic["layout"]["gears"], *semantic["layout"]["display_gears"]]
            }
            self.assertLessEqual(len(actual_z_bands), z_stack["max_gear_layer_count"])
            self.assertEqual(sorted(actual_z_bands), z_stack["actual_gear_z_bands_mm"])
            for gear in [*semantic["layout"]["gears"], *semantic["layout"]["display_gears"]]:
                with self.subTest(gear=gear["gear_id"]):
                    assignment = assignments[gear["gear_id"]]
                    self.assertLessEqual(assignment["layer_index"], 4)
                    self.assertEqual(assignment["layer_index"], gear["z_stack_layer"])
                    self.assertAlmostEqual(assignment["z_min_mm"], gear["z"], places=4)
                    self.assertAlmostEqual(assignment["z_max_mm"], gear["z"] + gear["height"], places=4)

            independent = validation["independent_geometry_checks"]
            self.assertIn("z_stack", independent)
            self.assertEqual("pass", independent["z_stack"]["status"])
            self.assertEqual("pass", validation["checks"]["z_stack_layering"])
            self.assertTrue(semantic["checks"]["z_stack_layering_valid"])

    def test_fixed_arbors_do_not_use_rotating_gears_as_clearance_plates(self):
        design = _build_design(731)
        axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
        moving_gear_ids = {
            gear["gear_id"]
            for gear in [*design["gears"], *design["display_gears"]]
            if gear["gear_type"] in {"wheel", "pinion", "escape"}
        }

        for gear in [*design["gears"], *design["display_gears"]]:
            for hole in gear.get("clearance_holes", []):
                with self.subTest(gear=gear["gear_id"], hole=hole["hole_id"]):
                    self.assertEqual(
                        gear["axis_id"],
                        hole["axis_id"],
                        "a rotating gear may only have same-axis functional bores; foreign fixed-axis pass-through holes must be rejected by the solver",
                    )
                    self.assertNotIn(
                        gear["gear_id"],
                        moving_gear_ids,
                        "foreign-axis clearance holes in moving gears hide dynamic interference",
                    )

        independent = _build_independent_geometry_report(design)
        self.assertEqual("pass", independent["support_axes"]["status"])
        self.assertEqual([], independent["support_axes"]["axis_interference_failures"])
        self.assertIn("pattern_solver", design)
        selected = design["pattern_solver"]["selected_candidate"]
        proof_ids = {proof["proof_id"] for proof in selected["shaft_to_foreign_gear_keepout_proofs"]}
        self.assertIn("minute_work_axis_vs_center_wheel", proof_ids)

    def test_support_axes_envelope_and_housing_reject_current_known_failure_modes(self):
        design = _build_design(731)
        axis_by_id = {axis["axis_id"]: axis for axis in design["axes"]}
        center_wheel = next(gear for gear in design["gears"] if gear["gear_id"] == "center_wheel")
        minute_axis = axis_by_id["minute_work_axis"]
        center_axis = axis_by_id["center_axis"]
        minute_axis["x"] = 2.2627
        minute_axis["y"] = -2.2627
        minute_axis["support_segments"] = [
            {"segment_id": "lower_arbor_minute_work_axis", "z_min": -0.7, "z_max": 3.1, "radius": 0.16},
            {"segment_id": "minute_work_arbor", "z_min": 3.36, "z_max": 4.12, "radius": 0.16},
        ]
        distance = ((minute_axis["x"] - center_axis["x"]) ** 2 + (minute_axis["y"] - center_axis["y"]) ** 2) ** 0.5
        self.assertLess(distance + 0.16, center_wheel["outer_radius"])
        design["housing"] = {"mainplate_is_flat_round_disk": False}

        independent = _build_independent_geometry_report(design)

        self.assertEqual("fail", independent["support_axes"]["status"])
        self.assertTrue(independent["support_axes"]["floating_segments"])
        self.assertTrue(independent["support_axes"]["axis_interference_failures"])
        self.assertEqual("fail", independent["housing_parent_body"]["status"])

    def test_bridge_perimeter_service_band_rejects_elements_too_close_to_mainplate_edge(self):
        design = _build_design(731)
        balance_axis = _axis_by_id(design, "balance_axis")
        balance_axis["x"] = 19.8
        balance_axis["y"] = 0.0

        independent = _build_independent_geometry_report(design)

        self.assertEqual("fail", independent["bridge_perimeter_service_band"]["status"])
        self.assertTrue(independent["bridge_perimeter_service_band"]["violations"])

    def test_bridge_perimeter_service_band_exempts_seconds_hand_above_bridge_plane(self):
        design = _build_design(731)
        fourth_axis = _axis_by_id(design, "fourth_axis")
        seconds_hand = next(hand for hand in design["display"]["hands"] if hand["hand_id"] == "seconds_hand")
        seconds_sweep = design["display"]["sweep_envelopes"]["seconds_hand"]
        mainplate_radius = design["housing"]["mainplate_radius_mm"]
        near_outer_edge_radius = mainplate_radius - (fourth_axis["x"] ** 2 + fourth_axis["y"] ** 2) ** 0.5 - 0.35
        self.assertLess(
            0.35,
            design["housing"]["bridge_perimeter_reserved_band_mm"],
            "test setup puts the seconds-hand sweep inside the bridge screw service band in XY",
        )
        seconds_hand["length_mm"] = round(near_outer_edge_radius, 4)
        seconds_sweep["radius_mm"] = round(near_outer_edge_radius, 4)

        independent = _build_independent_geometry_report(design)

        self.assertEqual("pass", independent["bridge_perimeter_service_band"]["status"])
        self.assertEqual([], independent["bridge_perimeter_service_band"]["violations"])
        exemptions = {
            exemption["entity_id"]: exemption
            for exemption in independent["bridge_perimeter_service_band"]["z_height_exemptions"]
        }
        self.assertIn("seconds_hand_sweep", exemptions)
        self.assertEqual("above_future_bridge_top", exemptions["seconds_hand_sweep"]["reason"])

    def test_jewel_support_contract_rejects_missing_and_colliding_jewel_geometry(self):
        design = _build_design(731)
        center_axis = _axis_by_id(design, "center_axis")
        center_axis["lower_jewel"] = None

        independent = _build_independent_geometry_report(design)

        self.assertEqual("fail", independent["jewel_supports"]["status"])
        self.assertIn("center_axis", independent["jewel_supports"]["missing_lower_jewels"])

        design = _build_design(731)
        center_axis = _axis_by_id(design, "center_axis")
        center_axis["lower_jewel"]["outer_radius"] = 9.0

        independent = _build_independent_geometry_report(design)

        self.assertEqual("fail", independent["jewel_supports"]["status"])
        self.assertTrue(independent["jewel_supports"]["interference_failures"])

    def test_declared_external_meshes_have_tip_to_root_clearance(self):
        design = _build_design(731)
        axes = {axis["axis_id"]: axis for axis in design["axes"]}
        gears = {gear["gear_id"]: gear for gear in [*design["gears"], *design["display_gears"]]}
        all_meshes = [*design["meshes"], *design["display_meshes"]]

        for mesh in all_meshes:
            driver = gears[mesh["driver"]]
            driven = gears[mesh["driven"]]
            driver_axis = axes[driver["axis_id"]]
            driven_axis = axes[driven["axis_id"]]
            center_distance = (
                (driver_axis["x"] - driven_axis["x"]) ** 2
                + (driver_axis["y"] - driven_axis["y"]) ** 2
            ) ** 0.5
            driver_tip_into_driven_root = driver["outer_radius"] + driven["root_radius"] - center_distance
            driven_tip_into_driver_root = driven["outer_radius"] + driver["root_radius"] - center_distance

            with self.subTest(mesh=(mesh["driver"], mesh["driven"])):
                self.assertLessEqual(driver_tip_into_driven_root, 0.0)
                self.assertLessEqual(driven_tip_into_driver_root, 0.0)

    def test_gear_tooth_bodies_are_bored_for_their_arbors(self):
        design = _build_design(731)

        for gear in design["gears"]:
            if gear["gear_id"] == "barrel_outer_teeth":
                continue
            with self.subTest(gear=gear["gear_id"]):
                solid_without_bore = _gear_body(dict(gear))
                solid_with_bore = _gear_tooth_body_with_bore(dict(gear))
                self.assertLess(solid_with_bore.volume, solid_without_bore.volume)
                removed_volume = solid_without_bore.volume - solid_with_bore.volume
                self.assertGreater(removed_volume, 0.5 * 3.14159 * gear["bore_radius"] ** 2 * gear["height"])

    def test_watch_wheels_use_single_body_open_spoked_cutouts(self):
        design = _build_design(947)
        wheel_gears = [
            gear
            for gear in [*design["gears"], *design["display_gears"]]
            if _should_use_watch_wheel_spoke_cutouts(gear)
        ]
        small_pinions = [
            gear
            for gear in [*design["gears"], *design["display_gears"]]
            if gear["gear_type"] == "pinion"
            and not _should_use_watch_wheel_spoke_cutouts(gear)
        ]

        self.assertGreaterEqual(len(wheel_gears), 6)
        self.assertIn("escape_wheel", {gear["gear_id"] for gear in wheel_gears})
        self.assertIn("minute_wheel", {gear["gear_id"] for gear in wheel_gears})
        self.assertIn("minute_pinion", {gear["gear_id"] for gear in wheel_gears})
        self.assertIn("hour_wheel", {gear["gear_id"] for gear in wheel_gears})
        self.assertNotIn("barrel_outer_teeth", {gear["gear_id"] for gear in wheel_gears})
        self.assertGreaterEqual(min(gear["root_radius"] * 2.0 for gear in wheel_gears), 2.0)
        self.assertIn("center_pinion", {gear["gear_id"] for gear in small_pinions})
        self.assertTrue(all("spoke_modeling_strategy" not in gear for gear in small_pinions))
        self.assertTrue(any(gear["spoke_count"] != wheel_gears[0]["spoke_count"] for gear in wheel_gears[1:]))

        for gear in wheel_gears:
            with self.subTest(gear=gear["gear_id"]):
                self.assertIn(gear["spoke_count"], [2, 3, 4, 5])
                self.assertEqual("single_body_cutout", gear["spoke_modeling_strategy"])
                self.assertGreaterEqual(gear["rim_inner_radius"] / gear["root_radius"], 0.84)
                max_hub_ratio = 0.28 if gear["gear_type"] in {"escape", "pinion"} else 0.19
                self.assertLessEqual(gear["hub_outer_radius"] / gear["root_radius"], max_hub_ratio)
                self.assertEqual(0, len(_gear_tooth_body_with_bore(dict(gear)).children))
                rendered = _make_gear(dict(gear))
                self.assertEqual(0, len(rendered.children))

    def test_hour_hand_motion_chain_rejects_source_name_only_declaration(self):
        design = _build_design(731)
        display = design["display"]
        display.pop("motion_works", None)
        display.pop("coaxial_sleeve_clearance", None)
        tubes = {tube["tube_id"]: tube for tube in display["tube_stack"]}
        tubes["hour_tube"]["inner_radius"] = 0.30
        tubes["cannon_pinion_tube"]["outer_radius"] = 0.32
        for chain in display["drive_chains"]:
            if chain["hand_id"] == "hour_hand":
                chain["path"] = ["cannon_pinion_assembly", "hour_wheel", "hour_hand"]
                chain.pop("ratio_proof", None)
                chain.pop("interface_sequence", None)

        independent = _build_independent_geometry_report(design)

        self.assertEqual("fail", independent["motion_chains"]["hour_hand"]["status"])
        self.assertIn("minute_wheel_assembly", independent["motion_chains"]["hour_hand"]["missing_nodes"])
        self.assertEqual("fail", independent["coaxial_sleeves"]["status"])

    def test_display_hand_blades_attach_to_hubs_in_generated_brep(self):
        design = _build_design(731)

        for hand in design["display"]["hands"]:
            with self.subTest(hand_id=hand["hand_id"]):
                axis = _axis_by_id(design, hand["axis_id"])
                hand_shape = _make_hand(
                    hand["hand_id"],
                    axis["x"],
                    axis["y"],
                    hand["angle_deg"],
                    hand["length_mm"],
                    hand["z_mm"],
                    hand["width_mm"],
                    hand["profile"],
                )
                children = {child.label: child for child in hand_shape.children}
                hub = children[f"{hand['hand_id']}_hub"]
                blade = children[f"{hand['hand_id']}_blade"]
                hub_box = hub.bounding_box()
                blade_box = blade.bounding_box()
                hub_center = tuple(hub_box.center())
                blade_min = tuple(blade_box.min)
                blade_max = tuple(blade_box.max)
                hub_size = tuple(hub_box.size)
                hub_outer_radius = max(hub_size[0], hub_size[1]) / 2.0
                dx = max(blade_min[0] - axis["x"], 0.0, axis["x"] - blade_max[0])
                dy = max(blade_min[1] - axis["y"], 0.0, axis["y"] - blade_max[1])
                blade_to_axis_distance = (dx**2 + dy**2) ** 0.5

                self.assertAlmostEqual(axis["x"], hub_center[0], places=4)
                self.assertAlmostEqual(axis["y"], hub_center[1], places=4)
                self.assertLessEqual(blade_to_axis_distance, hub_outer_radius + 0.02)

    def test_same_seed_repeats_layout_and_different_seed_changes_seeded_choices(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right, tempfile.TemporaryDirectory() as other:
            result_left = run_power_chain_mvp(Path(left), seed=731)
            result_right = run_power_chain_mvp(Path(right), seed=731)
            result_other = run_power_chain_mvp(Path(other), seed=124)

            semantic_left = json.loads(Path(result_left["artifacts"]["semantic_json"]).read_text(encoding="utf-8"))
            semantic_right = json.loads(Path(result_right["artifacts"]["semantic_json"]).read_text(encoding="utf-8"))
            semantic_other = json.loads(Path(result_other["artifacts"]["semantic_json"]).read_text(encoding="utf-8"))

            self.assertEqual(semantic_left["seed_manifest"], semantic_right["seed_manifest"])
            self.assertEqual(semantic_left["layout"]["axes"], semantic_right["layout"]["axes"])
            self.assertNotEqual(semantic_left["seed_manifest"], semantic_other["seed_manifest"])


if __name__ == "__main__":
    unittest.main()


