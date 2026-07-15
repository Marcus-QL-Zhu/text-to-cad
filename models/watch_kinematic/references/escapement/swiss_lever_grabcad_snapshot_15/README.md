# Swiss Lever Watch Escapement Model

This directory publishes the complete original Snapshot 15 ZIP used by the
watch generator, together with its provenance and redistribution notices. The
archive contains the assembly STEP, STL exports, DXF and OpenSCAD sources,
secondary pieces, source notes, and reference images.

## Ownership And Redistribution

These CAD files remain owned by their original creator, David Velez.
They are not covered by the repository license.
Original model: https://grabcad.com/library/swiss-lever-watch-escapement-model-1
Public non-commercial redistribution requires attribution under GrabCAD guidance.
Commercial public use requires explicit permission from the creator.
Removing this payload makes the generated watch power chain mechanically incomplete.

GrabCAD guidance:

- https://help.grabcad.com/article/246-how-can-models-be-used-and-shared
- https://help.grabcad.com/article/149-community-values-and-guidelines

## Provenance And Integrity

The original ZIP is the only CAD payload tracked by this repository. Generator
code verifies its checksum and extracts it on demand into the ignored
`_extracted/` cache. Generated or extracted STEP/STL/DXF/GLB files are never
Git inputs.

`SOURCE.json` records the creator, original model URL, published date, source
snapshot identity, source snapshot SHA-256, usage policy, and the accepted
per-file reference manifest. The ZIP checksum is the canonical integrity gate;
extracted files remain local cache and never enter Git.
