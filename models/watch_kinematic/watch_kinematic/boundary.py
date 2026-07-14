from __future__ import annotations


BOUNDARY_HARD_CONSTRAINTS = [
    "input_drive_axis_exists",
    "gear_train_connects_drive_to_each_output_axis",
    "each_visible_axis_has_support_path",
    "mesh_pairs_have_center_distance_match",
    "no_unexplained_overlapping_gears",
    "animation_sidecar_covers_all_moving_groups",
]

BOUNDARY_ACCEPTANCE_CRITERIA = [
    "all_motion_axes_have_local_frames",
    "boundary_package_preserves_v1_exclusions",
]


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def build_boundary_package(case: dict) -> dict:
    drive_axis = case["drive_axis"]
    output_axes = case["output_axes"]
    axis_ids = [drive_axis["id"], *[axis["id"] for axis in output_axes]]

    return {
        "domain": "watch_kinematic",
        "case_id": case["case_id"],
        "mechanism_type": case["mechanism_type"],
        "task_statement": (
            "Generate a watch-style kinematic demonstration mechanism that "
            "transmits one input rotation to visible output hand axes."
        ),
        "object_and_environment_list": {
            "environment": {
                "case_diameter_mm": case["case_diameter_mm"],
                "movement_thickness_mm": case["movement_thickness_mm"],
                "local_frame": case["local_frame"],
            },
            "input_objects": [drive_axis["id"]],
            "output_objects": [axis["id"] for axis in output_axes],
            "decorative_objects": case["style"]["motifs"],
        },
        "function_flow_graph": {
            "nodes": [
                "input_drive",
                "gear_train",
                "output_motion_display",
                "axis_support",
                "decorative_watch_case",
            ],
            "edges": [
                ["input_drive", "gear_train", "transmit_rotation"],
                ["gear_train", "output_motion_display", "display_motion"],
                ["axis_support", "gear_train", "support_rotating_axes"],
                ["decorative_watch_case", "output_motion_display", "decorate_watch_case"],
            ],
        },
        "interface_graph": {
            "drive_axis": drive_axis["id"],
            "output_axes": [axis["id"] for axis in output_axes],
            "motion_axis_frames": {
                axis_id: case["local_frame"] for axis_id in axis_ids
            },
            "required_interfaces": [
                "drive_to_first_gear_mesh",
                "gear_mesh_chain_between_axes",
                "pivot_support_to_mainplate_or_bridge",
                "hand_to_output_axis",
            ],
        },
        "required_functions": [
            "transmit_rotation",
            "display_motion",
            "support_rotating_axes",
            "decorate_watch_case",
        ],
        "hard_constraints": BOUNDARY_HARD_CONSTRAINTS.copy(),
        "soft_preferences": [
            "visible_gear_train",
            "open_mainplate",
            "reviewable_bridge_paths",
            "clear_decorative_identity",
        ],
        "operating_modes": [
            "static_semantic_review",
            "animated_kinematic_review",
        ],
        "acceptance_criteria": _dedupe(
            [*case["acceptance_criteria"], *BOUNDARY_ACCEPTANCE_CRITERIA]
        ),
        "open_questions": [
            "gear tooth counts and exact center distances are selected in synthesis",
            "decorative motif placement is selected in CAD generation",
        ],
        "not_in_v1_scope": list(case["excluded_systems"]),
        "drive_axis": drive_axis,
        "output_axes": output_axes,
        "local_frame": case["local_frame"],
        "style": case["style"],
        "style_motifs": case["style"]["motifs"],
    }
