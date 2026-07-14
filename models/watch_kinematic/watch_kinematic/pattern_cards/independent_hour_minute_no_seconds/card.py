import json
from pathlib import Path

PATTERN_CARD_ID = "independent_hour_minute_no_seconds_v1"


def build_independent_display_pattern_card() -> dict:
    return {
        "id": PATTERN_CARD_ID,
        "name": "Independent Hour And Minute Display Without Seconds",
        "pattern_class": "watch_kinematic_power_chain_variant",
        "lifecycle_state": "pattern_card_contract",
        "review_stage": "xy solver first, 3d generation after layout acceptance",
        "solved_function": (
            "Display minutes and hours on freely placed axes using two independent "
            "branches from the going train, without requiring a central display axis "
            "or generating a seconds hand."
        ),
        "construction_references": [
            "movement_geometric_center",
            "movement_frame",
            "train_stage_3_wheel_as_display_reference",
        ],
        "required_roles": [
            "mainplate",
            "mainspring_barrel",
            "neutral_train_stage",
            "escape_wheel_assembly",
            "pallet_fork",
            "balance_wheel_assembly",
            "minute_display_branch",
            "minute_input_relay_axis",
            "minute_display_axis",
            "minute_display_member",
            "minute_hand",
            "hour_display_branch",
            "hour_input_relay_axis",
            "hour_reduction_relay_axis",
            "hour_display_axis",
            "hour_display_member",
            "hour_hand",
        ],
        "forbidden_roles": [
            "seconds_hand",
            "seconds_display_arbor",
            "serial_hour_from_minute_motion_works",
        ],
        "forbidden_required_axes": [
            "display_center_axis",
            "center_axis",
            "seconds_axis",
        ],
        "hard_constraints": [
            "minute_display_axis != hour_display_axis",
            "movement_geometric_center is construction reference only",
            "no_seconds_hand",
            "minute branch and hour branch both originate from train_stage_3_wheel",
            "hour branch does not use minute_display_member as a driver, driven member, or ancestor",
            "train_to_minute_display_ratio = 1",
            "train_to_hour_display_ratio = 1 / 12",
            "hour_speed / minute_speed = 1 / 12",
            "for every gear: axis_center_distance + gear_tip_radius + 0.80 mm <= case_inner_radius",
        ],
        "role_contracts": {
            "minute_display_branch": {
                "role": "parallel_minute_display_branch",
                "function": "drive the minute display directly from the going train reference",
                "motion_chain": (
                    "train_stage_3_wheel -> minute_input_relay_pinion + "
                    "minute_input_relay_wheel -> minute_display_member -> minute_hand"
                ),
                "required_ratio": "minute_display_member speed / train_stage_3_wheel speed = 1",
                "allowed_motion": "rotate_about_local_z",
            },
            "hour_display_branch": {
                "role": "parallel_hour_display_branch",
                "function": "drive the hour display from the going train without passing through the minute display",
                "motion_chain": (
                    "train_stage_3_wheel -> hour_input_relay_pinion + "
                    "hour_input_relay_wheel -> hour_reduction_relay_pinion + "
                    "hour_reduction_relay_wheel -> hour_display_member -> hour_hand"
                ),
                "required_ratio": "hour_display_member speed / train_stage_3_wheel speed = 1 / 12",
                "forbidden_ancestors": [
                    "minute_display_member",
                    "minute_display_axis",
                    "minute_input_relay_axis",
                ],
                "allowed_motion": "rotate_about_local_z",
            },
        },
        "validation_checks": [
            "pattern_card_id_is_independent_hour_minute_no_seconds_v1",
            "movement_center_is_construction_reference_only",
            "no_required_display_center_axis",
            "no_seconds_hand",
            "separate_minute_and_hour_axes",
            "minute_motion_chain_closed",
            "hour_motion_chain_closed",
            "minute_branch_connected_to_train",
            "hour_branch_connected_to_train",
            "hour_branch_does_not_depend_on_minute_branch",
            "train_to_minute_ratio_1_to_1",
            "train_to_hour_ratio_1_to_12",
            "hour_to_minute_ratio_1_to_12",
            "declared_mesh_center_distances_pass",
            "same_layer_non_mesh_clearance_pass",
            "all_gear_tip_envelopes_inside_case",
            "foreign_axis_to_gear_keepout_pass",
            "minute_hand_sweep_clear",
            "hour_hand_sweep_clear",
        ],
        "negative_cases": [
            "collapse_minute_hour_axes_must_fail",
            "add_seconds_hand_must_fail",
            "disconnect_minute_branch_from_train_must_fail",
            "disconnect_hour_branch_from_train_must_fail",
            "hour_from_minute_serial_chain_must_fail",
        ],
    }


def render_independent_display_pattern_markdown(card: dict) -> str:
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


def write_independent_display_pattern_card(output_dir: Path) -> list[Path]:
    card = build_independent_display_pattern_card()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{PATTERN_CARD_ID}.json"
    md_path = output_dir / f"{PATTERN_CARD_ID}.md"
    json_path.write_text(
        json.dumps(card, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        render_independent_display_pattern_markdown(card),
        encoding="utf-8",
    )
    return [json_path, md_path]
