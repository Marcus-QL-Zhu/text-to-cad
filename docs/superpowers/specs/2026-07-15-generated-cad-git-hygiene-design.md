# Generated CAD Git Hygiene Design

## Goal

Prevent reproducible CAD outputs from entering Git, Git LFS, or Codex's background Git diff pipeline while retaining the one non-regenerable third-party escapement source package required by the watch generator.

## Repository Policy

- Ignore generated and extracted 2D/3D model formats repository-wide.
- Keep source code, semantic sidecars, validation reports, documentation, and generation recipes in normal Git.
- Keep only the original GrabCAD Swiss lever escapement ZIP as a binary source artifact in Git LFS.
- Store attribution, provenance, and redistribution terms next to that archive in normal Git.
- Extract the vendor archive into an ignored local cache when a generator needs it.
- Do not commit generated watch, reducer, warm-up, viewer, screenshot, or animation artifacts.

## Ignored Model Formats

The project-level and shared local ignore rules cover at least:

```text
*.step *.stp *.stl *.glb *.gltf *.3mf *.obj *.ply
*.iges *.igs *.brep *.fcstd *.sldprt *.sldasm
*.x_t *.x_b *.jt *.sat *.sab *.dxf *.dwg
```

The ignore policy is format-based so generated files remain excluded even when written outside a conventional `outputs/` directory. Output-directory rules remain as a second guard.

## Third-Party Exception

The original file `swiss-lever-watch-escapement-model-1.snapshot.15.zip` is the sole CAD payload exception. The ZIP itself is tracked through Git LFS; extracted model files remain ignored. Runtime code resolves an existing local extraction or extracts the archive into a deterministic ignored cache before use.

## Existing Repository Cleanup

- Remove tracked generated model files from the index while preserving source files and required reports.
- Replace tracked extracted escapement geometry with the original ZIP plus normal-Git attribution and provenance files.
- Do not delete local generated models as part of index cleanup unless they are known disposable outputs.
- Do not rewrite upstream history in this feature branch; the clean publication branch contains only the desired final tree.

## Shared Worktree Protection

Add the same generated-model patterns to the common repository `.git/info/exclude`. This local rule applies immediately to all linked worktrees, including branches that have not yet received the committed `.gitignore` change.

## Verification

- A release-hygiene test proves representative model formats are ignored.
- The test proves the vendor ZIP is tracked through LFS and extracted vendor model files are ignored.
- `git ls-files` contains no generated CAD model formats outside the approved vendor ZIP.
- Creating a large ignored GLB does not change `git status` and does not grow `.git/lfs/tmp`.
- Watch generation still succeeds after resolving the vendor archive locally.

