import json
from pathlib import Path

PATTERN_CARD_ID = "central_hour_minute_with_off_center_seconds_v1"


def build_current_pattern_card() -> dict:
    return {
        "id": PATTERN_CARD_ID,
        "name": "Central Hour/Minute With Off-Center Seconds",
        "pattern_class": "watch_kinematic_power_chain_variant",
        "lifecycle_state": "executable_pattern_card",
        "review_stage": "full power chain with bridge-ready supports",
        "solved_function": (
            "Generate a mechanical watch power chain from mainspring barrel to "
            "Swiss lever escapement, with coaxial central hour/minute hands and "
            "an off-center seconds hand."
        ),
        "construction_references": [
            "movement_geometric_center",
            "display_center_axis",
            "mainplate_frame",
        ],
        "required_roles": [
            "mainplate",
            "mainspring_barrel",
            "barrel_arbor",
            "center_wheel_axis",
            "third_wheel_axis",
            "fourth_wheel_axis",
            "escape_wheel_axis",
            "pallet_fork_axis",
            "balance_wheel_axis",
            "central_hour_minute_display_axis",
            "minute_work_axis",
            "hour_hand",
            "minute_hand",
            "off_center_seconds_hand",
            "upper_jewel_bearing_targets",
            "bridge_perimeter_service_band",
        ],
        "hard_constraints": [
            "hour_hand_axis == minute_hand_axis == display_center_axis",
            "seconds_hand_axis == fourth_wheel_axis",
            "hour_speed : minute_speed : seconds_speed = 1 : 60 : 3600",
            "display hands rotate clockwise in the STEP module convention",
            "all train axes have bridge-ready upper jewel bearing targets",
            "bridge perimeter service band is reserved before bridge CAD is generated",
            "gear layers do not exceed four functional Z layers",
            "foreign through-axes clear non-owned gear envelopes",
        ],
        "negative_cases": [
            "missing_central_hour_minute_axis_must_fail",
            "seconds_hand_not_on_fourth_axis_must_fail",
            "wrong_display_speed_ratio_must_fail",
            "through_axis_intersects_foreign_gear_must_fail",
            "bridge_service_band_intrusion_must_fail",
        ],
        "validation_checks": [
            "power_chain_connected",
            "compound_gears_complete",
            "gear_mesh_phase_alignment",
            "display_hands_exist",
            "display_hand_stack_clear",
            "three_hand_drive_chains_declared",
            "display_motion_chain_realized",
            "hour_motion_reduction_proven",
            "coaxial_display_sleeve_clearance",
            "central_hour_minute_axis",
            "seconds_hand_length_within_case_clearance",
            "seconds_hand_sweep_clear",
            "display_hand_mount_stacks_closed",
            "display_hand_mount_stacks_xy_connected",
            "display_hand_mount_stacks_6dof_constrained",
        ],
    }


def render_current_pattern_markdown(card: dict) -> str:
    lines = [
        f"# {card['name']}",
        "",
        f"- Pattern ID: `{card['id']}`",
        f"- Lifecycle State: `{card['lifecycle_state']}`",
        "",
        "## Solved Function",
        "",
        card["solved_function"],
        "",
        "## Required Roles",
        "",
    ]
    lines.extend(f"- `{role}`" for role in card["required_roles"])
    lines.extend(["", "## Hard Constraints", ""])
    lines.extend(f"- {constraint}" for constraint in card["hard_constraints"])
    lines.extend(["", "## Validation Checks", ""])
    lines.extend(f"- `{check}`" for check in card["validation_checks"])
    lines.extend(["", "## Negative Cases", ""])
    lines.extend(f"- `{case}`" for case in card["negative_cases"])
    return "\n".join(lines) + "\n"


def write_current_pattern_card(output_dir: str | Path) -> list[Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    card = build_current_pattern_card()
    json_path = target / f"{PATTERN_CARD_ID}.json"
    md_path = target / f"{PATTERN_CARD_ID}.md"
    json_path.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_current_pattern_markdown(card), encoding="utf-8")
    return [json_path, md_path]
