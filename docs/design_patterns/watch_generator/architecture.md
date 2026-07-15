# Watch Generator Architecture

## Ownership Boundary

text-to-cad owns CAD artifact generation, assembly topology, rendering and Explorer.
The watch generator owns engineering rules, pattern solvers, geometry construction, semantic sidecars, validation gates and motion declarations.
The Swiss lever escapement is a bundled third-party payload under separate terms.

The generator therefore consumes the repository's native artifact pipeline; it
does not provide a separate STEP, GLB, rendering, or Explorer implementation.
The bundled Swiss lever payload is governed by the notice in
[`THIRD_PARTY_ASSETS.md`](../../../THIRD_PARTY_ASSETS.md) and its local
provenance files.

## Public Generation Boundary

[`models/watch_kinematic/generate_watch.py`](../../../models/watch_kinematic/generate_watch.py)
is the thin public generation boundary. Its `PATTERN_BUILDERS` mapping is:

| Public pattern | Builder | Package card |
| --- | --- | --- |
| `1` | `build_partitioned_bridge_stage` | `central_hour_minute_offcenter_seconds` |
| `2` | `build_separate_display_partitioned_bridge_stage` | `separate_hour_minute_no_seconds` |
| `3` | `build_pattern3_independent_display_complete_model` | `independent_hour_minute_no_seconds` |

Each builder receives an isolated attempt directory, a seed, and
`include_lightening=True`. A passing builder report must identify a STEP inside
that attempt directory. The public entry point then moves only the successful
attempt's contents to the target directory, remaps artifact paths in its report,
and writes `run_record.json`.

## Generation Flow

1. Validate `--pattern` and `--max-attempts`, then choose the explicit seed or a random 32-bit first seed.
2. Create the requested empty output directory or the default temporary output directory.
3. Run the mapped builder in a private attempt directory.
4. On failure, remove that attempt directory and retry with a distinct random seed until the attempt limit is reached.
5. On success, publish the generated artifacts, save `run_record.json`, and optionally open the STEP through the native CAD skill command.

No failed STEP or other failed-attempt artifact is published. When every attempt
fails, the target contains the failure `run_record.json` and the command returns
a nonzero status.

## Contributor Entry Points

The pattern-card packages under
[`models/watch_kinematic/watch_kinematic/pattern_cards`](../../../models/watch_kinematic/watch_kinematic/pattern_cards)
separate card contracts, solvers, and review writers. Their local
[`AGENTS.md`](../../../models/watch_kinematic/watch_kinematic/pattern_cards/AGENTS.md)
defines the package convention. Public pattern behavior and migration history
are documented in [patterns.md](patterns.md); required additions are documented
in [extension_guide.md](extension_guide.md).
