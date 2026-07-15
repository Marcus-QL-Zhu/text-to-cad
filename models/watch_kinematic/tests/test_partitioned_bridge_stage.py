import tempfile
import unittest
import json
import math
import numpy as np
from contextlib import contextmanager
from types import SimpleNamespace
from matplotlib.path import Path as MplPath
from pathlib import Path

from models.watch_kinematic.watch_kinematic import partitioned_bridge_stage as bridge_stage_module
from models.watch_kinematic.watch_kinematic.partitioned_bridge_stage import (
    build_analytic_bridge_stage_plan,
    build_independent_display_bridge_stage_plan,
    build_independent_display_partitioned_bridge_stage,
    build_pattern3_independent_display_complete_model,
    build_separate_display_bridge_stage_plan,
    build_separate_display_partitioned_bridge_stage,
    _build_base_without_old_bridges,
    _flat_step_feature_refs_for_color_sync,
    _flatten_for_step_color_sync,
    _make_analytic_bridge_stage,
    _extrude_smooth_bridge_boundary,
    _polygon_distance,
    _sync_bridge_translucency_motion_from_glb_json,
)
from models.watch_kinematic.watch_kinematic import power_chain_mvp as p
from models.watch_kinematic.watch_kinematic.power_chain_mvp import _build_design
from models.watch_kinematic.watch_kinematic.pattern_cards.separate_hour_minute_no_seconds import (
    solve_separate_display_layout,
)
from models.watch_kinematic.watch_kinematic.pattern_cards.independent_hour_minute_no_seconds import (
    PATTERN_CARD_ID as INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
    solve_independent_display_layout,
)
class PartitionedBridgeStageTests(unittest.TestCase):
    def test_smooth_bridge_boundary_builds_valid_nonzero_solid(self):
        points = [
            (10.0, 0.0),
            (8.7, 5.0),
            (5.0, 8.7),
            (0.0, 10.0),
            (-5.0, 8.7),
            (-8.7, 5.0),
            (-10.0, 0.0),
            (-8.7, -5.0),
            (-5.0, -8.7),
            (0.0, -10.0),
            (5.0, -8.7),
            (8.7, -5.0),
        ]

        solid = _extrude_smooth_bridge_boundary(points, 1.2)

        self.assertGreater(float(getattr(solid, "volume", 0.0)), 1e-6)

    def test_independent_display_bridge_service_spans_do_not_overlap_between_bridges(self):
        solver_report = solve_independent_display_layout(seed=731)
        design = p._build_independent_display_design(731, solver_report)

        plan = build_independent_display_bridge_stage_plan(design, layout_id="seed_731_independent_service_span_test")
        repeated_plan = build_independent_display_bridge_stage_plan(
            design,
            layout_id="seed_731_independent_service_span_test",
        )

        bridges = plan["bridges"]
        self.assertEqual(
            [bridge["support_pads"] for bridge in bridges],
            [bridge["support_pads"] for bridge in repeated_plan["bridges"]],
        )
        for bridge in bridges:
            for pad in bridge["support_pads"]:
                self.assertTrue(
                    any(
                        _span_inside(pad["angular_start_deg"], pad["angular_end_deg"], span)
                        for span in bridge["outer_service_spans"]
                    )
                )
        for left_index, left in enumerate(bridges):
            for right in bridges[left_index + 1 :]:
                for left_span in left["outer_service_spans"]:
                    for right_span in right["outer_service_spans"]:
                        with self.subTest(left=left["bridge_id"], right=right["bridge_id"]):
                            self.assertAlmostEqual(
                                0.0,
                                _span_overlap_deg(left_span, right_span),
                                places=4,
                            )
        train = next(bridge for bridge in bridges if bridge["bridge_id"] == "train_bridge")
        self.assertGreaterEqual(len(train["outer_service_spans"]), 2)

    def test_independent_display_partitioned_bridge_stage_generates_complete_lightened_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_independent_display_partitioned_bridge_stage(
                Path(tmp),
                seed=731,
                include_lightening=True,
            )

            self.assertEqual("pass", result["status"])
            self.assertEqual(INDEPENDENT_DISPLAY_PATTERN_CARD_ID, result["pattern_card_id"])
            self.assertTrue(result["lightening_enabled"])
            step_path = Path(result["artifacts"]["step"])
            self.assertTrue(step_path.exists())
            self.assertGreater(step_path.stat().st_size, 0)

            step_text = step_path.read_text(encoding="utf-8", errors="ignore")
            required_labels = [
                "minute_input_relay_pinion",
                "minute_input_relay_wheel",
                "minute_display_member",
                "hour_input_relay_pinion",
                "hour_input_relay_wheel",
                "hour_reduction_relay_pinion",
                "hour_reduction_relay_wheel",
                "hour_display_member",
                "minute_hand",
                "hour_hand",
                "barrel_bridge",
                "train_bridge",
                "escapement_bridge",
            ]
            for label in required_labels:
                with self.subTest(label=label):
                    self.assertIn(label, step_text)
            self.assertNotIn("seconds_hand", step_text)

            report = json.loads(Path(result["artifacts"]["report_json"]).read_text(encoding="utf-8"))
            self.assertEqual("pass", report["validation"]["status"])
            self.assertEqual("pass", report["validation"]["checks"]["hour_branch_independent_from_minute_branch"])
            self.assertEqual("pass", report["validation"]["checks"]["independent_display_motion_groups_declared"])
            self.assertEqual("pass", report["validation"]["checks"]["external_escapement_assembly_present"])
            self.assertEqual("pass", report["bridge_stage"]["status"])
            self.assertEqual(
                ["barrel_bridge", "escapement_bridge", "train_bridge"],
                sorted(bridge["bridge_id"] for bridge in report["bridge_stage"]["bridges"]),
            )

    def test_pattern3_complete_model_generates_only_after_hard_validation_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _patched_pattern3_fast_cad_pipeline():
                result = build_pattern3_independent_display_complete_model(
                    Path(tmp),
                    seed=731,
                    include_lightening=False,
                )

            self.assertEqual("pass", result["status"])
            self.assertEqual(INDEPENDENT_DISPLAY_PATTERN_CARD_ID, result["pattern_card_id"])
            self.assertTrue(result["generation_gate"]["allowed_to_open_or_deliver"])
            self.assertEqual([], result["generation_gate"]["failed_checks"])
            step_path = Path(result["artifacts"]["step"])
            self.assertTrue(step_path.exists())
            self.assertGreater(step_path.stat().st_size, 0)
            report = json.loads(Path(result["artifacts"]["report_json"]).read_text(encoding="utf-8"))
            self.assertEqual("pass", report["validation"]["status"])
            self.assertEqual(
                "pass",
                report["validation"]["checks"][
                    "pattern_card_id_is_watch_pattern_03_independent_hour_minute_no_seconds_v1"
                ],
            )
            evidence = report["evidence"]
            builders = {
                "solver": "solve_independent_display_layout",
                "semantic": "_build_independent_display_semantic_report",
                "role_contracts": "_build_independent_display_role_contract_report",
                "kinematic": "_build_independent_display_kinematic_report",
            }
            for name, builder in builders.items():
                with self.subTest(evidence=name):
                    self.assertIn(name, evidence)
                    self.assertEqual(
                        INDEPENDENT_DISPLAY_PATTERN_CARD_ID,
                        evidence[name]["source"]["complete_entrypoint_pattern_card_id"],
                    )
                    payload_pattern_card_id = evidence[name]["payload"].get("pattern_card_id")
                    if payload_pattern_card_id is None:
                        self.assertNotIn("payload_pattern_card_id", evidence[name]["source"])
                    else:
                        self.assertEqual(payload_pattern_card_id, evidence[name]["source"]["payload_pattern_card_id"])
                    self.assertEqual(731, evidence[name]["source"]["generation_seed"])
                    self.assertEqual(builder, evidence[name]["source"]["builder"])
            self.assertEqual(731, evidence["solver"]["payload"]["seed"])
            self.assertEqual("pass", evidence["semantic"]["payload"]["status"])
            self.assertEqual(
                "pass",
                evidence["semantic"]["payload"]["checks"][
                    "pattern_card_id_is_watch_pattern_03_independent_hour_minute_no_seconds_v1"
                ],
            )

    def test_pattern3_semantic_evidence_is_retargeted_to_its_own_pattern_card(self):
        semantic = {
            "pattern_card_id": "watch_pattern_03_independent_hour_minute_no_seconds_v1",
            "status": "fail",
            "checks": {
                "pattern_card_id_is_watch_pattern_03_independent_hour_minute_no_seconds_v1": "fail",
                "separate_minute_and_hour_axes": "pass",
            },
        }

        retargeted = bridge_stage_module._retarget_independent_display_semantic_for_pattern3(
            semantic,
            pattern_card_id="watch_pattern_03_independent_hour_minute_no_seconds_v1",
            selected_candidate={"pattern_card_id": "watch_pattern_03_independent_hour_minute_no_seconds_v1"},
        )

        self.assertEqual("pass", retargeted["status"])
        self.assertEqual("watch_pattern_03_independent_hour_minute_no_seconds_v1", retargeted["pattern_card_id"])
        self.assertEqual(
            "pass",
            retargeted["checks"]["pattern_card_id_is_watch_pattern_03_independent_hour_minute_no_seconds_v1"],
        )

    def test_pattern3_complete_model_defaults_to_lightened_bridges(self):
        with tempfile.TemporaryDirectory() as tmp:
            with _patched_pattern3_fast_cad_pipeline():
                result = build_pattern3_independent_display_complete_model(
                    Path(tmp),
                    seed=731,
                )

            self.assertEqual("pass", result["status"])
            self.assertTrue(result["lightening_enabled"])
            for bridge in result["bridge_stage"]["bridges"]:
                with self.subTest(bridge=bridge["bridge_id"]):
                    self.assertEqual("pass", bridge["lightening"]["status"])
                    self.assertGreater(len(bridge["lightening"]["manufacturing_windows"]), 0)
                    for window in bridge["lightening"]["manufacturing_windows"]:
                        self.assertEqual("smooth_vector_curve", window.get("cad_boundary_kind"))
                        self.assertLessEqual(
                            _max_loop_segment_length(window["points"]),
                            0.9,
                            f"{bridge['bridge_id']} {window['window_id']} is too sparsely sampled and will render as a faceted lightening cutout",
                        )

    def test_pattern3_complete_model_stops_without_step_when_hard_validation_fails(self):
        original_validator = p._build_independent_display_validation_report

        def forced_failure(design, semantic, motion=None):
            validation = original_validator(design, semantic, motion)
            validation["status"] = "fail"
            validation["checks"]["forced_hard_gate_failure"] = "fail"
            validation["failed_checks"] = [*validation.get("failed_checks", []), "forced_hard_gate_failure"]
            return validation

        with tempfile.TemporaryDirectory() as tmp:
            original = p._build_independent_display_validation_report
            try:
                p._build_independent_display_validation_report = forced_failure
                with _patched_pattern3_fast_cad_pipeline(patch_validation=False):
                    result = build_pattern3_independent_display_complete_model(
                        Path(tmp),
                        seed=731,
                        include_lightening=False,
                    )
            finally:
                p._build_independent_display_validation_report = original

            self.assertEqual("fail", result["status"])
            self.assertFalse(result["generation_gate"]["allowed_to_open_or_deliver"])
            self.assertIn("forced_hard_gate_failure", result["generation_gate"]["failed_checks"])
            self.assertFalse(Path(result["artifacts"]["step"]).exists())
            self.assertTrue(Path(result["artifacts"]["report_json"]).exists())
            self.assertNotIn("evidence", result)

    def test_separate_display_partitioned_bridge_stage_generates_width_seams_and_lightening(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_separate_display_partitioned_bridge_stage(
                Path(tmp),
                seed=8459,
                include_lightening=True,
            )

            self.assertEqual("pass", result["status"])
            self.assertEqual("separate_hour_minute_no_seconds_v1", result["pattern_card_id"])
            self.assertTrue(result["lightening_enabled"])
            step_path = Path(result["artifacts"]["step"])
            self.assertTrue(step_path.exists())
            step_text = step_path.read_text(encoding="utf-8", errors="ignore")
            for label in ["barrel_bridge", "train_bridge", "escapement_bridge"]:
                with self.subTest(step_label=label):
                    self.assertIn(label, step_text)

            stage = result["bridge_stage"]
            self.assertEqual("pass", stage["status"])
            self.assertEqual("axis_voronoi_native_smooth_with_explicit_width", stage["seam_policy"]["kind"])
            self.assertGreaterEqual(stage["seam_policy"]["gap_width_mm"], p.BRIDGE_SEAM_GAP_WIDTH_MM)
            self.assertFalse(stage["grid_contour_used_for_cad"])
            self.assertEqual(
                ["barrel_bridge", "escapement_bridge", "train_bridge"],
                sorted(bridge["bridge_id"] for bridge in stage["bridges"]),
            )
            window_count = 0
            for bridge in stage["bridges"]:
                with self.subTest(bridge=bridge["bridge_id"]):
                    self.assertEqual("analytic_axis_voronoi_footprint", bridge["footprint_type"])
                    self.assertEqual("pass", bridge["edge_quality_status"])
                    self.assertGreaterEqual(bridge["seam_gap_width_mm"], p.BRIDGE_SEAM_GAP_WIDTH_MM)
                    self.assertIn("lightening", bridge)
                    window_count += len(bridge["lightening"]["manufacturing_windows"])
            self.assertGreater(window_count, 0)

    def test_separate_display_support_pads_use_full_outer_service_domain_and_edge_screws(self):
        solver_report = solve_separate_display_layout(seed=8459)
        design = p._build_separate_display_design(8459, solver_report)

        plan = build_separate_display_bridge_stage_plan(design, layout_id="seed_8459_partition_test")

        edge_margin = math.degrees(
            (p.BRIDGE_SUPPORT_PAD_ARC_LENGTH_TO_HEAD_DIAMETER_RATIO * p.BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM / 2.0)
            / p.BRIDGE_SCREW_PITCH_RADIUS_MM
        )
        for bridge in plan["bridges"]:
            with self.subTest(bridge=bridge["bridge_id"]):
                domain = bridge["outer_service_domain"]
                self.assertEqual([domain], bridge["outer_service_spans"])
                span = _positive_span(domain["angular_start_deg"], domain["angular_end_deg"])
                expected_count = 1 if span < 40.0 else 3 if span > 90.0 else 2
                self.assertEqual(expected_count, len(bridge["screws"]))
                self.assertEqual(expected_count, len(bridge["support_pads"]))
                self.assertEqual(
                    [screw["screw_id"] for screw in bridge["screws"]],
                    [pad["screw_id"] for pad in bridge["support_pads"]],
                )
                self.assertEqual(len(bridge["support_pads"]), len({pad["pad_id"] for pad in bridge["support_pads"]}))
                if expected_count == 1:
                    pad = bridge["support_pads"][0]
                    self.assertAlmostEqual(domain["angular_start_deg"], pad["angular_start_deg"], places=4)
                    self.assertAlmostEqual(domain["angular_end_deg"], pad["angular_end_deg"], places=4)
                else:
                    first_offset = _positive_span(domain["angular_start_deg"], bridge["screws"][0]["angle_deg"])
                    last_offset = _positive_span(bridge["screws"][-1]["angle_deg"], domain["angular_end_deg"])
                    self.assertLessEqual(first_offset, edge_margin + 0.5)
                    self.assertLessEqual(last_offset, edge_margin + 0.5)
                    self.assertEqual("start_edge", bridge["support_pads"][0]["pad_position"])
                    self.assertEqual("end_edge", bridge["support_pads"][-1]["pad_position"])

    def test_separate_display_edge_screws_anchor_to_final_visible_bridge_outer_edges(self):
        solver_report = solve_separate_display_layout(seed=45833)
        design = p._build_separate_display_design(45833, solver_report)

        plan = build_separate_display_bridge_stage_plan(design, layout_id="seed_45833_visible_edge_screw_test")

        for bridge in plan["bridges"]:
            if len(bridge["screws"]) < 2:
                continue
            for span in bridge["outer_service_spans"]:
                span_screws = [
                    screw
                    for screw in bridge["screws"]
                    if _angle_inside(screw["angle_deg"], span["angular_start_deg"], span["angular_end_deg"])
                ]
                if len(span_screws) < 2:
                    continue
                with self.subTest(bridge=bridge["bridge_id"], span=span):
                    first_offset = _positive_span(span["angular_start_deg"], span_screws[0]["angle_deg"])
                    last_offset = _positive_span(span_screws[-1]["angle_deg"], span["angular_end_deg"])
                    span_pads = [
                        pad
                        for pad in bridge["support_pads"]
                        if _span_inside(pad["angular_start_deg"], pad["angular_end_deg"], span)
                    ]
                    self.assertLessEqual(
                        first_offset,
                        span_pads[0]["target_angular_span_deg"] + 1.0,
                        f"{bridge['bridge_id']} first screw is not anchored near the visible bridge service edge",
                    )
                    self.assertLessEqual(
                        last_offset,
                        span_pads[-1]["target_angular_span_deg"] + 1.0,
                        f"{bridge['bridge_id']} last screw is not anchored near the visible bridge service edge",
                    )

    def test_separate_display_bridge_outer_edges_extend_to_case_arc_without_grid_patch(self):
        solver_report = solve_separate_display_layout(seed=8459)
        design = p._build_separate_display_design(8459, solver_report)

        plan = build_separate_display_bridge_stage_plan(design, layout_id="seed_8459_partition_test")

        for bridge in plan["bridges"]:
            with self.subTest(bridge=bridge["bridge_id"]):
                footprint = bridge["footprint"]
                self.assertEqual("pass", footprint.get("outer_edge_refit_status"))
                self.assertNotIn("grid_contour", footprint.get("source", ""))
                radii = [math.hypot(point[0], point[1]) for point in footprint["points"]]
                self.assertGreaterEqual(max(radii), p.CASE_RADIUS_MM - 0.08)

    def test_separate_display_bridge_outer_service_islands_do_not_fill_the_whole_outer_arc(self):
        solver_report = solve_separate_display_layout(seed=8459)
        design = p._build_separate_display_design(8459, solver_report)

        plan = build_separate_display_bridge_stage_plan(design, layout_id="seed_8459_partition_test")

        for bridge in plan["bridges"]:
            with self.subTest(bridge=bridge["bridge_id"]):
                footprint = bridge["footprint"]
                component_types = [component["component_type"] for component in footprint.get("components", [])]
                self.assertNotIn("case_arc_outer_service_refit_patch", component_types)
                self.assertEqual("seam_extended_to_case_arc_with_local_service_islands", footprint["outer_service_strategy"])
                domain_span = _positive_span(
                    bridge["outer_service_domain"]["angular_start_deg"],
                    bridge["outer_service_domain"]["angular_end_deg"],
                )
                pad_spans = [
                    _positive_span(pad["angular_start_deg"], pad["angular_end_deg"])
                    for pad in bridge["support_pads"]
                ]
                self.assertGreater(len(pad_spans), 0)
                if len(pad_spans) > 1:
                    self.assertLess(sum(pad_spans), domain_span * 0.75)
                    self.assertGreater(domain_span - sum(pad_spans), 8.0)

    def test_separate_display_bridge_footprints_have_real_width_seams(self):
        solver_report = solve_separate_display_layout(seed=8459)
        design = p._build_separate_display_design(8459, solver_report)

        plan = build_separate_display_bridge_stage_plan(design, layout_id="seed_8459_real_width_seam_test")
        bridges = {bridge["bridge_id"]: bridge for bridge in plan["bridges"]}

        for left_id, right_id in [("barrel_bridge", "train_bridge"), ("train_bridge", "escapement_bridge")]:
            with self.subTest(pair=(left_id, right_id)):
                observed = _minimum_component_distance(bridges[left_id], bridges[right_id])
                self.assertGreaterEqual(
                    observed,
                    p.BRIDGE_SEAM_GAP_WIDTH_MM - 0.05,
                    f"{left_id}/{right_id} geometry still shares an edge instead of a real seam",
                )

    def test_separate_display_bridge_footprints_are_closed_from_smooth_seams_not_label_masks(self):
        solver_report = solve_separate_display_layout(seed=8459)
        design = p._build_separate_display_design(8459, solver_report)

        plan = build_separate_display_bridge_stage_plan(design, layout_id="seed_8459_smooth_seam_boundary_test")

        for bridge in plan["bridges"]:
            with self.subTest(bridge=bridge["bridge_id"]):
                footprint = bridge["footprint"]
                self.assertEqual("native_smooth_seam_curves_closed_by_case_arcs", footprint["source"])
                self.assertNotIn("locked_bearing_capsules", json.dumps(footprint))
                self.assertNotIn("grid_label", json.dumps(footprint))
                self.assertGreaterEqual(len(footprint["points"]), 48)
                self.assertGreaterEqual(max(math.hypot(point[0], point[1]) for point in footprint["points"]), p.CASE_RADIUS_MM - 0.08)

    def test_separate_display_bridge_footprints_cover_upper_bearing_keepouts_without_posthoc_lobes(self):
        solver_report = solve_separate_display_layout(seed=8459)
        design = p._build_separate_display_design(8459, solver_report)

        plan = build_separate_display_bridge_stage_plan(design, layout_id="seed_8459_bearing_coverage_test")

        for bridge in plan["bridges"]:
            component_types = [component.get("component_type", "") for component in bridge["footprint"].get("components", [])]
            self.assertFalse(
                any("lobe" in component_type or "posthoc" in component_type for component_type in component_types),
                f"{bridge['bridge_id']} must not repair bearing coverage by adding post-hoc lobes: {component_types}",
            )
            for hole in bridge["clearance_holes"]:
                sample_radius = float(hole["radius_mm"]) + 0.08
                for sample in _sample_circle_points(float(hole["x"]), float(hole["y"]), sample_radius, count=16):
                    with self.subTest(bridge=bridge["bridge_id"], axis=hole["axis_id"], sample=sample):
                        self.assertTrue(
                            _effective_bridge_contains_point(bridge, sample),
                            f"{bridge['bridge_id']} final footprint does not cover upper bearing keepout for {hole['axis_id']}",
                        )

    def test_separate_display_train_bridge_uses_smooth_cad_boundary_not_polyline_facets(self):
        solver_report = solve_separate_display_layout(seed=8459)
        design = p._build_separate_display_design(8459, solver_report)
        design["bridge_stage"] = build_separate_display_bridge_stage_plan(design, layout_id="seed_8459_smooth_cad_boundary_test")
        design["bridges_generated"] = True

        children = _make_analytic_bridge_stage(design)
        train_bridge = next(child for child in children if getattr(child, "label", "") == "train_bridge")

        self.assertLessEqual(
            len(train_bridge.edges()),
            700,
            "train_bridge CAD boundary is still a high-edge polyline instead of a smooth curve BREP",
        )

    def test_separate_display_lightened_train_bridge_uses_smooth_window_boundaries(self):
        from models.watch_kinematic.watch_kinematic.bridge_lightening import solve_bridge_lightening_plan

        solver_report = solve_separate_display_layout(seed=8459)
        design = p._build_separate_display_design(8459, solver_report)
        bridge_stage = build_separate_display_bridge_stage_plan(design, layout_id="seed_8459_smooth_window_boundary_test")
        lightening = solve_bridge_lightening_plan(
            design,
            layout_id="seed_8459_smooth_window_boundary_test_lightening",
            bridge_stage=bridge_stage,
        )
        lightening_by_id = {bridge["bridge_id"]: bridge for bridge in lightening["bridges"]}
        train_lightening = lightening_by_id["train_bridge"]
        self.assertGreaterEqual(len(train_lightening["manufacturing_windows"]), 1)
        for window in train_lightening["manufacturing_windows"]:
            with self.subTest(window=window["window_id"]):
                self.assertEqual(
                    "smooth_vector_curve",
                    window.get("cad_boundary_kind"),
                    f"{window['window_id']} must be promoted from grid contour to a smooth CAD vector curve",
                )
                self.assertGreaterEqual(
                    window.get("minimum_corner_angle_deg", 0.0),
                    65.0,
                    f"{window['window_id']} remains visually faceted after vectorization",
                )
                self.assertLessEqual(
                    window.get("vectorized_point_count", 999),
                    128,
                    f"{window['window_id']} is too dense to be a stable smooth CAD cutter",
                )
                self.assertNotIn(
                    "fallback",
                    window["source"],
                    f"{window['window_id']} is still using a fallback grid/polyline contour",
                )
        for bridge in bridge_stage["bridges"]:
            bridge["lightening"] = {
                "status": lightening_by_id[bridge["bridge_id"]]["status"],
                "manufacturing_windows": lightening_by_id[bridge["bridge_id"]]["manufacturing_windows"],
                "policy": lightening["policy"],
            }
        design["bridge_stage"] = bridge_stage
        design["bridges_generated"] = True

        children = _make_analytic_bridge_stage(design)
        train_bridge = next(child for child in children if getattr(child, "label", "") == "train_bridge")

        self.assertLessEqual(
            len(train_bridge.edges()),
            420,
            "train_bridge lightening windows generated an unexpectedly dense cutter boundary",
        )

    def test_separate_display_smooth_bridge_boundaries_do_not_overshoot_case_radius(self):
        solver_report = solve_separate_display_layout(seed=8459)
        design = p._build_separate_display_design(8459, solver_report)
        design["bridge_stage"] = build_separate_display_bridge_stage_plan(design, layout_id="seed_8459_smooth_boundary_radius_test")
        design["bridges_generated"] = True

        bridge_children = [
            child
            for child in _make_analytic_bridge_stage(design)
            if getattr(child, "label", "") in {"barrel_bridge", "train_bridge", "escapement_bridge"}
        ]

        for child in bridge_children:
            bbox = child.bounding_box()
            with self.subTest(bridge=getattr(child, "label", "")):
                self.assertGreaterEqual(bbox.min.X, -p.CASE_RADIUS_MM - 0.01)
                self.assertGreaterEqual(bbox.min.Y, -p.CASE_RADIUS_MM - 0.01)
                self.assertLessEqual(bbox.max.X, p.CASE_RADIUS_MM + 0.01)
                self.assertLessEqual(bbox.max.Y, p.CASE_RADIUS_MM + 0.01)

    def test_separate_display_lightening_windows_do_not_intrude_upper_bearing_keepouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_separate_display_partitioned_bridge_stage(
                Path(tmp),
                seed=8459,
                include_lightening=True,
            )

            for bridge in result["bridge_stage"]["bridges"]:
                window_paths = [
                    MplPath(np.array(window["points"], dtype=float))
                    for window in bridge.get("lightening", {}).get("manufacturing_windows", [])
                    if len(window.get("points", [])) >= 3
                ]
                for hole in bridge["clearance_holes"]:
                    sample_radius = float(hole["radius_mm"]) + 0.12
                    for sample in _sample_circle_points(float(hole["x"]), float(hole["y"]), sample_radius, count=20):
                        with self.subTest(bridge=bridge["bridge_id"], axis=hole["axis_id"], sample=sample):
                            self.assertFalse(
                                any(path.contains_point(sample, radius=1e-6) for path in window_paths),
                                f"{bridge['bridge_id']} lightening window intrudes upper bearing keepout for {hole['axis_id']}",
                            )

    def test_separate_display_lightening_windows_keep_manufacturable_web_around_fasteners(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_separate_display_partitioned_bridge_stage(
                Path(tmp),
                seed=8459,
                include_lightening=True,
            )

            minimum_web_mm = 1.4
            for bridge in result["bridge_stage"]["bridges"]:
                fastener_report = bridge.get("lightening", {}).get("fastener_web_clearance")
                self.assertIsNotNone(fastener_report, f"{bridge['bridge_id']} is missing fastener web clearance report")
                self.assertEqual("pass", fastener_report["status"])
                windows = bridge.get("lightening", {}).get("manufacturing_windows", [])
                for window in windows:
                    points = [tuple(point) for point in window.get("points", [])]
                    if len(points) < 3:
                        continue
                    for screw in bridge["screws"]:
                        gap = _minimum_closed_polyline_distance_to_point(points, (float(screw["x"]), float(screw["y"])))
                        gap -= float(screw["head_diameter_mm"]) / 2.0
                        with self.subTest(bridge=bridge["bridge_id"], window=window["window_id"], screw=screw["screw_id"]):
                            self.assertGreaterEqual(
                                gap,
                                minimum_web_mm,
                                f"{bridge['bridge_id']} {window['window_id']} leaves only {gap:.3f} mm web around {screw['screw_id']}",
                            )

    def test_bridge_stage_uses_analytic_boundaries_not_grid_contours(self):
        design = _build_design(42, include_bridges=False)

        plan = build_analytic_bridge_stage_plan(design, layout_id="seed_42_layout_01")

        self.assertEqual("pass", plan["status"])
        self.assertEqual("analytic_boundary_fitting", plan["boundary_source"])
        self.assertFalse(plan["grid_contour_used_for_cad"])
        self.assertEqual("train_bridge", plan["central_axis_policy"]["owning_bridge_id"])
        self.assertEqual("pass", plan["central_axis_policy"]["center_seam_status"])
        for bridge in plan["bridges"]:
            self.assertIn(bridge["bridge_id"], {"barrel_bridge", "train_bridge", "escapement_bridge"})
            self.assertIn(bridge["boundary_style"], {"analytic_local_lobe", "analytic_main_plate_with_lobe_keepouts"})
            self.assertLessEqual(bridge["max_freeform_turn_count"], 2)
            self.assertEqual("pass", bridge["edge_quality_status"])
            self.assertNotEqual("grid_label_contour", bridge["footprint_type"])

    def test_bridge_plate_seams_clear_countersunk_head_diameter(self):
        design = _build_design(42, include_bridges=False)

        plan = build_analytic_bridge_stage_plan(design, layout_id="seed_42_layout_01")

        self.assertEqual("pass", plan["seam_policy"]["minimum_plate_gap_status"])
        self.assertGreaterEqual(
            plan["seam_policy"]["required_minimum_plate_gap_mm"],
            p.BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM,
        )
        self.assertGreaterEqual(
            plan["seam_policy"]["observed_minimum_plate_gap_mm"],
            plan["seam_policy"]["required_minimum_plate_gap_mm"] - 1e-6,
        )

    def test_local_bridge_boundaries_do_not_have_sharp_corners(self):
        design = _build_design(42, include_bridges=False)

        plan = build_analytic_bridge_stage_plan(design, layout_id="seed_42_layout_01")

        for bridge in plan["bridges"]:
            if bridge["bridge_id"] == "train_bridge":
                continue
            with self.subTest(bridge=bridge["bridge_id"]):
                self.assertEqual("pass", bridge["edge_quality_status"])
                self.assertGreaterEqual(bridge["minimum_boundary_angle_deg"], 80.0)
                self.assertIn(
                    bridge["edge_fitting_method"],
                    {"analytic_spline_fit"},
                )
                self.assertEqual("smooth_seam_curve", bridge["inner_boundary_kind"])
                self.assertGreaterEqual(bridge["inner_boundary_control_point_count"], 3)
                self.assertNotEqual("local_circle_lobe", bridge["inner_boundary_kind"])

    def test_analytic_bridge_stage_preserves_one_envelope_per_bridge(self):
        design = _build_design(42, include_bridges=False)

        plan = build_analytic_bridge_stage_plan(design, layout_id="seed_42_layout_01")

        for bridge in plan["bridges"]:
            with self.subTest(bridge=bridge["bridge_id"]):
                owned = []
                for envelope_id, envelope in plan["_partition"]["envelopes"].items():
                    if _effective_bridge_contains_envelope(bridge, envelope):
                        owned.append(envelope_id)
                self.assertEqual([bridge["bridge_id"]], owned)

    def test_train_keepouts_cut_through_outer_radius_without_local_plate_overhang(self):
        design = _build_design(42, include_bridges=False)

        plan = build_analytic_bridge_stage_plan(design, layout_id="seed_42_layout_01")

        train = next(bridge for bridge in plan["bridges"] if bridge["bridge_id"] == "train_bridge")
        for keepout in train["footprint"]["keepouts"]:
            radii = [math.hypot(point[0], point[1]) for point in keepout["points"]]
            self.assertGreater(max(radii), 22.0)

        for bridge in plan["bridges"]:
            if bridge["bridge_id"] == "train_bridge":
                continue
            radii = [math.hypot(point[0], point[1]) for point in bridge["footprint"]["points"]]
            self.assertLessEqual(max(radii), 22.0001)

    def test_support_pads_are_derived_from_their_bridge_outer_service_domain(self):
        design = _build_design(42, include_bridges=False)

        plan = build_analytic_bridge_stage_plan(design, layout_id="seed_42_layout_01")

        for bridge in plan["bridges"]:
            allowed_spans = bridge["outer_service_spans"]
            for pad in bridge["support_pads"]:
                with self.subTest(bridge=bridge["bridge_id"], pad=pad["pad_id"]):
                    self.assertEqual(bridge["bridge_id"], pad["owner_bridge"])
                    self.assertEqual("final_bridge_boundary_service_span", pad["domain_source"])
                    self.assertTrue(
                        any(_span_inside(pad["angular_start_deg"], pad["angular_end_deg"], allowed) for allowed in allowed_spans)
                    )

    def test_support_pads_follow_final_partition_edges_and_screws_are_inset(self):
        design = _build_design(42, include_bridges=False)

        plan = build_analytic_bridge_stage_plan(design, layout_id="seed_42_layout_01")
        bridges = {bridge["bridge_id"]: bridge for bridge in plan["bridges"]}

        barrel = bridges["barrel_bridge"]
        barrel_pad = barrel["support_pads"][0]
        self.assertEqual("final_bridge_boundary_service_span", barrel_pad["domain_source"])
        self.assertAlmostEqual(
            barrel["outer_service_domain"]["angular_start_deg"],
            barrel_pad["angular_start_deg"],
            places=4,
        )
        self.assertAlmostEqual(
            barrel["outer_service_domain"]["angular_end_deg"],
            barrel_pad["angular_end_deg"],
            places=4,
        )
        self.assertEqual(3, len(barrel["screws"]))

        train = bridges["train_bridge"]
        train_pads = train["support_pads"]
        self.assertEqual(2, len(train_pads))
        self.assertAlmostEqual(bridges["escapement_bridge"]["outer_service_domain"]["angular_end_deg"], train_pads[0]["angular_start_deg"], places=4)
        self.assertAlmostEqual(barrel["outer_service_domain"]["angular_start_deg"], train_pads[0]["angular_end_deg"], places=4)
        self.assertAlmostEqual(barrel["outer_service_domain"]["angular_end_deg"], train_pads[1]["angular_start_deg"], places=4)
        self.assertAlmostEqual(bridges["escapement_bridge"]["outer_service_domain"]["angular_start_deg"], train_pads[1]["angular_end_deg"], places=4)

        required_edge_margin = math.degrees(
            (p.BRIDGE_SUPPORT_PAD_ARC_LENGTH_TO_HEAD_DIAMETER_RATIO * p.BRIDGE_COUNTERSUNK_HEAD_DIAMETER_MM / 2.0)
            / p.BRIDGE_SCREW_PITCH_RADIUS_MM
        )
        for bridge in plan["bridges"]:
            for pad in bridge["support_pads"]:
                pad_screws = [
                    screw
                    for screw in bridge["screws"]
                    if _angle_inside(screw["angle_deg"], pad["angular_start_deg"], pad["angular_end_deg"])
                ]
                if len(pad_screws) <= 1:
                    continue
                for screw in pad_screws:
                    edge_distance = min(
                        _positive_span(pad["angular_start_deg"], screw["angle_deg"]),
                        _positive_span(screw["angle_deg"], pad["angular_end_deg"]),
                    )
                    self.assertGreaterEqual(edge_distance, required_edge_margin - 0.5)

    def test_step_review_assembly_flattens_semantic_colored_leaf_parts(self):
        design = _build_design(42, include_bridges=False)
        plan = build_analytic_bridge_stage_plan(design, layout_id="seed_42_layout_01")
        design["bridges_generated"] = True
        design["bridge_stage"] = plan
        base = p.Compound(
            label="nested_review_root",
            children=[
                p._make_mainplate(design),
                p._make_gear(next(gear for gear in design["gears"] if gear["gear_id"] == "center_wheel")),
            ],
        )

        leaves = _flatten_for_step_color_sync(base)
        by_label = {leaf.label: leaf for leaf in leaves}

        self.assertNotIn("nested_review_root", by_label)
        self.assertIn("foundation_mainplate", by_label)
        self.assertIn("center_wheel", by_label)
        self.assertEqual(tuple(p.Color(*p.REVIEW_MATERIALS["chrome"]["rgba"])), tuple(by_label["foundation_mainplate"].color))
        self.assertEqual(tuple(p.Color(*p.REVIEW_MATERIALS["brass"]["rgba"])), tuple(by_label["center_wheel"].color))

    def test_flattened_visible_material_nodes_are_part_level(self):
        design = _build_design(42, include_bridges=False)
        flat_nodes = _flatten_for_step_color_sync(_build_base_without_old_bridges(design))

        bad_nodes = [
            (getattr(node, "label", ""), type(node).__name__)
            for node in flat_nodes
            if getattr(node, "label", "") and type(node).__name__ != "Part"
        ]

        self.assertEqual([], bad_nodes)

    def test_flat_step_feature_refs_match_flattened_step_occurrences(self):
        design = _build_design(42, include_bridges=False)
        plan = build_analytic_bridge_stage_plan(design, layout_id="seed_42_layout_01")
        design["bridges_generated"] = True
        design["bridge_stage"] = plan
        flat_labels = [
            "foundation_mainplate",
            "center_wheel",
            "barrel_bridge",
            "train_bridge",
            "escapement_bridge",
        ]

        refs = _flat_step_feature_refs_for_color_sync(flat_labels, design)

        self.assertEqual("#o1.1", refs["foundation_mainplate"]["ref"])
        self.assertEqual("#o1.2", refs["center_wheel"]["ref"])
        self.assertEqual("#o1.3", refs["barrel_bridge"]["ref"])
        self.assertEqual("#o1.4", refs["train_bridge"]["ref"])
        self.assertEqual("#o1.5", refs["escapement_bridge"]["ref"])
        for feature_id in flat_labels:
            self.assertNotIn("#o1.1.", refs[feature_id]["ref"])

    def test_flat_step_feature_refs_preserve_indices_across_unlabeled_parts(self):
        design = _build_design(42, include_bridges=False)
        refs = _flat_step_feature_refs_for_color_sync(["first_part", "", "third_part"], design)

        self.assertEqual("#o1.1", refs["first_part"]["ref"])
        self.assertEqual("#o1.3", refs["third_part"]["ref"])
        self.assertNotIn("", refs)

    def test_browser_translucency_sync_rebinds_bridges_to_transparent_glb_leaves(self):
        motion = {
            "features": {
                "barrel_bridge": {"ref": "#o1.99", "axis": [0, 0, 1]},
                "barrel_bridge_service_1_screw_1": {"ref": "#o1.96", "axis": [0, 0, 1]},
                "train_bridge": {"ref": "#o1.105", "axis": [0, 0, 1]},
                "train_bridge_service_2_screw_3": {"ref": "#o1.104", "axis": [0, 0, 1]},
                "escapement_bridge": {"ref": "#o1.109", "axis": [0, 0, 1]},
            },
            "visual_materials": {
                "barrel_bridge": {"rgba": [0.73, 0.76, 0.78, 0.2]},
                "barrel_bridge_service_1_screw_1": {"rgba": [0.73, 0.76, 0.78, 1.0]},
                "train_bridge": {"rgba": [0.73, 0.76, 0.78, 0.2]},
                "train_bridge_service_2_screw_3": {"rgba": [0.73, 0.76, 0.78, 1.0]},
                "escapement_bridge": {"rgba": [0.73, 0.76, 0.78, 0.2]},
            },
            "semantic_material_contracts": {
                "barrel_bridge": {"visible_ref": "#o1.99"},
                "train_bridge": {"visible_ref": "#o1.105"},
                "escapement_bridge": {"visible_ref": "#o1.109"},
            },
        }
        glb_json = {
            "materials": [
                {"pbrMetallicRoughness": {"baseColorFactor": [0.73, 0.76, 0.78, 1.0]}},
                {"pbrMetallicRoughness": {"baseColorFactor": [0.73, 0.76, 0.78, 0.2]}},
            ],
            "meshes": [
                {"primitives": [{"material": 0}]},
                {"primitives": [{"material": 1}]},
                {"primitives": [{"material": 1}]},
                {"primitives": [{"material": 1}]},
            ],
            "nodes": [
                {"name": "o1.96.1", "mesh": 0, "extras": {"cadOccurrenceId": "o1.96.1"}},
                {"name": "o1.104.1", "mesh": 1, "extras": {"cadOccurrenceId": "o1.104.1"}},
                {"name": "o1.110.1", "mesh": 2, "extras": {"cadOccurrenceId": "o1.110.1"}},
                {"name": "o1.114.1", "mesh": 3, "extras": {"cadOccurrenceId": "o1.114.1"}},
            ],
        }

        changed = _sync_bridge_translucency_motion_from_glb_json(motion, glb_json)

        self.assertTrue(changed)
        self.assertEqual("#o1.104", motion["features"]["barrel_bridge"]["ref"])
        self.assertEqual(["o1.104.1"], motion["features"]["barrel_bridge"]["partIds"])
        self.assertEqual("#o1.110", motion["features"]["train_bridge"]["ref"])
        self.assertEqual(["o1.110.1"], motion["features"]["train_bridge"]["partIds"])
        self.assertEqual("#o1.114", motion["features"]["escapement_bridge"]["ref"])
        self.assertEqual(["o1.114.1"], motion["features"]["escapement_bridge"]["partIds"])
        self.assertNotIn("barrel_bridge_service_1_screw_1", motion["visual_materials"])
        self.assertNotIn("train_bridge_service_2_screw_3", motion["visual_materials"])
        self.assertEqual("#o1.104", motion["semantic_material_contracts"]["barrel_bridge"]["visible_ref"])

    def test_separate_display_partitioned_stage_motion_uses_review_material_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_separate_display_partitioned_bridge_stage(
                Path(tmp) / "stage",
                seed=8459,
                layout_id="material_contract_test",
                include_lightening=True,
            )

            motion = json.loads(Path(result["artifacts"]["motion_json"]).read_text(encoding="utf-8"))

        self.assertEqual("pass", motion["checks"]["review_materials_declared"])
        self.assertEqual("pass", motion["checks"]["semantic_material_contracts_cover_visible_features"])
        self.assertEqual(p.REVIEW_MATERIALS["chrome"], motion["visual_materials"]["foundation_mainplate"])
        self.assertEqual(p.REVIEW_MATERIALS["brass"], motion["visual_materials"]["train_stage_1_wheel"])
        self.assertEqual(p.REVIEW_MATERIALS["jewel"], motion["visual_materials"]["upper_jewel_bearing_train_stage_1_axis"])
        self.assertEqual(p.REVIEW_MATERIALS["silver"], motion["visual_materials"]["hour_hand_arbor_extension"])
        self.assertEqual(p.REVIEW_MATERIALS["translucent_bridge"], motion["visual_materials"]["barrel_bridge"])
        self.assertEqual(0.80, motion["visual_materials"]["barrel_bridge"]["rgba"][3])
        self.assertEqual(0.80, motion["visual_materials"]["train_bridge"]["rgba"][3])
        self.assertEqual(0.80, motion["visual_materials"]["escapement_bridge"]["rgba"][3])


def _minimum_angle(points):
    result = 180.0
    for index, point in enumerate(points):
        prev = points[index - 1]
        nxt = points[(index + 1) % len(points)]
        v1 = (prev[0] - point[0], prev[1] - point[1])
        v2 = (nxt[0] - point[0], nxt[1] - point[1])
        d1 = math.hypot(*v1)
        d2 = math.hypot(*v2)
        if d1 * d2 == 0:
            continue
        cos_value = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (d1 * d2)))
        result = min(result, math.degrees(math.acos(cos_value)))
    return result


def _effective_bridge_contains_envelope(bridge, envelope):
    points = np.array(envelope["points"], dtype=float)
    centroid = (float(points[:, 0].mean()), float(points[:, 1].mean()))
    footprint = bridge["footprint"]
    if bridge["bridge_id"] == "train_bridge":
        radius = 22.0
        if math.hypot(*centroid) > radius:
            return False
        for keepout in footprint.get("keepouts", []):
            if MplPath(np.array(keepout["points"], dtype=float)).contains_point(centroid):
                return False
        return True
    return MplPath(np.array(footprint["points"], dtype=float)).contains_point(centroid)


def _effective_bridge_contains_point(bridge, point):
    footprint = bridge["footprint"]
    components = footprint.get("components", [])
    if components:
        for component in components:
            points = component.get("points", [])
            if len(points) >= 3 and MplPath(np.array(points, dtype=float)).contains_point(point, radius=1e-6):
                return True
        return False
    return MplPath(np.array(footprint["points"], dtype=float)).contains_point(point, radius=1e-6)


def _minimum_component_distance(left_bridge, right_bridge):
    distances = []
    for left_component in left_bridge["footprint"].get("components", []):
        left_points = left_component.get("points", [])
        if len(left_points) < 3:
            continue
        for right_component in right_bridge["footprint"].get("components", []):
            right_points = right_component.get("points", [])
            if len(right_points) < 3:
                continue
            distances.append(_polygon_distance(left_points, right_points))
    return min(distances) if distances else 0.0


def _sample_circle_points(x, y, radius, *, count):
    return [
        (x + radius * math.cos(2.0 * math.pi * index / count), y + radius * math.sin(2.0 * math.pi * index / count))
        for index in range(count)
    ]


@contextmanager
def _patched_pattern3_fast_cad_pipeline(*, patch_validation=True):
    originals = {
        "build_assembly": p._build_separate_display_assembly,
        "flatten": bridge_stage_module._flatten_for_step_color_sync,
        "compound": bridge_stage_module.bd.Compound,
        "export_step": bridge_stage_module.bd.export_step,
        "motion": p._build_independent_display_motion_report,
        "semantic": p._build_independent_display_semantic_report,
        "validation": p._build_independent_display_validation_report,
    }

    def fake_export_step(_assembly, step_path):
        Path(step_path).write_text(
            "ISO-10303-21; PATTERN3 TEST STEP; ENDSEC; END-ISO-10303-21;",
            encoding="utf-8",
        )

    bridge_stage_module._flatten_for_step_color_sync = lambda _assembly: [
        SimpleNamespace(label="minute_hand"),
        SimpleNamespace(label="hour_hand"),
        SimpleNamespace(label="train_bridge"),
    ]
    bridge_stage_module.bd.Compound = lambda *, children, label: {"children": children, "label": label}
    bridge_stage_module.bd.export_step = fake_export_step
    p._build_separate_display_assembly = lambda _design: object()
    p._build_independent_display_motion_report = lambda _design, feature_refs_override=None: {
        "status": "pass",
        "moving_groups": [],
        "fixed_features": [],
        "features": feature_refs_override or {},
        "checks": {},
    }
    p._build_independent_display_semantic_report = lambda _design: {"status": "pass"}
    if patch_validation:
        p._build_independent_display_validation_report = lambda _design, _semantic, _motion=None: {
            "status": "pass",
            "failed_checks": [],
            "checks": {
                "pattern_card_id_is_watch_pattern_03_independent_hour_minute_no_seconds_v1": "pass",
                "hour_branch_independent_from_minute_branch": "pass",
            },
        }

    try:
        yield
    finally:
        p._build_separate_display_assembly = originals["build_assembly"]
        bridge_stage_module._flatten_for_step_color_sync = originals["flatten"]
        bridge_stage_module.bd.Compound = originals["compound"]
        bridge_stage_module.bd.export_step = originals["export_step"]
        p._build_independent_display_motion_report = originals["motion"]
        p._build_independent_display_semantic_report = originals["semantic"]
        if patch_validation:
            p._build_independent_display_validation_report = originals["validation"]


def _visible_outer_edge_angle_span(bridge):
    outer_points = []
    for point in bridge["footprint"]["points"]:
        radius = math.hypot(float(point[0]), float(point[1]))
        if radius >= p.CASE_RADIUS_MM - 0.08:
            outer_points.append((float(point[0]), float(point[1])))
    if not outer_points:
        raise AssertionError(f"{bridge['bridge_id']} has no visible outer case edge points")
    angles = [math.degrees(math.atan2(point[1], point[0])) % 360.0 for point in outer_points]
    best_start = angles[0]
    best_span = 360.0
    for candidate_start in angles:
        span = max((angle - candidate_start) % 360.0 for angle in angles)
        if span < best_span:
            best_start = candidate_start
            best_span = span
    return best_start, (best_start + best_span) % 360.0


def _minimum_closed_polyline_distance_to_point(points, point):
    minimum = float("inf")
    px, py = point
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        sx, sy = float(start[0]), float(start[1])
        ex, ey = float(end[0]), float(end[1])
        vx, vy = ex - sx, ey - sy
        length_squared = vx * vx + vy * vy
        if length_squared <= 1e-12:
            distance = math.hypot(px - sx, py - sy)
        else:
            t = max(0.0, min(1.0, ((px - sx) * vx + (py - sy) * vy) / length_squared))
            distance = math.hypot(px - (sx + t * vx), py - (sy + t * vy))
        minimum = min(minimum, distance)
    return minimum


def _max_loop_segment_length(points):
    normalized = [(float(point[0]), float(point[1])) for point in points]
    if len(normalized) < 2:
        return 0.0
    return max(math.dist(normalized[index], normalized[(index + 1) % len(normalized)]) for index in range(len(normalized)))


def _span_inside(start, end, allowed):
    allowed_start, allowed_end = allowed["angular_start_deg"], allowed["angular_end_deg"]
    mid = (start + ((end - start) % 360.0) / 2.0) % 360.0
    return (
        _angle_inside(start, allowed_start, allowed_end)
        and _angle_inside(end, allowed_start, allowed_end)
        and _angle_inside(mid, allowed_start, allowed_end)
    )

def _span_overlap_deg(left, right):
    total = 0.0
    for left_start, left_end in _span_segments(left["angular_start_deg"], left["angular_end_deg"]):
        for right_start, right_end in _span_segments(right["angular_start_deg"], right["angular_end_deg"]):
            total += max(0.0, min(left_end, right_end) - max(left_start, right_start))
    return total


def _span_segments(start, end):
    start = start % 360.0
    span = _positive_span(start, end)
    if start + span <= 360.0:
        return [(start, start + span)]
    return [(start, 360.0), (0.0, (start + span) % 360.0)]


def _angle_inside(angle, start, end):
    span = (end - start) % 360.0
    return ((angle - start) % 360.0) <= span + 1e-6


def _positive_span(start, end):
    return (end - start) % 360.0


if __name__ == "__main__":
    unittest.main()
