# Ontology-Based Watch Generator

This directory contains a computational-engineering demonstrator for generating
mechanical-watch assemblies with build123d. It converts reusable engineering
knowledge into executable design patterns, semantic contracts, constraint
solvers, geometry builders, and validation gates.

The generator is intentionally layered on text-to-cad. It reuses the upstream
STEP, GLB, assembly-topology, material, motion, and CAD Explorer pipeline rather
than maintaining a second CAD runtime.

## Design Philosophy

Computational engineering treats engineering knowledge as executable source
code. Rules such as gear clearance, power-chain continuity, bearing support,
bridge coverage, screw placement, material assignment, and allowed motion are
versioned, tested, and reused across every generated candidate.

The agent or user supplies a pattern, seed, and generation request. Deterministic
solvers and validators decide whether the result is acceptable. A failed seed is
discarded in an isolated staging directory and a new seed can be tried without
publishing a partial assembly. This separation lets agents orchestrate design
exploration without making unverified dimensions the source of truth.

## Two Research Lineages

The implementation combines two complementary research directions:

1. **Ontology for generative design** represents what each component means:
   its role, interfaces, part-whole relations, power-chain membership, material,
   intended degrees of freedom, and required evidence.
2. **Design synthesis** represents how a design is found: select a topology,
   define variable domains, solve coupled constraints, generate geometry,
   validate the candidate, and iterate when a hard rule fails.

Together they form executable semantics. The ontology prevents geometrically
plausible parts from losing their engineering purpose; design synthesis searches
for different valid arrangements within a declared problem boundary.

## System Layers

| Layer | Responsibility |
| --- | --- |
| Boundary setup | Case envelope, display topology, pattern selection, seed, and fixed third-party interfaces. |
| Design-pattern synthesis | Candidate variables, topology-specific rules, and the feasible search space for Patterns 1-3. |
| Semantic sidecars | Role contracts, power chains, assembly relations, materials, motion intent, and validation evidence. |
| Constraint solving | XY layout, Z stack, gear ratios and phase, clearances, bridge partitioning, bearing coverage, and fastener service regions. |
| Geometry harness | Stable build123d/OCP builders, local frames, named occurrences, imported escapement placement, and assembly creation. |
| Validation and publication | Hard gates, artifact checks, motion binding, material checks, isolated retries, STEP publication, and CAD Explorer handoff. |

The same layers can also be viewed as a three-part operational model: the
semantic layer states what the design means, the kinetic layer executes solvers
and geometry operations, and the dynamic layer feeds validation failures back
into retry or redesign decisions.

## Stable build123d Assembly Harness

Complex assemblies are generated through a controlled harness rather than a
single free-form modeling script:

1. A public entry point selects one canonical design-pattern builder.
2. The builder solves topology-specific XY, Z-stack, gearing, support, and
   clearance constraints before publishing geometry.
3. Parts are created in local reference frames and assembled with stable labels
   and occurrence identities.
4. Semantic contracts bind engineering roles to geometry, materials, motion,
   and expected degrees of freedom.
5. The third-party Swiss lever escapement is retained as a complete attributed
   subassembly and positioned through solved interfaces.
6. STEP, topology, material, motion, and evidence artifacts are produced as one
   candidate package.
7. Hard validators decide whether that package can be published. Failed attempts
   remain private and are removed before a distinct seed is tried.

This harness is the main reliability mechanism. It makes geometry generation,
semantic intent, validation, and browser review part of one transaction.

## Package Layout

- `watch_kinematic/` contains the generator, solver, geometry, semantic, and validation modules.
- `tests/` contains the package's focused regression and release-hygiene tests.
- `outputs/` is reserved for locally generated artifacts.

## Generated Outputs

Generated watch artifacts are reproducible and are not committed. Files under `outputs/` remain ignored except for the tracked `.gitkeep` marker.

The attributed Swiss lever reference is the only bundled non-regenerated CAD
payload. See [`THIRD_PARTY_ASSETS.md`](../../THIRD_PARTY_ASSETS.md) and the
provenance files beside the reference asset before redistributing it.

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

## Generation Flow

```text
requirements + pattern + seed
        -> candidate-variable domains
        -> coupled constraint solving
        -> semantic contracts and evidence
        -> build123d assembly generation
        -> hard geometry/semantic/motion/artifact gates
        -> publish on pass, retry a distinct seed on failure
```

## Current Limitations

- This is a research and engineering-workflow demonstrator, not a production
  watch movement ready for manufacturing release.
- It does not yet perform complete strength, fatigue, shock, wear, lubrication,
  thermal, tolerance-stack, metrology, or manufacturing-process validation.
- Gear geometry and kinematics support design exploration and visual validation;
  they are not a certified horological tooth-form or timing calculation package.
- The Swiss lever escapement is an attributed third-party reference assembly and
  remains subject to its source terms.
- Engineering semantics are delivered in sidecars. They are not yet embedded as
  complete AP242 assembly, PMI, tolerance, and mate semantics inside STEP.
- Seed retry samples the feasible space; it does not prove that every feasible
  design has been enumerated or that a rejected boundary has no solution.
- Winding and keyless works, automatic winding, calendar mechanisms, shock
  protection, and production detailing are outside the current scope.

## Extending To Other Design Scenarios

A new scenario should define its boundary, topology patterns, role contracts,
solver variables, geometry builders, hard validators, and evidence outputs while
reusing the upstream text-to-cad artifact and Explorer pipeline. Start with the
[extension guide](../../docs/design_patterns/watch_generator/extension_guide.md)
and keep the public generation boundary thin enough to merge upstream cleanly.

For ownership boundaries, architecture, complete builder paths, and extension
requirements, see [the watch generator documentation](../../docs/design_patterns/watch_generator/architecture.md).
