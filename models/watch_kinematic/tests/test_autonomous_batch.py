from pathlib import Path
import json
import tempfile
import unittest

from models.watch_kinematic.watch_kinematic.autonomous_batch import run_watch_design_batch


class WatchAutonomousBatchTests(unittest.TestCase):
    def test_generates_five_distinct_designs_but_blocks_production_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_watch_design_batch(Path(tmp), design_count=5)

            self.assertEqual("fail", result["status"])
            self.assertEqual(5, result["summary"]["requested_design_count"])
            self.assertEqual(5, result["summary"]["generated_design_count"])
            self.assertEqual(5, result["summary"]["distinct_fingerprint_count"])
            self.assertEqual(5, len(result["summary"]["failed_design_ids"]))
            self.assertEqual(
                {
                    "semantic_checks",
                    "interference_checks",
                    "power_chain_checks",
                    "role_contract_checks",
                    "production_geometry_checks",
                    "visual_review_checks",
                },
                set(result["summary"]["check_groups"]),
            )

            designs = result["designs"]
            self.assertEqual(5, len(designs))
            fingerprints = {design["fingerprint"] for design in designs}
            self.assertEqual(5, len(fingerprints))

            for design in designs:
                with self.subTest(design_id=design["design_id"]):
                    self.assertEqual("fail", design["status"])
                    self.assertEqual("pass", design["semantic_checks"]["status"])
                    self.assertEqual("pass", design["interference_checks"]["status"])
                    self.assertEqual("pass", design["power_chain_checks"]["status"])
                    self.assertEqual("pass", design["role_contract_checks"]["status"])
                    self.assertEqual("fail", design["production_geometry_checks"]["status"])
                    self.assertEqual("fail", design["visual_review_checks"]["status"])
                    self.assertGreaterEqual(
                        design["production_geometry_checks"]["observed_geometry_check_count"],
                        4,
                    )
                    self.assertGreaterEqual(design["semantic_checks"]["moving_axis_count"], 3)
                    self.assertGreaterEqual(design["semantic_checks"]["bridge_count"], 1)
                    self.assertNotIn(
                        "physical_z_arbor_exists_for_every_rotating_axis",
                        design["semantic_checks"]["failed_checks"],
                    )
                    self.assertEqual([], design["interference_checks"]["hard_collisions"])
                    self.assertGreaterEqual(design["power_chain_checks"]["driven_output_count"], 1)
                    self.assertIn(
                        "step_render_or_geometry_contract_review_exists",
                        design["visual_review_checks"]["failed_checks"],
                    )
                    self.assertEqual([], design["role_contract_checks"]["failed_checks"])
                    self.assertIn(
                        "bridge_2d_human_review_required",
                        design["production_geometry_checks"]["failed_checks"],
                    )
                    self.assertNotIn(
                        "bridge_geometry_is_featured_plate_not_rectangular_bar",
                        design["production_geometry_checks"]["failed_checks"],
                    )
                    self.assertNotIn(
                        "output_hand_geometry_is_featured_hand_not_rectangular_bar",
                        design["production_geometry_checks"]["failed_checks"],
                    )

                    for artifact_name in [
                        "step",
                        "semantic_json",
                        "interference_json",
                        "kinematic_json",
                        "role_contract_json",
                        "production_geometry_json",
                        "visual_review_json",
                        "dashboard_html",
                        "bridge_2d_review_html",
                    ]:
                        path = Path(design["artifacts"][artifact_name])
                        self.assertTrue(path.exists(), f"{artifact_name} missing for {design['design_id']}")
                        self.assertGreater(path.stat().st_size, 0, f"{artifact_name} is empty for {design['design_id']}")

                    bridge_2d_review = Path(design["artifacts"]["bridge_2d_review_html"]).read_text(encoding="utf-8")
                    self.assertIn("二维桥板方案审查", bridge_2d_review)
                    self.assertIn("当前 3D 桥板禁止验收", bridge_2d_review)
                    self.assertIn("长直梁穿越齿轮投影", bridge_2d_review)
                    self.assertIn("<svg", bridge_2d_review)

                    step_text = Path(design["artifacts"]["step"]).read_text(encoding="utf-8", errors="ignore")
                    self.assertNotIn("mainplate_cutout_axis_", step_text)
                    self.assertIn("gear_hub_", step_text)
                    self.assertIn("cycloidal_tooth_profile_", step_text)
                    for forbidden_parent_feature_product in [
                        "gear_spoke_",
                        "bridge_clearance_hole_",
                        "mainplate_threaded_receiver_",
                        "bridge_screw_slot_",
                    ]:
                        self.assertNotIn(
                            forbidden_parent_feature_product,
                            step_text,
                            f"{forbidden_parent_feature_product} must be an integrated feature, not a STEP product",
                        )
                    self.assertNotIn("bridge_bar_", step_text)
                    self.assertIn("train_bridge_plate_", step_text)
                    self.assertIn("bridge_screw_head_", step_text)
                    self.assertIn("output_hand_hub_", step_text)
                    self.assertIn("output_hand_blade_", step_text)
                    self.assertFalse(
                        "drive_spiral_visual_stack" in step_text,
                        "visual-only spiral stacks must not ship in engineering STEP without a role contract",
                    )
                    self.assertFalse(
                        "drive_spiral_ring_" in step_text,
                        "visual-only spiral rings must not appear as free engineering products",
                    )

                    role_contract_report = json.loads(
                        Path(design["artifacts"]["role_contract_json"]).read_text(encoding="utf-8")
                    )
                    self.assertEqual("watch_kinematic_role_contract_report", role_contract_report["kind"])
                    self.assertEqual("pass", role_contract_report["status"])
                    self.assertGreaterEqual(role_contract_report["summary"]["engineering_contract_count"], 6)
                    self.assertEqual([], role_contract_report["summary"]["missing_contract_occurrences"])
                    required_contract_keys = {
                        "contract_id",
                        "occurrence_id",
                        "role",
                        "parent_function",
                        "function_claims",
                        "behavior_claims",
                        "required_interfaces",
                        "required_features",
                        "evidence_requirements",
                        "blockers",
                        "validation",
                    }
                    for contract in role_contract_report["contracts"]:
                        with self.subTest(contract_id=contract["contract_id"]):
                            self.assertTrue(required_contract_keys.issubset(contract))
                    arbor_contracts = [
                        contract
                        for contract in role_contract_report["contracts"]
                        if contract["role"] == "rotating_arbor"
                    ]
                    self.assertGreaterEqual(len(arbor_contracts), 3)
                    for contract in arbor_contracts:
                        with self.subTest(arbor_contract_id=contract["contract_id"]):
                            self.assertEqual("pass", contract["validation"]["status"])
                            self.assertEqual([], contract["validation"]["missing_evidence"])
                    train_gear_contracts = [
                        contract
                        for contract in role_contract_report["contracts"]
                        if contract["role"] == "train_gear"
                    ]
                    self.assertGreaterEqual(len(train_gear_contracts), 3)
                    for contract in train_gear_contracts:
                        with self.subTest(train_gear_contract_id=contract["contract_id"]):
                            self.assertEqual("pass", contract["validation"]["status"])
                            self.assertEqual([], contract["validation"]["missing_evidence"])
                    for role in ["foundation_plate", "upper_support_bridge", "bridge_fastener"]:
                        role_contracts = [
                            contract
                            for contract in role_contract_report["contracts"]
                            if contract["role"] == role
                        ]
                        self.assertGreaterEqual(len(role_contracts), 1)
                        for contract in role_contracts:
                            with self.subTest(contract_id=contract["contract_id"]):
                                self.assertEqual("pass", contract["validation"]["status"])
                                self.assertEqual([], contract["validation"]["missing_evidence"])
                                if role == "upper_support_bridge":
                                    self.assertIn("route_planned_bridge_footprint", contract["required_features"])
                                    self.assertIn("bridge_6dof_constraint_chain", contract["required_features"])
                                    self.assertIn(
                                        "bridge footprint is planned in XY before 3D extrusion",
                                        contract["behavior_claims"],
                                    )
                                    self.assertIn(
                                        "declares a 6DoF fixed constraint chain through bridge fasteners",
                                        contract["behavior_claims"],
                                    )
                    output_hand_contracts = [
                        contract
                        for contract in role_contract_report["contracts"]
                        if contract["role"] == "output_display_hand"
                    ]
                    self.assertGreaterEqual(len(output_hand_contracts), 1)
                    for contract in output_hand_contracts:
                        with self.subTest(contract_id=contract["contract_id"]):
                            self.assertEqual("pass", contract["validation"]["status"])
                            self.assertEqual([], contract["validation"]["missing_evidence"])
                    failed_evidence = [
                        contract
                        for contract in role_contract_report["contracts"]
                        if contract["validation"]["status"] == "fail"
                    ]
                    self.assertEqual([], failed_evidence)

                    production_report = json.loads(
                        Path(design["artifacts"]["production_geometry_json"]).read_text(encoding="utf-8")
                    )
                    self.assertEqual("watch_kinematic_production_geometry_report", production_report["kind"])
                    self.assertEqual("fail", production_report["status"])
                    self.assertTrue(production_report["checks"]["wheel_central_openings_within_contract"])
                    self.assertTrue(production_report["checks"]["parent_body_features_not_exported_as_standalone_products"])
                    self.assertTrue(production_report["checks"]["geometry_evidence_has_observation_source"])
                    self.assertTrue(production_report["checks"]["assembly_z_contact_stack_has_no_unresolved_gaps"])
                    self.assertTrue(production_report["checks"]["uncontracted_visual_placeholders_not_exported"])
                    self.assertTrue(production_report["checks"]["output_display_hands_have_closed_mounting_stack"])
                    self.assertTrue(production_report["checks"]["bridge_fastener_paths_clear_moving_envelopes"])
                    self.assertTrue(production_report["checks"]["fixed_geometry_clears_moving_envelopes"])
                    self.assertTrue(production_report["checks"]["visible_foundation_parts_have_closed_contact_chain"])
                    self.assertTrue(production_report["checks"]["output_display_hand_components_attach_to_hub"])
                    self.assertIn("upper_support_bridges_have_2d_route_plan", production_report["checks"])
                    self.assertIn(
                        "upper_support_bridge_footprints_limit_soft_gear_overlap",
                        production_report["checks"],
                    )
                    self.assertIn(
                        "upper_support_bridge_centerlines_use_allowed_corridors",
                        production_report["checks"],
                    )
                    self.assertTrue(production_report["checks"]["upper_support_bridges_have_2d_route_plan"])
                    self.assertTrue(
                        production_report["checks"]["upper_support_bridge_footprints_limit_soft_gear_overlap"]
                    )
                    self.assertTrue(
                        production_report["checks"]["upper_support_bridge_centerlines_use_allowed_corridors"]
                    )
                    self.assertTrue(production_report["checks"]["upper_support_bridges_have_declared_6dof_constraint_chain"])
                    self.assertFalse(production_report["checks"]["bridge_2d_human_review_required"])
                    self.assertEqual([], production_report["failures"]["oversized_wheel_openings"])
                    self.assertEqual([], production_report["failures"]["standalone_parent_body_feature_products"])
                    self.assertEqual([], production_report["failures"]["unobserved_geometry_evidence"])
                    self.assertEqual([], production_report["failures"]["z_contact_stack_gaps"])
                    self.assertEqual([], production_report["failures"]["uncontracted_visual_products"])
                    self.assertEqual([], production_report["failures"]["output_display_mount_stack_gaps"])
                    self.assertEqual([], production_report["failures"]["bridge_fastener_motion_envelope_intrusions"])
                    self.assertEqual([], production_report["failures"]["fixed_motion_envelope_intrusions"])
                    self.assertEqual([], production_report["failures"]["foundation_contact_chain_gaps"])
                    self.assertEqual([], production_report["failures"]["output_hand_component_attachment_gaps"])
                    self.assertEqual([], production_report["failures"]["bridge_route_plan_failures"])
                    self.assertEqual([], production_report["failures"]["bridge_constraint_chain_failures"])
                    self.assertGreaterEqual(len(production_report["failures"]["bridge_2d_human_review_required"]), 1)
                    self.assertIn("bridge_2d_route_plans", production_report["observations"])
                    self.assertGreaterEqual(len(production_report["observations"]["bridge_2d_route_plans"]), 1)
                    for observation in production_report["observations"]["bridge_2d_route_plans"]:
                        with self.subTest(bridge_route_plan_id=observation["bridge_id"]):
                            self.assertGreaterEqual(observation["required_node_count"], 3)
                            self.assertGreaterEqual(observation["segment_count"], 1)
                            self.assertTrue(observation["single_continuous_footprint"])
                            self.assertLessEqual(observation["max_soft_gear_overlap_ratio"], 0.34)
                            self.assertEqual([], observation["hard_forbidden_intrusions"])

                    validation_report = json.loads(
                        Path(design["artifacts"]["validation_json"]).read_text(encoding="utf-8")
                    )
                    self.assertEqual("fail", validation_report["status"])
                    self.assertNotIn("semantic_checks", validation_report["hard_failures"])
                    self.assertNotIn("role_contract_checks", validation_report["hard_failures"])
                    self.assertIn("production_geometry_checks", validation_report["hard_failures"])
                    self.assertIn("visual_review_checks", validation_report["hard_failures"])

    def test_batch_manifest_is_human_reviewable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_watch_design_batch(Path(tmp), design_count=5)
            manifest_path = Path(result["artifacts"]["batch_manifest"])
            review_path = Path(result["artifacts"]["batch_review_html"])
            contact_sheet_path = Path(result["artifacts"]["batch_visual_contact_sheet"])

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            review_html = review_path.read_text(encoding="utf-8")

            self.assertEqual("watch_kinematic_autonomous_batch", manifest["kind"])
            self.assertEqual("fail", manifest["status"])
            self.assertEqual(5, len(manifest["designs"]))
            self.assertIn("连续 5 个不同手表机械设计", review_html)
            self.assertIn("语义检查", review_html)
            self.assertIn("干涉检查", review_html)
            self.assertIn("动力链检查", review_html)
            self.assertIn("目视检查", review_html)
            self.assertIn(".step", review_html)
            self.assertTrue(contact_sheet_path.exists())
            self.assertGreater(contact_sheet_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
