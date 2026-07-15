# Watch Generator Architecture

## Architectural Goal

The watch generator demonstrates a computational-engineering workflow for
complex build123d assemblies. Engineering intent is captured in code and data,
then applied repeatedly to different seeded layouts. Agents coordinate the
workflow; deterministic solvers, builders, and validators own acceptance.

The architecture is designed to remain mergeable with text-to-cad. Domain logic
lives under `models/watch_kinematic`, while shared CAD serialization, topology,
GLB rendering, and Explorer behavior stay in the upstream pipeline.

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

## Layer Model

### 1. Boundary Setup

The boundary describes the movement envelope, selected display topology, fixed
interfaces, and candidate seed. It prevents an unconstrained language model from
silently redefining the engineering task.

### 2. Design-Pattern Synthesis

Each public pattern defines a topology and a bounded variable space. Pattern
solvers determine viable arbor locations, gear relationships, display routing,
and bridge ownership. A seed influences candidate selection within declared
domains; it never overrides hard constraints.

### 3. Semantic Layer

Semantic sidecars identify component roles, part-whole relationships, power-chain
edges, support expectations, materials, motion intent, and validation evidence.
They let downstream checks reason about engineering purpose rather than relying
only on filenames or raw geometry.

### 4. Coupled Constraint Solving

Pattern-specific solvers coordinate XY placement, Z-stack layers, gear ratios and
phase, case clearance, arbor and bearing envelopes, bridge seams, lightening
windows, and screw service regions. Cross-layer checks prevent an XY-valid result
from being published when its Z stack or bridge geometry is invalid.

### 5. Geometry Harness

The build123d/OCP harness uses local frames, stable part labels, named assembly
occurrences, and controlled builder entry points. Imported escapement geometry is
treated as an attributed rigid subassembly whose solved interfaces determine
placement. Geometry construction remains downstream of the declared topology and
constraints.

### 6. Validation And Publication

Hard gates check required artifacts, geometry and envelope contracts, semantic
coverage, materials, motion bindings, and topology evidence. A candidate is built
inside an isolated attempt directory. Publication is transactional: only a
passing package is moved to the requested output directory.

## Semantic, Kinetic, And Dynamic Views

- **Semantic:** component meaning, interfaces, relationships, materials, and
  intended degrees of freedom.
- **Kinetic:** executable solvers, builders, artifact generation, and motion
  declarations.
- **Dynamic:** validation feedback, failed-seed isolation, retry, and retained
  run evidence.

The dynamic view currently operates at generation-attempt level. It is a bounded
repair/retry loop rather than a self-modifying engineering system.

## Assembly Artifact Contract

A complete successful run may include:

- the STEP assembly;
- STEP topology and browser-ready GLB artifacts from the native CAD pipeline;
- semantic and complete-model reports;
- material and motion sidecars;
- validation evidence emitted by the selected pattern;
- `run_record.json`, recording requested, attempted, and successful seeds.

Stable occurrence identities connect the assembly tree to material and motion
intent. This is essential for animation: rotating a geometric subtree by a loose
name can accidentally create orbital motion, while occurrence-bound motion keeps
each part on its declared axis and allowed degree of freedom.

## Reliability Rules

1. Solve and validate engineering relationships before treating visible geometry
   as evidence of correctness.
2. Use local frames and stable labels instead of world-coordinate assumptions and
   fragile assembly-tree positions.
3. Bind materials and motion through semantic roles and occurrence identities.
4. Keep third-party subassemblies complete and preserve provenance.
5. Build in a private staging directory and publish only after hard gates pass.
6. Record seeds and evidence so an accepted result can be reproduced.
7. Reuse text-to-cad's native artifact and Explorer stack instead of forking a
   parallel renderer or serializer.

## Engineering Limits

The current implementation validates a bounded geometric and kinematic design
problem. It does not certify strength, fatigue, shock, wear, lubrication,
tolerance stacks, thermal behavior, manufacturing processes, or horological
performance. Sidecars carry semantics beside STEP; full AP242 assembly, PMI,
tolerance, and mate embedding remains future work. Random retries explore the
declared candidate space without proving global completeness.

## Contributor Entry Points

The pattern-card packages under
[`models/watch_kinematic/watch_kinematic/pattern_cards`](../../../models/watch_kinematic/watch_kinematic/pattern_cards)
separate card contracts, solvers, and review writers. Their local
[`AGENTS.md`](../../../models/watch_kinematic/watch_kinematic/pattern_cards/AGENTS.md)
defines the package convention. Public pattern behavior and migration history
are documented in [patterns.md](patterns.md); required additions are documented
in [extension_guide.md](extension_guide.md).
