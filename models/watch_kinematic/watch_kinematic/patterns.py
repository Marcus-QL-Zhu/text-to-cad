"""Literature-derived pattern cards for the watch-style kinematic demo."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path


EVIDENCE = {
    "WK001": {
        "id": "WK001_ciechanowski_mechanical_watch",
        "type": "watchmaking_reference",
        "notes": "Explains the going train, compound wheel/pinion arbors, mainplate, train wheel bridge, and bridge screw support logic.",
    },
    "WK002": {
        "id": "WK002_openmovement_om10",
        "type": "watchmaking_reference",
        "notes": "Open-source mechanical watch movement program and future real-CAD cross-check source.",
    },
    "WK003": {
        "id": "WK003_eta_technical_communication",
        "type": "watchmaking_reference",
        "notes": "Names main plate, barrel bridge, train wheel bridge, balance bridge, pallet bridge, and bridge screws in real movement documentation.",
    },
    "WK004": {
        "id": "WK004_horopedia_barrel_arbor",
        "type": "watchmaking_reference",
        "notes": "Defines barrel arbor support through mainplate and barrel bridge and marks the drive-side arbor as torque critical.",
    },
    "WK005": {
        "id": "WK005_horopedia_watch_movement",
        "type": "watchmaking_reference",
        "notes": "Defines mechanical watch subsystem boundaries so visual motifs are not mistaken for escapement, winding, or setting mechanisms.",
    },
    "A1": {
        "id": "A1_formal_transmission_assembly_model",
        "type": "formal_model",
        "notes": "Local formal predicates and equations for gear trains, arbors, supports, bridges, screw joints, and visual-only scope.",
    },
    "A15": {
        "id": "A1_5_rule_space_sampler",
        "type": "rule_space_validation",
        "notes": "Generated 12 abstract candidates with 8 valid and 4 intentionally invalid cases across varied topology, arbor, output, and bridge counts.",
    },
    "VISUAL": {
        "id": "user_supplied_leap71_reference_images",
        "type": "visual_style_evidence",
        "notes": "Reference screenshots used only for open-case visual style, visible gears, decorative spiral, and faceted bezel motifs.",
    },
}


def _sources(*keys: str) -> list[dict]:
    return [deepcopy(EVIDENCE[key]) for key in keys]


PATTERN_CARDS = [
    {
        "id": "watch_case_and_mainplate_frame",
        "name": "Watch Case And Mainplate Frame",
        "pattern_class": "executable_engineering_pattern",
        "lifecycle_state": "executable_candidate",
        "solved_function": "Provide the fixed movement frame that owns the local datum frame, mainplate seats, bridge receivers, and case review boundary.",
        "required_interfaces": [
            "movement local coordinate frame",
            "drive/output arbor axis list",
            "mainplate lower pivot seat list",
            "bridge screw receiver list",
            "case and moving-gear clearance envelope",
        ],
        "generated_components": [
            "case review frame",
            "mainplate",
            "lower pivot seats",
            "bridge screw receiving features",
        ],
        "generated_features": [
            "fixed local datum frame",
            "mainplate lower support holes",
            "mainplate screw receiving holes",
            "case clearance boundary",
        ],
        "parameter_variables": [
            "case_outer_radius",
            "mainplate_radius",
            "mainplate_thickness",
            "axis_positions",
            "receiver_hole_positions",
        ],
        "hard_constraints": [
            "Mainplate(M) and Fixed(M) must hold for the movement base",
            "OwnsFeature(mainplate, lower_pivot_seat(axis)) for every non-report-only train arbor",
            "all arbor axes must be parallel to movement z in V0",
            "case boundary must not intersect gear pitch envelopes or output hand sweeps",
        ],
        "soft_preferences": [
            "leave visible negative space around the wheel train",
            "align case openings with bridge and output-axis rhythm",
        ],
        "validation_checks": [
            "every arbor has a declared axis in the shared local frame",
            "mainplate owns lower supports and screw receivers",
            "case and mainplate remain fixed in the animation sidecar",
        ],
        "known_failure_modes": [
            "floating axes without mainplate support seats",
            "bridge screws have no receiving feature in the mainplate",
            "case wall clips pitch circles or hand sweep",
        ],
        "repair_strategies": [
            "derive missing seats from the formal arbor list",
            "add mainplate receiver features before placing bridge screws",
            "increase case radius or compact the gear train",
        ],
        "evidence_sources": _sources("WK001", "WK003", "A1", "A15"),
        "formal_model_refs": [
            "Frame F = {origin O, x, y, z}",
            "Mainplate(M); Fixed(M)",
            "OwnsFeature(mainplate, lower_pivot_seat(axis))",
            "Axis(a) = line(p_a.x, p_a.y, z)",
        ],
        "rule_space_refs": [
            "valid candidates vary across 3-6 arbors while preserving one shared local frame",
            "invalid candidates reject missing support and bad mesh envelope placement",
        ],
        "promotion_notes": "Watch-specific until another mechanism domain reuses mainplate-like datum ownership with the same deterministic checks.",
    },
    {
        "id": "visible_output_hand_axis",
        "name": "Visible Output Hand Axis",
        "pattern_class": "executable_engineering_pattern",
        "lifecycle_state": "executable_candidate",
        "solved_function": "Attach a visible hand to an output arbor that is genuinely connected to the drive through the gear graph.",
        "required_interfaces": [
            "output arbor axis",
            "gear path from drive to output arbor",
            "hand sweep clearance envelope",
            "animation sidecar moving group",
        ],
        "generated_components": [
            "output arbor",
            "hand pointer",
            "hub cap",
            "hand sweep envelope",
        ],
        "generated_features": [
            "coaxial hand hub",
            "hand blade",
            "display clearance zone",
        ],
        "parameter_variables": [
            "axis_id",
            "hand_length",
            "hand_width",
            "hub_radius",
            "initial_display_angle",
        ],
        "hard_constraints": [
            "OutputAxis(arbor) must have a path from the drive axis through MeshesWith and RigidlyAttached edges",
            "DisplaysMotion(hand, arbor) and RigidlyAttached(hand, arbor) must be declared",
            "hand sweep must clear case, bridge, screw, and neighboring hand envelopes",
        ],
        "soft_preferences": [
            "make multi-output hands visually distinct",
            "avoid hiding active gear meshes with hand geometry",
        ],
        "validation_checks": [
            "output gear is connected to drive in the rule-space graph",
            "hand and arbor are coaxial",
            "hand group is included in the animation sidecar",
        ],
        "known_failure_modes": [
            "output hand rotates around a decorative but disconnected axis",
            "hand intersects bridge, bezel, or neighboring hand",
            "animation rate is manually assigned instead of propagated through gear graph",
        ],
        "repair_strategies": [
            "insert or reroute gear meshes until the output path exists",
            "shorten or phase-shift the hand sweep",
            "compute sidecar angular velocity from the graph ratio",
        ],
        "evidence_sources": _sources("WK001", "WK005", "A1", "A15"),
        "formal_model_refs": [
            "OutputAxis(a_o) -> exists path P from DriveAxis to a_o",
            "DisplaysMotion(hand, arbor)",
            "theta_g(t) = theta_g(0) + omega_g * t",
        ],
        "rule_space_refs": [
            "valid candidates cover 1, 2, and 3 output axes",
            "invalid_disconnected_output proves disconnected display axes are rejected",
        ],
        "promotion_notes": "Candidate can later generalize to any visible display axis driven by a mechanical graph.",
    },
    {
        "id": "compound_gear_train_between_axes",
        "name": "Compound Gear Train Between Axes",
        "pattern_class": "executable_engineering_pattern",
        "lifecycle_state": "executable_candidate",
        "solved_function": "Generate a multi-stage visible wheel/pinion graph that transmits rotation from a drive axis to one or more output axes.",
        "required_interfaces": [
            "drive arbor axis",
            "output arbor axes",
            "tooth counts",
            "gear module",
            "center-distance layout",
            "compound wheel/pinion pairs",
        ],
        "generated_components": [
            "drive wheel",
            "intermediate wheel/pinion arbors",
            "output pinions or wheels",
            "mesh relation graph",
        ],
        "generated_features": [
            "pitch circle metadata",
            "mesh pair records",
            "compound arbor records",
            "angular velocity propagation map",
        ],
        "parameter_variables": [
            "gear_module",
            "tooth_counts",
            "pitch_radii",
            "center_distances",
            "initial_phase_offsets",
        ],
        "hard_constraints": [
            "r = m * z / 2 for every wheel and pinion",
            "center_distance(axis_i, axis_j) = r_i + r_j for every external mesh",
            "omega_j = -omega_i * z_i / z_j for every external mesh",
            "RigidlyAttached(wheel_i, pinion_i) implies equal angular velocity on one arbor",
        ],
        "soft_preferences": [
            "prefer visible gear-size variation without breaking center-distance equations",
            "keep major mesh points visible in top review",
        ],
        "validation_checks": [
            "all output axes are connected to drive through mesh and compound edges",
            "all mesh equations satisfy module and center-distance tolerance",
            "animation directions match mesh parity",
        ],
        "known_failure_modes": [
            "orphan output gear with no path to drive",
            "pitch circles do not touch or overlap incorrectly",
            "compound wheel and pinion are placed on different axes",
        ],
        "repair_strategies": [
            "search a different topology family",
            "recompute center positions from pitch radii",
            "snap compound wheel and pinion to the same arbor axis",
        ],
        "evidence_sources": _sources("WK001", "WK002", "A1", "A15"),
        "formal_model_refs": [
            "r_g = (m_g * z_g) / 2",
            "center_distance(axis_i, axis_j) = r_i + r_j",
            "omega_j = -omega_i * z_i / z_j",
            "omega_out / omega_drive = product_over_mesh_edges(- z_driver_edge / z_driven_edge)",
        ],
        "rule_space_refs": [
            "valid candidates cover straight_chain, offset_chain, branched_outputs, dual_bridge_compact, and regulator_display topology families",
            "invalid_bad_mesh_distance proves mesh center-distance violations are rejected",
        ],
        "promotion_notes": "Strong candidate for a reusable visible gear-train synthesis pattern after tooth-profile and tolerance checks mature.",
    },
    {
        "id": "pivot_supported_by_plate_and_bridge",
        "name": "Pivot Supported By Plate And Bridge",
        "pattern_class": "executable_engineering_pattern",
        "lifecycle_state": "executable_candidate",
        "solved_function": "Constrain a rotating arbor with coaxial lower mainplate support and upper bridge support while leaving only legal Rz rotation.",
        "required_interfaces": [
            "arbor axis",
            "mainplate lower pivot seat",
            "bridge upper pivot seat",
            "support span",
            "report-only axial endshake policy",
        ],
        "generated_components": [
            "lower pivot seat",
            "upper pivot seat",
            "arbor support span",
            "support ledger entry",
        ],
        "generated_features": [
            "coaxial support holes",
            "seat ownership metadata",
            "radial constraint records",
        ],
        "parameter_variables": [
            "pivot_radius",
            "seat_clearance",
            "support_span",
            "bridge_z",
            "endshake_report_state",
        ],
        "hard_constraints": [
            "LowerSupport(mainplate_seat, arbor) must exist for every train arbor",
            "UpperSupport(bridge_seat, arbor) must exist for every train arbor unless explicitly visual-only",
            "lower and upper support seats must be coaxial with Axis(arbor)",
            "support pair constrains Tx/Ty while AllowsMotion(arbor, Rz)",
        ],
        "soft_preferences": [
            "make support bridge visually legible in review mode",
            "group nearby arbors under bridge shapes that remain installable",
        ],
        "validation_checks": [
            "every train arbor has lower and upper support",
            "support seats share the arbor axis",
            "support features are fixed, not part of rotating groups",
        ],
        "known_failure_modes": [
            "a decorative pivot marker hides an unsupported arbor",
            "bridge support hole is near but not coaxial",
            "bridge hole moves with the gear instead of staying fixed",
        ],
        "repair_strategies": [
            "project missing seats from the arbor axis",
            "split bridge groups when one bridge cannot support all arbors cleanly",
            "move support features to fixed mainplate or bridge product",
        ],
        "evidence_sources": _sources("WK001", "WK003", "WK004", "A1", "A15"),
        "formal_model_refs": [
            "LowerSupport(s_l, a) and UpperSupport(s_u, a)",
            "Coaxial(s, Axis(a))",
            "Constrains(s_l, a, Tx/Ty); Constrains(s_u, a, Tx/Ty)",
            "AllowsMotion(a, Rz)",
        ],
        "rule_space_refs": [
            "invalid_missing_upper_support proves unsupported arbors are rejected",
            "valid candidates vary across 1-3 bridge groups while preserving support closure",
        ],
        "promotion_notes": "Candidate for later core support semantics after axial location/endshake is upgraded from report-only.",
    },
    {
        "id": "screw_fastened_bridge_to_mainplate",
        "name": "Screw Fastened Bridge To Mainplate",
        "pattern_class": "executable_engineering_pattern",
        "lifecycle_state": "executable_candidate",
        "solved_function": "Fasten a train bridge to the mainplate through complete screw interfaces instead of decorative floating hardware.",
        "required_interfaces": [
            "bridge body",
            "mainplate receiver features",
            "screw axes",
            "head bearing faces",
            "clearance holes",
        ],
        "generated_components": [
            "train bridge",
            "socket-head screw placeholders",
            "bridge clearance holes",
            "mainplate receiving holes",
        ],
        "generated_features": [
            "head-bearing faces",
            "coaxial screw paths",
            "threaded or receiving mainplate features",
            "bridge-to-mainplate contact faces",
        ],
        "parameter_variables": [
            "screw_count",
            "screw_axis_positions",
            "clearance_hole_diameter",
            "head_seat_diameter",
            "receiver_depth",
        ],
        "hard_constraints": [
            "ScrewFastens(screw, bridge, mainplate) must include head face, clearance hole, and receiver",
            "screw, bridge clearance hole, and mainplate receiver must be coaxial",
            "each bridge must have at least two fastening or locating constraints in V0 review",
            "bridge fixed state must close back to the mainplate, not to a visual proxy",
        ],
        "soft_preferences": [
            "place screws near bridge ends or support lobes",
            "avoid screw heads covering gear mesh contact points",
        ],
        "validation_checks": [
            "screw count matches clearance-hole and receiver count",
            "each screw path terminates in owned mainplate geometry",
            "bridge remains fixed in the animation sidecar",
        ],
        "known_failure_modes": [
            "floating screw does not terminate in a receiving feature",
            "bridge looks attached but has no contact or screw path",
            "single screw underconstrains a bridge in review semantics",
        ],
        "repair_strategies": [
            "generate missing receiver holes before generating screws",
            "add a second screw or locating feature to each bridge group",
            "move screw axes away from moving gear envelopes",
        ],
        "evidence_sources": _sources("WK001", "WK003", "A1", "A15"),
        "formal_model_refs": [
            "ScrewFastens(screw, bridge, mainplate)",
            "HasHeadBearingFace(screw, head_face)",
            "HasClearanceHole(bridge, clearance_hole)",
            "HasReceivingFeature(mainplate, receiver)",
        ],
        "rule_space_refs": [
            "invalid_incomplete_bridge_screws proves bridge screw interface failures are rejected",
            "valid candidates include 1, 2, and 3 bridge groups with complete screw semantics",
        ],
        "promotion_notes": "Reusable for bridge-like fastening once standard screw tables and thread classes are added.",
    },
    {
        "id": "spiral_visual_drive_or_regulator",
        "name": "Spiral Visual Drive Or Regulator",
        "pattern_class": "visual_style_pattern",
        "lifecycle_state": "draft_pattern",
        "solved_function": "Add a decorative spiral that evokes a watch spring/regulator while remaining explicitly visual-only.",
        "required_interfaces": [
            "visual anchor axis",
            "clearance from gear train",
            "out-of-scope real mainspring/escapement declaration",
        ],
        "generated_components": [
            "flat visual spiral",
            "decorative hub",
            "visual clearance envelope",
        ],
        "generated_features": [
            "spiral curve",
            "hub marker",
            "fixed or sidecar-only visual transform",
        ],
        "parameter_variables": [
            "spiral_turns",
            "inner_radius",
            "outer_radius",
            "strip_width",
            "visual_phase",
        ],
        "hard_constraints": [
            "visual-only spiral must not imply real mainspring torque storage",
            "visual-only spiral must not imply real escapement or balance regulation",
            "visual-only spiral must clear all engineered gear and bridge envelopes",
        ],
        "soft_preferences": [
            "use spiral as a recognizable visual anchor",
            "place spiral where it does not hide active transmission edges",
        ],
        "validation_checks": [
            "spiral is tagged VisualOnly(part)",
            "mainspring torque and escapement remain report-only exclusions",
            "spiral geometry clears gear pitch and hand sweep envelopes",
        ],
        "known_failure_modes": [
            "visual spiral is mistaken for validated power source",
            "spiral overlaps gear train or bridge screw head",
            "decorative animation is not declared sidecar-only",
        ],
        "repair_strategies": [
            "rename metadata to visual-only",
            "move or shrink spiral envelope",
            "remove animation if it implies functional regulation",
        ],
        "evidence_sources": _sources("WK005", "A1", "VISUAL"),
        "formal_model_refs": [
            "VisualOnly(part)",
            "ReportOnly(real_mainspring_torque)",
            "ReportOnly(real_escapement_physics)",
        ],
        "rule_space_refs": [
            "style_tags include spiral_visual, but no valid candidate treats the spiral as a torque source",
        ],
        "promotion_notes": "Visual draft only; cannot become an engineering pattern without a separate power-source or regulating-organ formal model.",
    },
    {
        "id": "decorative_bezel_facets",
        "name": "Decorative Bezel Facets",
        "pattern_class": "visual_style_pattern",
        "lifecycle_state": "draft_pattern",
        "solved_function": "Add fixed faceted bezel styling around the case without creating hidden support, motion, or transmission claims.",
        "required_interfaces": [
            "case outer boundary",
            "fixed decorative plane",
            "hand and gear clearance envelopes",
        ],
        "generated_components": [
            "faceted bezel ring",
            "facet markers",
        ],
        "generated_features": [
            "radial decorative facets",
            "outer chamfer rhythm",
            "fixed review material metadata",
        ],
        "parameter_variables": [
            "facet_count",
            "facet_depth",
            "bezel_width",
            "facet_phase",
        ],
        "hard_constraints": [
            "visual-only bezel facets must not imply real motion support",
            "visual-only bezel facets must not imply real case sealing or water resistance",
            "visual-only bezel facets must clear hand sweep and gear envelopes",
        ],
        "soft_preferences": [
            "align facet rhythm with the visual composition",
            "keep decoration subordinate to the mechanism view",
        ],
        "validation_checks": [
            "bezel facets are fixed in the sidecar",
            "decorative ring clears all moving groups",
            "case boundary still encloses the movement review envelope",
        ],
        "known_failure_modes": [
            "decorative geometry is treated as functional bridge or bearing support",
            "facets occlude output hands or gear meshes",
            "facet phase conflicts with bridge screw visibility",
        ],
        "repair_strategies": [
            "mark bezel facets as fixed visual style",
            "increase bezel radius or reduce facet depth",
            "rotate facet phase away from screws and outputs",
        ],
        "evidence_sources": _sources("A1", "VISUAL"),
        "formal_model_refs": [
            "VisualOnly(part)",
            "Fixed(part)",
            "ReportOnly(real_case_sealing)",
        ],
        "rule_space_refs": [
            "rule-space candidates treat style tags separately from topology validity",
        ],
        "promotion_notes": "Visual draft only; no core promotion without real enclosure, sealing, or mounting semantics.",
    },
]


def build_watch_pattern_cards() -> list[dict]:
    """Return Gate A2 watch kinematic pattern cards."""

    return deepcopy(PATTERN_CARDS)


def write_watch_pattern_cards(output_dir: Path) -> list[Path]:
    """Write JSON and Markdown pattern cards under output_dir."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []

    for card in build_watch_pattern_cards():
        json_path = output_dir / f"{card['id']}.json"
        markdown_path = output_dir / f"{card['id']}.md"

        json_path.write_text(
            json.dumps(card, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(_render_markdown(card), encoding="utf-8")
        written_paths.extend([json_path, markdown_path])

    return written_paths


def _render_markdown(card: dict) -> str:
    lines = [
        f"# {card['name']}",
        "",
        f"- ID: `{card['id']}`",
        f"- Pattern Class: `{card['pattern_class']}`",
        f"- Lifecycle State: `{card['lifecycle_state']}`",
        f"- Solved Function: {card['solved_function']}",
        "",
    ]

    section_titles = [
        ("required_interfaces", "Required Interfaces"),
        ("generated_components", "Generated Components"),
        ("generated_features", "Generated Features"),
        ("parameter_variables", "Parameter Variables"),
        ("hard_constraints", "Hard Constraints"),
        ("soft_preferences", "Soft Preferences"),
        ("validation_checks", "Validation Checks"),
        ("known_failure_modes", "Known Failure Modes"),
        ("repair_strategies", "Repair Strategies"),
        ("formal_model_refs", "Formal Model References"),
        ("rule_space_refs", "Rule-Space References"),
    ]
    for key, title in section_titles:
        lines.extend([f"## {title}", ""])
        lines.extend(f"- {item}" for item in card[key])
        lines.append("")

    lines.extend(["## Evidence Sources", ""])
    for source in card["evidence_sources"]:
        lines.append(f"- `{source['id']}` ({source['type']}): {source['notes']}")

    lines.extend(["", "## Promotion Notes", "", card["promotion_notes"], ""])
    return "\n".join(lines)
