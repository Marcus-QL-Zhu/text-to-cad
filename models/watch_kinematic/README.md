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
python -m pip install -r skills/cad/requirements.txt
python -m pip install -r models/watch_kinematic/requirements.txt
```

## Public Usage

Public generation entry points and usage instructions will be documented here after the integration interfaces are established.
