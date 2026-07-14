import json
from pathlib import Path

PATTERN_CARD_ID = "separate_hour_minute_no_seconds_v1"

def build_separate_display_pattern_card() -> dict:
    return {
        "id": PATTERN_CARD_ID,
        "name": "Separate Hour And Minute Display Without Seconds",
        "pattern_class": "watch_kinematic_power_chain_variant",
        "lifecycle_state": "pattern_card_contract",
        "review_stage": "no bridges first, bridge integration after lower mechanism acceptance",
        "solved_function": (
            "Display minutes and hours on independent solver-owned axes without "
            "requiring a central display axis or generating a seconds hand."
        ),
        "construction_references": [
            "movement_geometric_center",
            "movement_frame",
        ],
        "required_roles": [
            "mainplate",
            "case_or_review_frame",
            "mainspring_barrel",
            "barrel_arbor",
            "neutral_train_stage",
            "train_stage_1_wheel_or_pinion_pair",
            "train_stage_2_wheel_or_pinion_pair",
            "train_stage_3_or_final_train_pair",
            "escape_wheel_assembly",
            "pallet_fork",
            "balance_wheel_assembly",
            "hairspring_placeholder",
            "display_input_relay_axis",
            "display_input_relay_compound_member",
            "minute_display_axis",
            "minute_display_member",
            "minute_hand",
            "hour_display_axis",
            "hour_display_member",
            "hour_hand",
            "hour_reduction_display_train",
        ],
        "forbidden_roles": [
            "seconds_hand",
            "seconds_display_arbor",
        ],
        "forbidden_required_axes": [
            "display_center_axis",
            "center_axis",
            "seconds_axis",
        ],
        "hard_constraints": [
            "minute_display_axis != hour_display_axis",
            "movement_geometric_center is construction reference only",
            "hour_speed / minute_speed = 1 / 12",
            "no seconds display members are generated",
            "minute hand has a closed physical motion chain from train_stage_3_wheel",
            "hour hand has a closed motion chain from minute_display_member",
            "external Swiss lever escapement assembly replaces placeholder pallet/balance geometry",
            "for every gear: axis_center_distance + gear_tip_radius + 0.80 mm <= case_inner_radius",
        ],
        "role_contracts": {
            "display_input_relay_axis": {
                "role": "train_to_minute_display_input_relay",
                "function": "physically couple the selected train output to the minute display member",
                "motion_chain": (
                    "train_stage_3_wheel -> display_input_relay_pinion + "
                    "display_input_relay_wheel -> minute_display_member"
                ),
                "mount_chain": (
                    "mainplate lower support + declared upper support or accepted "
                    "no-bridge phase support policy"
                ),
                "allowed_motion": "rotate_about_local_z",
                "required_ratio": "minute_display_member speed / train_stage_3_wheel speed = 1",
                "required_geometry": [
                    "axis",
                    "compound relay wheel and pinion",
                    "two real external mesh interfaces",
                    "center-distance proof",
                    "mesh-plane proof",
                ],
            },
            "minute_display_axis": {
                "role": "free_placed_minute_display_axis",
                "function": "display minutes from the going train",
                "motion_chain": (
                    "train_stage_3_wheel -> display_input_relay -> "
                    "minute_display_member -> minute_hand"
                ),
                "mount_chain": (
                    "mainplate lower support + declared upper support or accepted "
                    "no-bridge phase support policy"
                ),
                "allowed_motion": "rotate_about_local_z",
                "required_ratio": "1 revolution per hour",
                "required_geometry": [
                    "axis",
                    "arbor/member",
                    "hand hub",
                    "hand blade",
                    "support seat",
                    "sweep envelope",
                ],
            },
            "hour_display_axis": {
                "role": "free_placed_hour_display_axis",
                "function": "display hours from minute display via 12:1 reduction",
                "motion_chain": (
                    "minute_display_member -> hour_reduction_display_train -> "
                    "hour_display_member -> hour_hand"
                ),
                "mount_chain": (
                    "mainplate lower support + declared upper support or accepted "
                    "no-bridge phase support policy"
                ),
                "allowed_motion": "rotate_about_local_z",
                "required_ratio": "1 revolution per 12 hours",
                "required_geometry": [
                    "axis",
                    "arbor/member",
                    "hand hub",
                    "hand blade",
                    "support seat",
                    "sweep envelope",
                ],
            },
            "hour_reduction_display_train": {
                "role": "separated_display_ratio_transform",
                "function": "convert minute display speed to hour display speed",
                "required_ratio": "hour_speed / minute_speed = 1 / 12",
                "allowed_interfaces": [
                    "external mesh",
                    "internal mesh",
                    "rigid compound arbor",
                    "idler external mesh",
                ],
                "required_evidence": [
                    "tooth-count equation",
                    "direction proof",
                    "center-distance proof",
                    "mesh-plane proof",
                ],
            },
        },
        "validation_checks": [
            "pattern_card_id_is_separate_hour_minute_no_seconds_v1",
            "movement_center_is_construction_reference_only",
            "no_required_display_center_axis",
            "no_seconds_hand",
            "separate_minute_and_hour_axes",
            "minute_motion_chain_closed",
            "minute_display_power_chain_connected_to_train",
            "hour_motion_chain_closed",
            "hour_to_minute_ratio_1_to_12",
            "external_escapement_assembly_present",
            "display_direction_contract_pass",
            "minute_hand_mount_6dof_pass",
            "hour_hand_mount_6dof_pass",
            "minute_hand_sweep_clear",
            "hour_hand_sweep_clear",
            "display_relay_meshes_valid",
            "declared_mesh_center_distances_pass",
            "display_relay_axes_supported",
            "same_layer_non_mesh_clearance_pass",
            "all_gear_tip_envelopes_inside_case",
            "foreign_axis_to_gear_keepout_pass",
            "train_escapement_bridge_seam_corridor_pass",
            "escape_pinion_display_input_same_layer_clearance_pass",
            "animation_leaf_binding_pass",
            "semantic_material_contracts_cover_visible_features",
        ],
        "negative_cases": [
            "remove_hour_display_relay_must_fail",
            "remove_display_input_relay_must_fail",
            "replace_external_escapement_with_placeholder_must_fail",
            "collapse_minute_hour_axes_must_fail",
            "add_seconds_hand_must_fail",
            "ancestor_animation_binding_must_fail",
        ],
    }


def render_separate_display_pattern_markdown(card: dict) -> str:
    lines = [
        f"# {card['name']}",
        "",
        f"- ID: `{card['id']}`",
        f"- Pattern Class: `{card['pattern_class']}`",
        f"- Lifecycle State: `{card['lifecycle_state']}`",
        f"- Review Stage: {card['review_stage']}",
        f"- Solved Function: {card['solved_function']}",
        "",
    ]

    sections = [
        ("Construction References", card["construction_references"]),
        ("Required Roles", card["required_roles"]),
        ("Forbidden Roles", card["forbidden_roles"]),
        ("Forbidden Required Axes", card["forbidden_required_axes"]),
        ("Hard Constraints", card["hard_constraints"]),
        ("Validation Checks", card["validation_checks"]),
        ("Negative Cases", card["negative_cases"]),
    ]
    for title, values in sections:
        lines.extend([f"## {title}", ""])
        lines.extend(f"- `{value}`" for value in values)
        lines.append("")

    lines.extend(["## Role Contracts", ""])
    for role_name, contract in card["role_contracts"].items():
        lines.extend([f"### `{role_name}`", ""])
        for key, value in contract.items():
            label = key.replace("_", " ").title()
            if isinstance(value, list):
                lines.append(f"- {label}:")
                lines.extend(f"  - `{item}`" for item in value)
            else:
                lines.append(f"- {label}: {value}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_separate_display_pattern_card(output_dir: Path) -> list[Path]:
    card = build_separate_display_pattern_card()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{PATTERN_CARD_ID}.json"
    md_path = output_dir / f"{PATTERN_CARD_ID}.md"
    json_path.write_text(
        json.dumps(card, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        render_separate_display_pattern_markdown(card),
        encoding="utf-8",
    )
    return [json_path, md_path]
