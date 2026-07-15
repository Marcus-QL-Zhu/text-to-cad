# Watch Generator Clean Upstream Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a clean branch based on the latest `earthtojake/text-to-cad` main branch that contains the three accepted mechanical-watch generators, their semantic sidecars and validation gates, the complete attributed third-party Swiss lever escapement, and no generated watch or reducer output artifacts.

**Architecture:** Preserve the accepted watch generator implementation from `codex/watch-separate-display@5be78528` and integrate it into the native `text-to-cad` repository layout. Reuse the upstream CAD, STEP-to-GLB, assembly-topology, material, animation, render, and CAD Explorer pipeline without copying or reimplementing it. Add only thin public entry points, model-specific dependency metadata, provenance checks, release hygiene, and retry orchestration.

**Tech Stack:** Python 3.11, build123d, OpenCascade, NumPy, SciPy, Matplotlib, Pillow, native text-to-cad CAD skill and CAD Explorer, pytest/unittest, Git LFS for third-party CAD payloads.

## Global Constraints

- Base the integration branch on the current `origin/main`, not on the diverged local `main` history.
- Treat `codex/watch-separate-display@5be78528` as the accepted watch-generator source baseline.
- Preserve accepted geometry, solver behavior, semantic sidecars, material contracts, motion bindings, and hard validation behavior.
- Public Pattern 1 maps to the original central hour/minute plus off-center seconds implementation.
- Public Pattern 2 maps to the original separate serial hour/minute implementation.
- Public Pattern 3 is the accepted original Pattern 4 independent hour/minute hard-gated implementation, renamed throughout the clean branch as Pattern 3.
- Remove the original early Pattern 3 implementation from the clean branch; do not publish it or retain a second competing independent-display package.
- Do not split or refactor `power_chain_mvp.py`, `partitioned_bridge_stage.py`, `bridge_xy_partition.py`, or other accepted shared modules during this migration.
- Do not reorganize solver, geometry, semantic, material, animation, or artifact-writing responsibilities during this migration.
- Do not copy or reimplement STEP-to-GLB conversion, assembly topology, browser rendering, or CAD Explorer.
- Do not track files generated under `models/watch_kinematic/outputs/` or `models/planetary_reducer/outputs/`.
- Delete local generated watch and reducer outputs after the source snapshot and manifest are complete; do not back them up.
- Keep the complete Swiss lever escapement payload in the GitHub branch because the declared watch power chain is incomplete without it.
- The Swiss lever escapement remains under its original creator's/GrabCAD terms and is excluded from the repository's root software license.
- Keep all third-party reference assets outside generated-output directories.
- Any failed solver or hard validator attempt must not publish a final STEP; retry orchestration may select another seed up to the configured attempt limit.
- Generated models default to an OS temporary directory unless the user explicitly supplies `--output-dir`.
- Before user review, generate native text-to-cad Explorer artifacts and perform agent visual checks from top and isometric views.

---

## File Structure

The clean branch will use this structure:

```text
models/watch_kinematic/
  README.md
  requirements.txt
  generate_watch.py
  watch_kinematic/
    ...accepted shared generator modules...
    pattern_cards/
      central_hour_minute_offcenter_seconds/
      separate_hour_minute_no_seconds/
      independent_hour_minute_no_seconds/
  references/
    escapement/
      swiss_lever_grabcad_snapshot_15/
        README.md
        SOURCE.json
        LICENSE.grabcad.md
        ...complete original payload...
  tests/
    ...accepted generator tests...
    test_public_generate_watch.py
    test_release_hygiene.py
  outputs/
    .gitkeep
THIRD_PARTY_ASSETS.md
docs/design_patterns/watch_generator/
  architecture.md
  patterns.md
  extension_guide.md
```

The final branch contains exactly three canonical pattern packages. The accepted original Pattern 4 code becomes the sole `independent_hour_minute_no_seconds` package and is identified as Pattern 3 in code, sidecars, filenames, reports and documentation.

---

### Task 1: Freeze the Accepted Source Baseline and Migration Manifest

**Files:**
- Create external snapshot: `C:/Users/wande/Documents/text-to-cad-source-snapshot-2026-07-14/`
- Create: `docs/design_patterns/watch_generator/migration_source_manifest.json`
- Create: `docs/design_patterns/watch_generator/migration_inventory.md`

**Interfaces:**
- Consumes: Git refs `40a3729e` and `5be78528`, local worktree status, upstream `origin/main`.
- Produces: an auditable list of source files to copy and generated paths to discard.

- [ ] **Step 1: Refresh upstream and record immutable source refs**

Run:

```powershell
git fetch origin main --prune
git rev-parse main
git rev-parse codex/watch-separate-display
git rev-parse origin/main
```

Expected: local main resolves to `40a3729e...`, accepted watch source resolves to `5be78528...`, and upstream main resolves independently.

- [ ] **Step 2: Generate a source-only inventory**

Create `migration_source_manifest.json` using the refreshed upstream SHA:

```powershell
$upstream = (git rev-parse origin/main).Trim()
$manifest = [ordered]@{
  accepted_source_commit = "5be7852844a3f4c5698a737eba81c026e96ced16"
  upstream_base_commit = $upstream
  include_roots = @(
    "models/watch_kinematic/watch_kinematic",
    "models/watch_kinematic/tests",
    "models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15"
  )
  exclude_roots = @(
    "models/watch_kinematic/outputs",
    "models/planetary_reducer/outputs"
  )
  public_pattern_mapping = [ordered]@{
    "1" = "central_hour_minute_offcenter_seconds"
    "2" = "separate_hour_minute_no_seconds"
    "3" = "independent_hour_minute_no_seconds"
  }
  source_pattern_mapping = [ordered]@{
    independent_hour_minute_no_seconds = "accepted original pattern4_independent_hour_minute_no_seconds implementation"
  }
}
New-Item -ItemType Directory -Force docs/design_patterns/watch_generator | Out-Null
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 docs/design_patterns/watch_generator/migration_source_manifest.json
```

- [ ] **Step 3: Document the inventory decisions**

`migration_inventory.md` must list:

```text
KEEP: accepted watch source, tests, sidecar builders, solver and validation code.
KEEP: complete GrabCAD escapement payload plus provenance.
REUSE UPSTREAM: CAD skill, STEP/GLB pipeline, assembly topology, materials, motion runtime, Explorer.
DROP: all watch/reducer generated outputs, historical candidate batches, local screenshots and dashboards.
DROP: standalone Ontology-based-Watch-Generator transcode and Explorer reimplementations.
DEFER: reducer, EFEM, reference-assembly and design-pattern-factory work.
```

- [ ] **Step 4: Create a complete source/reference snapshot without generated outputs**

```powershell
$snapshot = "C:/Users/wande/Documents/text-to-cad-source-snapshot-2026-07-14"
$main = "C:/Users/wande/Documents/text-to-cad"
$watch = "C:/Users/wande/.config/superpowers/worktrees/text-to-cad/codex-watch-separate-display"
New-Item -ItemType Directory -Force "$snapshot/main-worktree", "$snapshot/watch-worktree" | Out-Null

robocopy $main "$snapshot/main-worktree" /E `
  /XD "$main/.git" "$main/.venv" "$main/node_modules" "$main/.pytest_cache" `
      "$main/models/watch_kinematic/outputs" "$main/models/planetary_reducer/outputs" `
  /XF *.pyc
if ($LASTEXITCODE -gt 7) { throw "main source snapshot failed: $LASTEXITCODE" }

robocopy $watch "$snapshot/watch-worktree" /E `
  /XD "$watch/.git" "$watch/.venv" "$watch/node_modules" "$watch/.pytest_cache" `
      "$watch/models/watch_kinematic/outputs" "$watch/models/planetary_reducer/outputs" `
  /XF *.pyc
if ($LASTEXITCODE -gt 7) { throw "watch source snapshot failed: $LASTEXITCODE" }

git -C $main status --short --branch | Set-Content "$snapshot/main-status.txt"
git -C $watch status --short --branch | Set-Content "$snapshot/watch-status.txt"
git -C $main show-ref | Set-Content "$snapshot/git-refs.txt"
```

Expected: both source trees, all downloaded third-party references and all uncommitted non-output work are copied; neither generated-output directory exists in the snapshot.

- [ ] **Step 5: Verify the snapshot exclusions**

```powershell
if (Test-Path "$snapshot/main-worktree/models/watch_kinematic/outputs") { throw "watch outputs were copied" }
if (Test-Path "$snapshot/main-worktree/models/planetary_reducer/outputs") { throw "reducer outputs were copied" }
if (!(Test-Path "$snapshot/watch-worktree/models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15/Escapement Model.STEP")) { throw "escapement reference missing" }
```

Expected: generated outputs are absent and the third-party escapement remains present.

- [ ] **Step 6: Verify the manifest contains no generated output path in `include_roots`**

Run:

```powershell
python -c "import json; p=json.load(open('docs/design_patterns/watch_generator/migration_source_manifest.json')); assert all('/outputs' not in x for x in p['include_roots'])"
```

Expected: exit code `0`.

- [ ] **Step 7: Commit the migration inventory**

```powershell
git add docs/design_patterns/watch_generator/migration_source_manifest.json docs/design_patterns/watch_generator/migration_inventory.md
git commit -m "docs: inventory accepted watch generator source"
```

---

### Task 2: Create the Upstream-Based Integration Worktree

**Files:**
- Create worktree: `C:/Users/wande/.config/superpowers/worktrees/text-to-cad/codex-watch-generator-upstream`

**Interfaces:**
- Consumes: latest `origin/main` and Task 1 manifest.
- Produces: clean branch `codex/watch-generator-upstream-integration`.

- [ ] **Step 1: Fetch current upstream refs**

```powershell
git fetch origin main --prune
```

Expected: `origin/main` updates successfully without changing existing worktrees.

- [ ] **Step 2: Create the clean branch and isolated worktree**

```powershell
git worktree add -b codex/watch-generator-upstream-integration C:/Users/wande/.config/superpowers/worktrees/text-to-cad/codex-watch-generator-upstream origin/main
```

Expected: the new worktree is clean and `git log -1` matches `origin/main`.

- [ ] **Step 3: Copy the plan and migration manifest into the clean branch**

Use `Copy-Item` only for these documentation files. Do not copy either old repository root wholesale.

- [ ] **Step 4: Confirm the branch contains no historical generated outputs**

```powershell
git ls-files models/watch_kinematic/outputs models/planetary_reducer/outputs
```

Expected: no generated file output, or only an upstream `.gitkeep`.

- [ ] **Step 5: Commit the branch bootstrap documentation**

```powershell
git add docs/superpowers/plans/2026-07-14-watch-generator-clean-upstream-integration.md docs/design_patterns/watch_generator
git commit -m "docs: bootstrap clean watch generator integration"
```

---

### Task 3: Add Release Hygiene Before Copying Generator Code

**Files:**
- Modify: `.gitignore`
- Create: `models/watch_kinematic/outputs/.gitkeep`
- Create: `models/watch_kinematic/tests/test_release_hygiene.py`

**Interfaces:**
- Produces: blocking rules that prevent generated watch/reducer artifacts from entering the clean branch.

- [ ] **Step 1: Write the failing hygiene test**

```python
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]


def tracked_files(*paths: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line and not line.endswith("/.gitkeep")]


def test_generated_model_outputs_are_not_tracked():
    assert tracked_files(
        "models/watch_kinematic/outputs",
        "models/planetary_reducer/outputs",
    ) == []
```

- [ ] **Step 2: Run the test**

```powershell
python -m pytest models/watch_kinematic/tests/test_release_hygiene.py -v
```

Expected: fail until the output policy and directories are present.

- [ ] **Step 3: Add precise ignore rules**

Append to `.gitignore`:

```gitignore
# Reproducible generated CAD outputs
models/watch_kinematic/outputs/*
!models/watch_kinematic/outputs/.gitkeep
models/planetary_reducer/outputs/*
!models/planetary_reducer/outputs/.gitkeep

# Python runtime caches
**/__pycache__/
*.py[cod]
```

- [ ] **Step 4: Re-run the hygiene test**

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add .gitignore models/watch_kinematic/outputs/.gitkeep models/watch_kinematic/tests/test_release_hygiene.py
git commit -m "chore: exclude reproducible CAD outputs"
```

---

### Task 4: Copy the Accepted Watch Generator Without Rewriting It

**Files:**
- Create: `models/watch_kinematic/watch_kinematic/**`
- Create: `models/watch_kinematic/tests/test_*.py`
- Create: `models/watch_kinematic/README.md`

**Interfaces:**
- Consumes: exact files from `codex/watch-separate-display@5be78528`.
- Produces: native `models.watch_kinematic.watch_kinematic` modules and accepted test suite.

- [ ] **Step 1: Export only source and tests from the accepted commit**

Use Git archive from the immutable commit:

```powershell
$archive = "$env:TEMP/watch-generator-source-5be78528.tar"
git archive --format=tar --output=$archive 5be7852844a3f4c5698a737eba81c026e96ced16 models/watch_kinematic/watch_kinematic models/watch_kinematic/tests
tar -xf $archive -C C:/Users/wande/.config/superpowers/worktrees/text-to-cad/codex-watch-generator-upstream
```

Expected: source and tests appear; `models/watch_kinematic/outputs` remains empty.

- [ ] **Step 2: Verify source-file parity**

Run from the clean worktree:

```powershell
@'
import subprocess
from pathlib import Path

root = Path.cwd()
listing = subprocess.run(
    ["git", "ls-tree", "-r", "--name-only", "5be7852844a3f4c5698a737eba81c026e96ced16", "models/watch_kinematic/watch_kinematic", "models/watch_kinematic/tests"],
    check=True,
    capture_output=True,
    text=True,
).stdout.splitlines()
paths = [Path(item) for item in listing if item.endswith(".py")]
for path in paths:
    expected = subprocess.run(
        ["git", "show", f"5be7852844a3f4c5698a737eba81c026e96ced16:{path.as_posix()}"],
        check=True,
        capture_output=True,
    ).stdout
    actual = (root / path).read_bytes()
    if actual != expected:
        raise SystemExit(f"source mismatch: {path}")
print(f"verified {len(paths)} source files")
'@ | python -
```

Expected: all copied source and accepted test files match exactly.

- [ ] **Step 3: Run import smoke tests**

```powershell
python -c "from models.watch_kinematic.watch_kinematic.partitioned_bridge_stage import build_partitioned_bridge_stage, build_separate_display_partitioned_bridge_stage, build_pattern4_independent_display_complete_model; print('watch imports ok')"
```

Expected: `watch imports ok`.

- [ ] **Step 4: Run accepted unit tests that do not emit full STEP files**

```powershell
python -m pytest models/watch_kinematic/tests/test_current_pattern_solver.py models/watch_kinematic/tests/test_separate_display_pattern.py models/watch_kinematic/tests/test_pattern4_independent_display_pattern.py models/watch_kinematic/tests/test_gear_case_clearance.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the unchanged accepted implementation**

```powershell
git add models/watch_kinematic/watch_kinematic models/watch_kinematic/tests models/watch_kinematic/README.md
git commit -m "feat: add accepted ontology watch generators"
```

---

### Task 5: Collapse the Historical Pattern 3 and Pattern 4 Overlap

**Files:**
- Delete: `models/watch_kinematic/watch_kinematic/pattern_cards/independent_hour_minute_no_seconds/**` from the early implementation.
- Rename: `models/watch_kinematic/watch_kinematic/pattern_cards/pattern4_independent_hour_minute_no_seconds/` to `models/watch_kinematic/watch_kinematic/pattern_cards/independent_hour_minute_no_seconds/`.
- Delete: `models/watch_kinematic/watch_kinematic/independent_display_pattern.py` from the early implementation.
- Rename: `models/watch_kinematic/watch_kinematic/pattern4_independent_display_pattern.py` to `models/watch_kinematic/watch_kinematic/independent_display_pattern.py`.
- Modify: `models/watch_kinematic/watch_kinematic/partitioned_bridge_stage.py`.
- Modify: `models/watch_kinematic/watch_kinematic/power_chain_mvp.py` only where imports or Pattern 3 identifiers require it.
- Delete: `models/watch_kinematic/tests/test_independent_display_pattern.py` from the early implementation.
- Rename: `models/watch_kinematic/tests/test_pattern4_independent_display_pattern.py` to `models/watch_kinematic/tests/test_independent_display_pattern.py`.
- Modify: `models/watch_kinematic/tests/test_partitioned_bridge_stage.py`.

**Interfaces:**
- Consumes: accepted original Pattern 4 implementation copied in Task 4.
- Produces: one canonical Pattern 3 implementation with no Pattern 4 public or internal identity.

- [ ] **Step 1: Add a failing namespace test**

Create these assertions in `test_independent_display_pattern.py` before renaming the implementation:

```python
from pathlib import Path


def test_independent_display_is_canonical_pattern_03():
    card = get_pattern_card()
    assert card["id"] == "watch_pattern_03_independent_hour_minute_no_seconds_v1"
    assert card["name"] == "Pattern 3 - Independent Hour And Minute Display Without Seconds"


def test_no_pattern4_namespace_remains_in_watch_source():
    root = Path("models/watch_kinematic/watch_kinematic")
    matches = []
    for path in root.rglob("*.py"):
        if "pattern4" in path.name.lower() or "pattern 4" in path.read_text(encoding="utf-8").lower():
            matches.append(str(path))
    assert matches == []
```

- [ ] **Step 2: Run the namespace test and verify failure**

```powershell
python -m pytest models/watch_kinematic/tests/test_independent_display_pattern.py -v
```

Expected: FAIL because the accepted implementation still uses Pattern 4 names.

- [ ] **Step 3: Remove the superseded early implementation**

Use `git rm` only on the early package and its old facade/test listed above. Confirm the accepted original Pattern 4 package still exists before moving it.

- [ ] **Step 4: Rename the accepted implementation into the canonical Pattern 3 paths**

```powershell
git mv models/watch_kinematic/watch_kinematic/pattern_cards/pattern4_independent_hour_minute_no_seconds models/watch_kinematic/watch_kinematic/pattern_cards/independent_hour_minute_no_seconds
git mv models/watch_kinematic/watch_kinematic/pattern4_independent_display_pattern.py models/watch_kinematic/watch_kinematic/independent_display_pattern.py
git mv models/watch_kinematic/tests/test_pattern4_independent_display_pattern.py models/watch_kinematic/tests/test_independent_display_pattern.py
```

- [ ] **Step 5: Rename only Pattern identity symbols**

Apply these exact identity changes without moving behavior between modules:

```text
pattern4_independent_hour_minute_no_seconds_v1 -> watch_pattern_03_independent_hour_minute_no_seconds_v1
build_pattern4_independent_display_complete_model -> build_pattern3_independent_display_complete_model
_pattern4_hard_gate_report -> _pattern3_hard_gate_report
_pattern4_evidence_payload -> _pattern3_evidence_payload
_retarget_independent_display_validation_for_pattern4 -> _retarget_independent_display_validation_for_pattern3
_retarget_independent_display_semantic_for_pattern4 -> _retarget_independent_display_semantic_for_pattern3
watch_power_chain_pattern4_independent_display_with_analytic_partitioned_bridges.step -> watch_power_chain_pattern3_independent_display_with_analytic_partitioned_bridges.step
pattern4_independent_display_complete_model_report.json -> pattern3_independent_display_complete_model_report.json
```

Change user-facing `Pattern 4` text to `Pattern 3`. Do not alter equations, geometry constants, solver branches, material values, motion formulas, validation thresholds or sidecar payload content beyond the pattern identity keys.

- [ ] **Step 6: Run focused naming and behavior tests**

```powershell
python -m pytest models/watch_kinematic/tests/test_independent_display_pattern.py models/watch_kinematic/tests/test_partitioned_bridge_stage.py -v
```

Expected: PASS and no `pattern4` namespace remains under `models/watch_kinematic/watch_kinematic`.

- [ ] **Step 7: Commit the targeted naming cleanup**

```powershell
git add models/watch_kinematic/watch_kinematic models/watch_kinematic/tests
git commit -m "refactor: promote accepted watch Pattern 4 to Pattern 3"
```

---

### Task 6: Include and Govern the Complete GrabCAD Escapement

**Files:**
- Create: `models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15/**`
- Create: `models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15/README.md`
- Create: `models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15/SOURCE.json`
- Create: `models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15/LICENSE.grabcad.md`
- Create: `THIRD_PARTY_ASSETS.md`
- Create: `models/watch_kinematic/tests/test_third_party_escapement.py`

**Interfaces:**
- Consumes: complete original payload at the accepted commit.
- Produces: runtime-complete escapement assembly plus machine-verifiable provenance.

- [ ] **Step 1: Write the failing provenance and completeness tests**

```python
import hashlib
import json
from pathlib import Path


ASSET = Path("models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15")


def test_complete_escapement_payload_is_published():
    source = json.loads((ASSET / "SOURCE.json").read_text(encoding="utf-8"))
    assert source["creator"] == "David Velez"
    assert source["source_url"] == "https://grabcad.com/library/swiss-lever-watch-escapement-model-1"
    assert (ASSET / "Escapement Model.STEP").exists()
    for relative_path, expected in source["files"].items():
        actual = hashlib.sha256((ASSET / relative_path).read_bytes()).hexdigest()
        assert actual == expected


def test_root_license_excludes_grabcad_payload():
    notice = Path("THIRD_PARTY_ASSETS.md").read_text(encoding="utf-8")
    assert "David Velez" in notice
    assert "not covered by the repository license" in notice
```

- [ ] **Step 2: Copy the complete payload from the accepted commit**

```powershell
$archive = "$env:TEMP/watch-escapement-source-5be78528.tar"
git archive --format=tar --output=$archive 5be7852844a3f4c5698a737eba81c026e96ced16 models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15
tar -xf $archive -C C:/Users/wande/.config/superpowers/worktrees/text-to-cad/codex-watch-generator-upstream
```

Expected: STEP, STL, DXF, OpenSCAD, images and text files are all present.

- [ ] **Step 3: Add the exact source record**

`SOURCE.json` must record:

```json
{
  "title": "Swiss Lever Watch Escapement Model",
  "creator": "David Velez",
  "source_url": "https://grabcad.com/library/swiss-lever-watch-escapement-model-1",
  "published_date": "2020-11-16",
  "snapshot_name": "swiss-lever-watch-escapement-model-1.snapshot.15.zip",
  "snapshot_sha256": "8c7a49df842f35cd748c0d7c5ffc0b3c118b6b5de0543bacb73b4683c3c35bff",
  "usage_policy": "GrabCAD attributed non-commercial public use; commercial public use requires creator permission",
  "files": {}
}
```

Populate `files` with the verified SHA-256 values for every distributed asset. Do not omit secondary pieces because the generator places the complete external assembly.

- [ ] **Step 4: Add prominent redistribution notices**

The asset README, asset license notice and root `THIRD_PARTY_ASSETS.md` must state:

```text
These CAD files remain owned by their original creator, David Velez.
They are not covered by the repository license.
Original model: https://grabcad.com/library/swiss-lever-watch-escapement-model-1
Public non-commercial redistribution requires attribution under GrabCAD guidance.
Commercial public use requires explicit permission from the creator.
Removing this payload makes the generated watch power chain mechanically incomplete.
```

Also link:

```text
https://help.grabcad.com/article/246-how-can-models-be-used-and-shared
https://help.grabcad.com/article/149-community-values-and-guidelines
```

- [ ] **Step 5: Run provenance tests and Git LFS checks**

```powershell
python -m pytest models/watch_kinematic/tests/test_third_party_escapement.py -v
git check-attr filter -- "models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15/Escapement Model.STEP"
```

Expected: tests PASS and the STEP file uses the `lfs` filter.

- [ ] **Step 6: Commit**

```powershell
git add models/watch_kinematic/references/escapement THIRD_PARTY_ASSETS.md models/watch_kinematic/tests/test_third_party_escapement.py
git commit -m "feat: include attributed Swiss lever escapement"
```

---

### Task 7: Declare Model-Specific Runtime Dependencies

**Files:**
- Create: `models/watch_kinematic/requirements.txt`
- Modify: `models/watch_kinematic/README.md`
- Create: `models/watch_kinematic/tests/test_runtime_dependencies.py`

**Interfaces:**
- Produces: reproducible Python environment requirements without changing upstream global CAD requirements.

- [ ] **Step 1: Write the dependency import test**

```python
def test_watch_generator_runtime_dependencies_import():
    import build123d  # noqa: F401
    import matplotlib  # noqa: F401
    import numpy  # noqa: F401
    import PIL  # noqa: F401
    import scipy  # noqa: F401
```

- [ ] **Step 2: Add the model-specific requirements**

```text
build123d
numpy
scipy
matplotlib
Pillow
```

- [ ] **Step 3: Test in the existing workspace environment**

```powershell
python -m pytest models/watch_kinematic/tests/test_runtime_dependencies.py -v
```

Expected: PASS.

- [ ] **Step 4: Document installation without duplicating the upstream toolchain**

README command:

```powershell
python -m pip install -r skills/cad/requirements.txt
python -m pip install -r models/watch_kinematic/requirements.txt
```

- [ ] **Step 5: Commit**

```powershell
git add models/watch_kinematic/requirements.txt models/watch_kinematic/README.md models/watch_kinematic/tests/test_runtime_dependencies.py
git commit -m "docs: declare watch generator dependencies"
```

---

### Task 8: Add a Thin Three-Pattern Generation and Retry Entry Point

**Files:**
- Create: `models/watch_kinematic/generate_watch.py`
- Create: `models/watch_kinematic/tests/test_public_generate_watch.py`

**Interfaces:**
- Produces: `generate_watch(pattern: int, seed: int | None, max_attempts: int, output_dir: Path | None) -> GenerationResult`.
- Reuses: existing accepted builders in `partitioned_bridge_stage.py`.

- [ ] **Step 1: Write failing mapping and retry tests**

The tests must import `Path` and assert:

```python
from pathlib import Path


def test_public_pattern_mapping_uses_accepted_builders():
    assert PATTERN_BUILDERS[1].__name__ == "build_partitioned_bridge_stage"
    assert PATTERN_BUILDERS[2].__name__ == "build_separate_display_partitioned_bridge_stage"
    assert PATTERN_BUILDERS[3].__name__ == "build_pattern3_independent_display_complete_model"


def test_failed_seed_retries_without_publishing_failed_step(monkeypatch, tmp_path):
    attempted = []

    def fake_builder(output_dir, *, seed, include_lightening=True):
        attempted.append(seed)
        if len(attempted) == 1:
            raise ValueError("solver failed")
        step = Path(output_dir) / "model.step"
        step.write_text("ok", encoding="utf-8")
        return {"status": "pass", "artifacts": {"step": str(step)}}

    monkeypatch.setitem(PATTERN_BUILDERS, 3, fake_builder)
    result = generate_watch(pattern=3, seed=7333, max_attempts=2, output_dir=tmp_path)
    assert result.status == "pass"
    assert result.attempt_count == 2
    assert len(attempted) == 2
```

- [ ] **Step 2: Implement only orchestration**

The entry point must:

```text
1. Validate pattern is 1, 2 or 3.
2. Use the supplied seed for attempt 1, or generate a random 32-bit seed.
3. Derive a fresh random seed for each retry.
4. Give every attempt its own temporary subdirectory.
5. Call the existing accepted builder with include_lightening=True.
6. Accept only a report with pass status and an existing STEP.
7. Publish only the successful attempt directory.
8. Return attempted seeds and failure messages in run_record.json.
9. Never generate GLB itself.
```

Default output root:

```python
Path(tempfile.gettempdir()) / f"ontology-watch-pattern-{pattern:02d}-seed-{seed}"
```

Use this public result contract:

```python
@dataclass(frozen=True)
class GenerationResult:
    status: str
    pattern: int
    requested_seed: int | None
    successful_seed: int
    attempt_count: int
    attempted_seeds: tuple[int, ...]
    output_dir: Path
    step_path: Path
    report: dict[str, Any]
```

- [ ] **Step 3: Add CLI arguments**

```text
--pattern {1,2,3}
--seed INTEGER
--max-attempts INTEGER   default: 3
--output-dir PATH
--open                   generate native Explorer artifacts and print/open the review URL
```

- [ ] **Step 4: For `--open`, call the native text-to-cad CAD/render command**

Invoke it from Python with the successful path:

```python
subprocess.run(
    [sys.executable, "skills/cad/scripts/step", str(result.step_path)],
    cwd=repository_root,
    check=True,
)
```

The CLI must not import or copy private GLB exporter modules. Failure to produce the native GLB, topology and STEP module artifacts returns a non-zero exit code.

- [ ] **Step 5: Run tests**

```powershell
python -m pytest models/watch_kinematic/tests/test_public_generate_watch.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add models/watch_kinematic/generate_watch.py models/watch_kinematic/tests/test_public_generate_watch.py
git commit -m "feat: add watch generation and seed retry entrypoint"
```

---

### Task 9: Prove Native Artifact and Motion Integration

**Files:**
- Create: `models/watch_kinematic/tests/test_native_artifact_contract.py`

**Interfaces:**
- Consumes: one successful STEP per public pattern.
- Produces: proof that the branch uses native assembly topology, materials and motion sidecars.

- [ ] **Step 1: Add an artifact contract test**

For each generated Pattern, assert:

```text
STEP exists.
Motion JSON exists.
STEP module JavaScript exists.
Native GLB exists after the CAD skill runs.
GLB STEP_topology contains an assembly section.
Assembly section contains root, occurrences and leafPartIds.
Every declared moving feature resolves to at least one leaf part.
Bridge material opacity matches the pattern's declared material contract.
```

- [ ] **Step 2: Generate one short-path smoke model per public pattern**

```powershell
python models/watch_kinematic/generate_watch.py --pattern 1 --seed 731 --max-attempts 1 --output-dir C:/tmp/watch-p1
python models/watch_kinematic/generate_watch.py --pattern 2 --seed 8459 --max-attempts 1 --output-dir C:/tmp/watch-p2
python models/watch_kinematic/generate_watch.py --pattern 3 --seed 731 --max-attempts 1 --output-dir C:/tmp/watch-p3
```

Expected: three successful STEP bundles outside the repository.

- [ ] **Step 3: Run native artifact generation for each STEP**

```powershell
python skills/cad/scripts/step --kind assembly C:/tmp/watch-p1/watch_power_chain_with_analytic_partitioned_bridges_and_scaled_swiss_lever_reference.step
python skills/cad/scripts/step --kind assembly C:/tmp/watch-p2/watch_power_chain_separate_display_with_analytic_partitioned_bridges.step
python skills/cad/scripts/step --kind assembly C:/tmp/watch-p3/watch_power_chain_pattern3_independent_display_with_analytic_partitioned_bridges.step
```

Expected: GLB and topology artifacts generated with no custom transcode module.

- [ ] **Step 4: Run the artifact contract test**

```powershell
python -m pytest models/watch_kinematic/tests/test_native_artifact_contract.py -v
```

Expected: PASS for all three patterns.

- [ ] **Step 5: Commit**

```powershell
git add models/watch_kinematic/tests/test_native_artifact_contract.py
git commit -m "test: verify native watch artifact integration"
```

---

### Task 10: Publish Upstream-Compatible Documentation

**Files:**
- Modify: `README.md`
- Modify: `models/watch_kinematic/README.md`
- Create: `docs/design_patterns/watch_generator/architecture.md`
- Create: `docs/design_patterns/watch_generator/patterns.md`
- Create: `docs/design_patterns/watch_generator/extension_guide.md`

**Interfaces:**
- Produces: contributor-facing explanation of ownership boundaries and extension points.

- [ ] **Step 1: Document the ownership boundary**

State explicitly:

```text
text-to-cad owns CAD artifact generation, assembly topology, rendering and Explorer.
The watch generator owns engineering rules, pattern solvers, geometry construction, semantic sidecars, validation gates and motion declarations.
The Swiss lever escapement is a bundled third-party payload under separate terms.
```

- [ ] **Step 2: Document all three public patterns and exact builder mapping**

Explain that the accepted original Pattern 4 implementation was promoted to the sole canonical Pattern 3 and that the superseded early Pattern 3 was removed.

- [ ] **Step 3: Document random-seed behavior**

Explain explicit seed, random seed, retry attempts, failed-attempt isolation, successful artifact paths, and temporary-directory defaults.

- [ ] **Step 4: Document extension rules**

A new domain/pattern must provide:

```text
role contracts
solver variables and constraints
geometry builder
semantic sidecars
motion declarations where applicable
hard validators
one thin public builder entry
tests that use the native text-to-cad artifact pipeline
```

- [ ] **Step 5: Commit**

```powershell
git add README.md models/watch_kinematic/README.md docs/design_patterns/watch_generator THIRD_PARTY_ASSETS.md
git commit -m "docs: publish watch generator integration guide"
```

---

### Task 11: Delete Local Generated Watch and Reducer Outputs Safely

**Files:**
- Delete locally: contents of `models/watch_kinematic/outputs/` except `.gitkeep`.
- Delete locally: contents of `models/planetary_reducer/outputs/` except `.gitkeep`.
- Preserve: `models/watch_kinematic/references/**`, `models/reference_assemblies/**`, and `references/**`.

**Interfaces:**
- Consumes: completed source snapshot and clean integration branch.
- Produces: reclaimed disk space without deleting downloaded third-party assets.

- [ ] **Step 1: Resolve and print deletion roots**

```powershell
$repo = (Resolve-Path C:/Users/wande/Documents/text-to-cad).Path
$watch = (Resolve-Path "$repo/models/watch_kinematic/outputs").Path
$reducer = (Resolve-Path "$repo/models/planetary_reducer/outputs").Path
$watch
$reducer
```

Expected: both resolved paths remain under the intended repository and end in `/outputs`.

- [ ] **Step 2: Print preserved reference roots before deletion**

```powershell
Resolve-Path "$repo/models/watch_kinematic/references"
Resolve-Path "$repo/models/reference_assemblies"
```

Expected: neither path is inside either deletion root.

- [ ] **Step 3: Remove only output-directory children**

Use native PowerShell `Remove-Item -LiteralPath` on each verified child. Do not construct paths through another shell. Recreate `.gitkeep` afterward.

- [ ] **Step 4: Repeat the verified cleanup for the accepted watch worktree**

Target only:

```text
C:/Users/wande/.config/superpowers/worktrees/text-to-cad/codex-watch-separate-display/models/watch_kinematic/outputs
C:/Users/wande/.config/superpowers/worktrees/text-to-cad/codex-watch-separate-display/models/planetary_reducer/outputs
```

- [ ] **Step 5: Verify references still exist and outputs are empty**

Expected:

```text
Escapement Model.STEP exists.
Downloaded reference assemblies remain present.
Output directories contain only .gitkeep or are empty.
```

Do not commit deletions on old experimental branches. The clean branch already excludes those historical files.

---

### Task 12: Full Verification, Visual Gate and Push

**Files:**
- No generated model files added to Git.
- Update only documentation if verification discovers command corrections.

**Interfaces:**
- Produces: PR-ready branch and three externally reviewed models.

- [ ] **Step 1: Run the complete watch test suite**

```powershell
python -m pytest models/watch_kinematic/tests -v
```

Expected: PASS.

- [ ] **Step 2: Verify release hygiene**

```powershell
git status --short
git ls-files models/watch_kinematic/outputs models/planetary_reducer/outputs
git diff --stat origin/main...HEAD
```

Expected: no generated model artifacts, no unrelated reducer/factory/reference-assembly work, and only the intended integration files.

- [ ] **Step 3: Generate three random-seed acceptance models in temporary directories**

```powershell
python models/watch_kinematic/generate_watch.py --pattern 1 --max-attempts 3 --open
python models/watch_kinematic/generate_watch.py --pattern 2 --max-attempts 3 --open
python models/watch_kinematic/generate_watch.py --pattern 3 --max-attempts 3 --open
```

Expected: each command reports attempted seed(s), successful seed, STEP path and Explorer URL.

- [ ] **Step 4: Perform agent visual self-checks**

For each pattern inspect top and isometric views and play the animation. Block delivery on:

```text
missing escapement components
incorrect bridge transparency/materials
floating or translated rotating parts
hands or gears not rotating
gear/case boundary violations
missing bridge plates, screws or support islands
obvious interference or missing assembly members
```

- [ ] **Step 5: User acceptance gate**

Open Pattern 1, then Pattern 2, then Pattern 3 in CAD Explorer. Continue only after the user accepts all three.

- [ ] **Step 6: Final branch review**

Use `superpowers:requesting-code-review`. Review especially:

```text
upstream mergeability
no duplicated CAD/Explorer pipeline
third-party redistribution notices
generated-output exclusion
public Pattern mapping
random-seed retry behavior
native motion and material behavior
```

- [ ] **Step 7: Push the clean branch to the user's fork**

```powershell
git push myfork codex/watch-generator-upstream-integration
```

Expected: branch is available on `https://github.com/Marcus-QL-Zhu/text-to-cad` and can be proposed directly against `earthtojake/text-to-cad`.

---

## Acceptance Criteria

- [ ] The branch is based on current upstream `origin/main`.
- [ ] Public Patterns 1, 2 and 3 generate complete watches.
- [ ] Public Pattern 3 uses the accepted original Pattern 4 hard-gated behavior under a fully renamed Pattern 3 identity.
- [ ] The superseded early Pattern 3 and every `pattern4` source identity are absent from the clean branch.
- [ ] Random seeds are supported; failed seeds retry without publishing failed STEP files.
- [ ] The complete Swiss lever escapement is present in Git and appears in every complete watch.
- [ ] Third-party creator, source, hashes and redistribution rules are prominent and machine-checked.
- [ ] Generated watch and reducer outputs are absent from Git.
- [ ] No standalone GLB/Explorer/transcode implementation is copied into the branch.
- [ ] Native text-to-cad assembly topology, materials and animation work for all three patterns.
- [ ] Top and isometric visual checks pass before user acceptance.
- [ ] The final diff contains no planetary-reducer, EFEM, unrelated reference-assembly or historical experiment output files.

## Superseded Plan

This plan supersedes the standalone-repository architecture in:

```text
docs/superpowers/plans/2026-07-10-ontochrono-open-source-implementation.md
```

That document remains historical context only. Its third-party provenance facts are retained here; its standalone package, copied reference backend, custom transcode and private Explorer integration must not be reused.
