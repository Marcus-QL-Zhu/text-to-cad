import json
import os
from pathlib import Path
import struct
from typing import Any

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT_ENV = "WATCH_NATIVE_ARTIFACT_ROOT"
PATTERN_SEEDS = {1: 731, 2: 8459, 3: 731}


def _fixture_root() -> Path:
    raw_root = os.environ.get(FIXTURE_ROOT_ENV)
    if not raw_root:
        pytest.skip(
            f"native watch artifacts are external integration fixtures; set {FIXTURE_ROOT_ENV} "
            "to the root produced by the three public generate_watch CLI runs"
        )
    root = Path(raw_root).expanduser().resolve()
    assert root.is_dir(), f"{FIXTURE_ROOT_ENV} is not a directory: {root}"
    assert not root.is_relative_to(REPOSITORY_ROOT), f"native artifact fixtures must be outside the repository: {root}"
    return root


def _run_record(root: Path, pattern: int) -> tuple[Path, dict[str, Any]]:
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in root.rglob("run_record.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("pattern") == pattern:
            matches.append((path, payload))
    assert len(matches) == 1, (
        f"expected one Pattern {pattern} run_record.json under {root}, "
        f"found {[str(path) for path, _ in matches]}"
    )
    return matches[0]


def _recorded_step_path(record_path: Path, record: dict[str, Any]) -> Path:
    recorded = Path(str(record.get("step_path") or ""))
    step_path = recorded if recorded.is_file() else record_path.parent / recorded.name
    assert step_path.is_file(), f"recorded STEP does not exist: {recorded} (fixture record: {record_path})"
    return step_path.resolve()


def _read_glb(glb_path: Path) -> tuple[dict[str, Any], bytes]:
    payload = glb_path.read_bytes()
    assert len(payload) >= 20, f"GLB is too small: {glb_path}"
    magic, version, declared_length = struct.unpack_from("<4sII", payload, 0)
    assert magic == b"glTF" and version == 2, f"not a GLB v2 file: {glb_path}"
    assert declared_length <= len(payload), f"truncated GLB: {glb_path}"

    offset = 12
    gltf: dict[str, Any] | None = None
    binary = b""
    while offset + 8 <= declared_length:
        chunk_length, chunk_type = struct.unpack_from("<I4s", payload, offset)
        offset += 8
        chunk = payload[offset : offset + chunk_length]
        assert len(chunk) == chunk_length, f"truncated GLB chunk: {glb_path}"
        offset += chunk_length
        if chunk_type == b"JSON":
            decoded = json.loads(chunk.decode("utf-8").rstrip(" \t\r\n\0"))
            assert isinstance(decoded, dict), f"GLB JSON chunk is not an object: {glb_path}"
            gltf = decoded
        elif chunk_type == b"BIN\0":
            binary = chunk
    assert gltf is not None, f"GLB has no JSON chunk: {glb_path}"
    return gltf, binary


def _step_topology_index(gltf: dict[str, Any], binary: bytes, glb_path: Path) -> dict[str, Any]:
    assert "STEP_topology" in gltf.get("extensionsUsed", []), f"STEP_topology is not declared: {glb_path}"
    extension = gltf.get("extensions", {}).get("STEP_topology")
    assert isinstance(extension, dict), f"STEP_topology extension is missing: {glb_path}"
    view_index = extension.get("indexView")
    views = gltf.get("bufferViews")
    assert isinstance(view_index, int) and isinstance(views, list) and 0 <= view_index < len(views), (
        f"STEP_topology indexView is invalid: {glb_path}"
    )
    view = views[view_index]
    assert isinstance(view, dict) and int(view.get("buffer", 0)) == 0, f"STEP_topology indexView is invalid: {glb_path}"
    start = int(view.get("byteOffset", 0))
    length = int(view.get("byteLength", 0))
    assert start >= 0 and length > 0 and start + length <= len(binary), (
        f"STEP_topology indexView is out of range: {glb_path}"
    )
    index = json.loads(binary[start : start + length].decode("utf-8"))
    assert isinstance(index, dict), f"STEP_topology index is not an object: {glb_path}"
    return index


def _occurrence_ids(topology: dict[str, Any]) -> set[str]:
    columns = topology.get("tables", {}).get("occurrenceColumns")
    rows = topology.get("occurrences")
    assert isinstance(columns, list) and "id" in columns, "STEP_topology occurrence columns are missing id"
    assert isinstance(rows, list) and rows, "STEP_topology occurrences are empty"
    id_index = columns.index("id")
    return {str(row[id_index]) for row in rows if isinstance(row, list) and len(row) > id_index and row[id_index]}


def _assembly_nodes(root: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    pending = [root]
    while pending:
        node = pending.pop()
        nodes.append(node)
        children = node.get("children", [])
        assert isinstance(children, list), f"assembly node children are not a list: {node.get('id')}"
        pending.extend(child for child in children if isinstance(child, dict))
    return nodes


def _resolved_leaf_ids(feature: dict[str, Any], nodes: list[dict[str, Any]], leaf_ids: set[str]) -> set[str]:
    selectors: set[str] = set()
    part_ids = feature.get("partIds")
    if isinstance(part_ids, list):
        selectors.update(str(value).lstrip("#") for value in part_ids if value)
    for key in ("ref", "selector"):
        if feature.get(key):
            selectors.add(str(feature[key]).lstrip("#"))
    raw_selectors = feature.get("selectors")
    if isinstance(raw_selectors, list):
        selectors.update(str(value).lstrip("#") for value in raw_selectors if value and value != "__model__")

    resolved = {
        leaf_id
        for selector in selectors
        for leaf_id in leaf_ids
        if leaf_id == selector or leaf_id.startswith(f"{selector}.")
    }
    for node in nodes:
        identities = {str(node.get("id") or ""), str(node.get("occurrenceId") or "")}
        if selectors & identities:
            node_leaf_ids = node.get("leafPartIds")
            if isinstance(node_leaf_ids, list):
                resolved.update(str(value) for value in node_leaf_ids if str(value) in leaf_ids)
    return resolved


def _moving_feature_ids(motion: dict[str, Any]) -> set[str]:
    groups = motion.get("moving_groups")
    assert isinstance(groups, list) and groups, "motion JSON has no moving_groups"
    moving = {
        str(feature_id)
        for group in groups
        if isinstance(group, dict)
        for feature_id in group.get("feature_ids", [])
    }
    assert moving, "motion JSON declares no moving features"
    return moving


def _embedded_step_module_motion(step_module: str) -> dict[str, Any]:
    marker = "const WATCH_POWER_CHAIN_MOTION = "
    start = step_module.index(marker) + len(marker)
    payload, _ = json.JSONDecoder().raw_decode(step_module, start)
    assert isinstance(payload, dict), "STEP module motion payload is not an object"
    return payload


def _glb_material_alphas_by_occurrence(gltf: dict[str, Any]) -> dict[str, set[float]]:
    materials = gltf.get("materials", [])
    meshes = gltf.get("meshes", [])
    result: dict[str, set[float]] = {}
    for node in gltf.get("nodes", []):
        if not isinstance(node, dict) or not isinstance(node.get("mesh"), int):
            continue
        mesh_index = node["mesh"]
        if not (0 <= mesh_index < len(meshes)) or not isinstance(meshes[mesh_index], dict):
            continue
        occurrence_id = str(node.get("extras", {}).get("cadOccurrenceId") or node.get("name") or "")
        if not occurrence_id:
            continue
        for primitive in meshes[mesh_index].get("primitives", []):
            material_index = primitive.get("material") if isinstance(primitive, dict) else None
            if not isinstance(material_index, int) or not (0 <= material_index < len(materials)):
                continue
            color = materials[material_index].get("pbrMetallicRoughness", {}).get("baseColorFactor", [])
            alpha = float(color[3]) if isinstance(color, list) and len(color) >= 4 else 1.0
            result.setdefault(occurrence_id, set()).add(alpha)
    return result


@pytest.mark.parametrize("pattern", [1, 2, 3])
def test_native_watch_artifact_contract(pattern: int) -> None:
    fixture_root = _fixture_root()
    record_path, record = _run_record(fixture_root, pattern)
    expected_seed = PATTERN_SEEDS[pattern]
    assert record.get("status") == "pass"
    assert record.get("requested_seed") == expected_seed
    assert record.get("successful_seed") == expected_seed
    assert record.get("attempted_seeds") == [expected_seed]

    step_path = _recorded_step_path(record_path, record)
    motion_path = step_path.with_name(f"{step_path.stem}.motion.json")
    step_module_path = step_path.with_name(f".{step_path.name}.js")
    glb_path = step_path.with_name(f".{step_path.name}.glb")
    for label, artifact_path in (
        ("STEP", step_path),
        ("motion JSON", motion_path),
        ("STEP module JavaScript", step_module_path),
        ("native GLB/topology", glb_path),
    ):
        assert artifact_path.is_file() and artifact_path.stat().st_size > 0, (
            f"Pattern {pattern} {label} is missing: {artifact_path}"
        )

    motion = json.loads(motion_path.read_text(encoding="utf-8"))
    step_module = step_module_path.read_text(encoding="utf-8")
    assert _embedded_step_module_motion(step_module) == motion, (
        f"Pattern {pattern} STEP module motion differs from native motion JSON"
    )
    gltf, binary = _read_glb(glb_path)
    topology = _step_topology_index(gltf, binary, glb_path)
    assembly = topology.get("assembly")
    assert topology.get("entryKind") == "assembly", f"Pattern {pattern} topology is not an assembly"
    assert isinstance(assembly, dict), f"Pattern {pattern} STEP_topology has no assembly section"
    root = assembly.get("root")
    assert isinstance(root, dict), f"Pattern {pattern} assembly has no root"
    leaf_part_ids = root.get("leafPartIds")
    assert isinstance(leaf_part_ids, list) and leaf_part_ids, f"Pattern {pattern} assembly root has no leafPartIds"
    leaf_ids = {str(value) for value in leaf_part_ids}
    occurrence_ids = _occurrence_ids(topology)
    assert leaf_ids <= occurrence_ids, f"Pattern {pattern} assembly leafPartIds are absent from topology occurrences"

    nodes = _assembly_nodes(root)
    features = motion.get("features")
    assert isinstance(features, dict), f"Pattern {pattern} motion JSON has no features"
    moving_feature_ids = _moving_feature_ids(motion)
    fixed_feature_list = motion.get("fixed_features")
    assert isinstance(fixed_feature_list, list), f"Pattern {pattern} motion JSON has no fixed_features"
    fixed_feature_ids = {str(feature_id) for feature_id in fixed_feature_list}
    moving_feature_list = [
        str(feature_id)
        for group in motion["moving_groups"]
        for feature_id in group.get("feature_ids", [])
    ]
    assert len(moving_feature_list) == len(moving_feature_ids), (
        f"Pattern {pattern} duplicates a feature across moving groups"
    )
    assert len(fixed_feature_list) == len(fixed_feature_ids), (
        f"Pattern {pattern} duplicates a fixed feature"
    )
    assert moving_feature_ids.isdisjoint(fixed_feature_ids), (
        f"Pattern {pattern} classifies features as both moving and fixed: "
        f"{sorted(moving_feature_ids & fixed_feature_ids)}"
    )
    classified_feature_ids = moving_feature_ids | fixed_feature_ids
    assert classified_feature_ids == set(features), (
        f"Pattern {pattern} 6DoF coverage differs from visible features: "
        f"missing={sorted(set(features) - classified_feature_ids)}, "
        f"extra={sorted(classified_feature_ids - set(features))}"
    )

    intent = motion.get("dynamic_6dof_intent")
    assert isinstance(intent, dict), f"Pattern {pattern} motion JSON has no dynamic_6dof_intent"
    intent_moving_ids = {
        str(feature_id)
        for group in intent.get("moving_groups", [])
        for feature_id in group.get("feature_ids", [])
    }
    intent_fixed_ids = {
        str(feature.get("feature_id"))
        for feature in intent.get("fixed_features", [])
        if isinstance(feature, dict)
    }
    assert intent_moving_ids == moving_feature_ids
    assert intent_fixed_ids == fixed_feature_ids
    assert all(group.get("allowed_dof") == ["rz"] for group in intent["moving_groups"])
    assert all(
        feature.get("locked_dof") == ["tx", "ty", "tz", "rx", "ry", "rz"]
        for feature in intent["fixed_features"]
    )

    for feature_id in sorted(classified_feature_ids):
        feature = features.get(feature_id)
        assert isinstance(feature, dict), f"Pattern {pattern} classified feature is undeclared: {feature_id}"
        resolved = _resolved_leaf_ids(feature, nodes, leaf_ids)
        assert resolved, (
            f"Pattern {pattern} classified feature does not resolve to an assembly leaf: "
            f"{feature_id} -> {feature}"
        )
        assert feature_id in step_module, f"Pattern {pattern} STEP module omits classified feature: {feature_id}"

    contracts = motion.get("semantic_material_contracts")
    visual_materials = motion.get("visual_materials")
    assert isinstance(contracts, dict) and isinstance(visual_materials, dict)
    bridge_ids = sorted(
        feature_id
        for feature_id, contract in contracts.items()
        if isinstance(contract, dict) and contract.get("role") == "translucent_bridge_support"
    )
    assert bridge_ids == ["barrel_bridge", "escapement_bridge", "train_bridge"]
    glb_alphas = _glb_material_alphas_by_occurrence(gltf)
    for bridge_id in bridge_ids:
        contract = contracts[bridge_id]
        visual = visual_materials.get(bridge_id)
        assert isinstance(visual, dict) and visual == contract.get("material"), (
            f"Pattern {pattern} bridge material contract differs: {bridge_id}"
        )
        rgba = visual.get("rgba")
        assert isinstance(rgba, list) and len(rgba) == 4
        declared_alpha = float(rgba[3])
        assert 0.0 < declared_alpha < 1.0
        assert declared_alpha == pytest.approx(0.8)
        feature = features.get(bridge_id)
        assert isinstance(feature, dict) and feature.get("ref") == contract.get("visible_ref")
        resolved = _resolved_leaf_ids(feature, nodes, leaf_ids)
        rendered_alphas = {alpha for leaf_id in resolved for alpha in glb_alphas.get(leaf_id, set())}
        assert rendered_alphas, (
            f"Pattern {pattern} bridge has no rendered GLB material: "
            f"{bridge_id} -> {sorted(resolved)}"
        )
        assert any(alpha == pytest.approx(declared_alpha) for alpha in rendered_alphas), (
            f"Pattern {pattern} bridge opacity differs from its material contract: "
            f"{bridge_id} declared={declared_alpha} rendered={sorted(rendered_alphas)}"
        )
