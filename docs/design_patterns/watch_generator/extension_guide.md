# Extending The Watch Generator

New patterns belong in the existing pattern-card package structure. Keep the
public generator as the single publication boundary and reuse the native
text-to-cad artifact pipeline for CAD artifact generation, assembly topology,
rendering, and Explorer.

## Required Extension Contract

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

Treat this list as a vertical slice. A new scenario is incomplete when it adds
geometry without role contracts, solver evidence, and hard validators, or adds
semantics without a reproducible geometry and publication path.

Put the card contract, solver, and review writer in a focused package under
[`models/watch_kinematic/watch_kinematic/pattern_cards`](../../../models/watch_kinematic/watch_kinematic/pattern_cards).
The card declares the role contract and hard constraints; the solver emits
explicit proof fields; the review writer remains a human-readable review
surface, not the source of engineering truth.

## Publication Rules

The thin builder entry must accept an isolated output directory, `seed`, and
`include_lightening`, return a passing report that identifies a STEP inside that
output directory, and leave validation failures to the public retry boundary.
Register only the final public builder in
[`PATTERN_BUILDERS`](../../../models/watch_kinematic/generate_watch.py), then
add focused tests that exercise it through the native artifact pipeline.

Do not create a separate CAD serializer, GLB/Explorer runtime, or artifact
directory convention. The public entry point owns seed selection, retry
isolation, successful-artifact publication, and `run_record.json`.

## Validation Expectations

Treat role contracts, solver proofs, geometry, semantic sidecars, motion, and
hard validation gates as one delivery contract. Add tests before changing solver
contracts, hard gates, bridge service rules, motion semantics, or package IDs.
For Pattern 3 complete-model work, retain lightened bridges by default; use
`include_lightening=False` only for targeted debugging or speed tests.

For a new design domain, begin with a boundary that is narrow enough to express
as executable constraints. Add topology patterns only after the required roles,
interfaces, permitted degrees of freedom, and failure conditions are explicit.
Keep domain solvers and validators inside the domain package; contribute reusable
CAD, artifact, or Explorer capabilities to the upstream text-to-cad layer.

See [architecture.md](architecture.md) for the ownership boundary and
[patterns.md](patterns.md) for the existing public mappings.
