# Ontology-Based Watch Generator

This directory contains the ontology-based mechanical-watch generator package copied from the accepted baseline at `5be7852844a3f4c5698a737eba81c026e96ced16`.

## Package Layout

- `watch_kinematic/` contains the generator, solver, geometry, semantic, and validation modules.
- `tests/` contains the package's focused regression and release-hygiene tests.
- `outputs/` is reserved for locally generated artifacts.

## Generated Outputs

Generated watch artifacts are reproducible and are not committed. Files under `outputs/` remain ignored except for the tracked `.gitkeep` marker.

## Dependencies

From the repository root, install the upstream CAD skill requirements first,
then install the watch-specific runtime requirements:

```powershell
Push-Location skills/cad
python -m pip install -r requirements.txt
Pop-Location
python -m pip install -r models/watch_kinematic/requirements.txt
```

## Public Usage

Use `generate_watch.py` as the sole public generation entry point. It accepts
only the three canonical public patterns:

| Pattern | Public pattern | Builder |
| --- | --- | --- |
| `1` | Central Hour/Minute With Off-Center Seconds | `build_partitioned_bridge_stage` |
| `2` | Separate Hour And Minute Display Without Seconds | `build_separate_display_partitioned_bridge_stage` |
| `3` | Independent Hour And Minute Display Without Seconds | `build_pattern3_independent_display_complete_model` |

For example:

```powershell
python models/watch_kinematic/generate_watch.py --pattern 1 --seed 731 --max-attempts 3
python models/watch_kinematic/generate_watch.py --pattern 2 --seed 8459 --max-attempts 3
python models/watch_kinematic/generate_watch.py --pattern 3 --seed 731 --max-attempts 3
```

Pass `--output-dir <directory>` to publish a successful run there. The target
may be created when absent or reused when it already exists and is empty; a
non-empty target fails. With no `--output-dir`, the generator uses the
deterministic system-temporary target
`ontology-watch-pattern-<two-digit-pattern>-seed-<first-seed>` (for example,
`ontology-watch-pattern-01-seed-731`) with the same empty-directory rule. Add
`--open` to review the successful STEP through the native CAD skill entry point.

An explicit `--seed` starts the first attempt with that seed. Omitting it
chooses a random 32-bit seed. A failed attempt is isolated in a private staging
directory and removed before the next distinct random seed is tried; only a
successful attempt is published to the selected output directory. The published
directory contains the successful artifact paths and `run_record.json`, which
records the requested seed, attempted seeds, successful seed, and attempt count.

The accepted original Pattern 4 implementation was promoted to the sole
canonical Pattern 3. The superseded early Pattern 3 was removed.

For ownership boundaries, architecture, complete builder paths, and extension
requirements, see [the watch generator documentation](../../docs/design_patterns/watch_generator/architecture.md).
