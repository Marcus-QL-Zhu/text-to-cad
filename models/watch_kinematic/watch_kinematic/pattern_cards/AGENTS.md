# Watch Pattern Card Source Map

This folder contains executable watch pattern-card packages. Use it as source code, not as generated evidence.

Before editing a pattern, read the project-level entry map:

```text
C:/Users/wande/.config/superpowers/worktrees/text-to-cad/codex-watch-separate-display/docs/design_patterns/sprints/watch_kinematic_demo/pattern_cards/watch_pattern_1_to_4_entry_map.md
```

Package convention:

- `card.py` declares the role contract, hard constraints, negative cases, and markdown/json card writer.
- `solver.py` owns the deterministic or seeded layout solver and must emit explicit proof fields for hard constraints.
- `review.py` writes human-readable 2D review pages only; it must not become the source of engineering truth.
- `__init__.py` exports the package entry points.

Validation rule:

- Add or update tests before changing solver contracts, hard gates, bridge service rules, motion semantics, or package IDs.
- Do not put one-off generated STEP/HTML/PNG artifacts in this source folder.
- If a pattern needs a compatibility facade, keep the facade thin and point back to the package.
- Pattern 3's complete-model entry is a deliverable path: it must default to lightened bridges. Use `include_lightening=False` only for targeted debug or speed tests.
