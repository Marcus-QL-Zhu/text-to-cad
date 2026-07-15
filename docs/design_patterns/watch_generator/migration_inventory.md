# Watch Generator Migration Inventory

## Immutable Source Baseline

- Local `main` at snapshot time: `40a3729edb0cb32633683c8ae80a82ee212a7a92`.
- Accepted watch source: `5be7852844a3f4c5698a737eba81c026e96ced16` (`codex/watch-separate-display`).
- Refreshed upstream base: `fdbb4b4fb62d95ae298cfe9a46fdc7092bdaf423` (`origin/main`).

## Migration Decisions

- KEEP: accepted watch source, tests, sidecar builders, solver and validation code.
- KEEP: the three official watch case inputs and the watch kinematic domain semantics note.
- KEEP: complete GrabCAD escapement payload plus provenance.
- REUSE UPSTREAM: CAD skill, STEP/GLB pipeline, assembly topology, materials, motion runtime, Explorer.
- DROP: all watch/reducer generated outputs, historical candidate batches, local screenshots and dashboards.
- DROP: standalone Ontology-based-Watch-Generator transcode and Explorer reimplementations.
- DEFER: reducer, EFEM, reference-assembly and design-pattern-factory work.

## Snapshot Boundary

The external source snapshot retains both worktrees, downloaded third-party references, and non-output uncommitted work. It excludes `.git`, virtual environments, dependency caches, Python bytecode, and the watch and reducer generated-output roots listed in the manifest.
