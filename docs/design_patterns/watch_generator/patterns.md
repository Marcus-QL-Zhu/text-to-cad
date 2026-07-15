# Watch Generator Patterns

The watch generator publishes exactly three public patterns through
[`generate_watch.py`](../../../models/watch_kinematic/generate_watch.py):

| Pattern | Name | Exact builder mapping | Canonical card package |
| --- | --- | --- | --- |
| `1` | Central Hour/Minute With Off-Center Seconds | `build_partitioned_bridge_stage` | `central_hour_minute_offcenter_seconds` |
| `2` | Separate Hour And Minute Display Without Seconds | `build_separate_display_partitioned_bridge_stage` | `separate_hour_minute_no_seconds` |
| `3` | Independent Hour And Minute Display Without Seconds | `build_pattern3_independent_display_complete_model` | `independent_hour_minute_no_seconds` |

The builder functions are defined in
[`partitioned_bridge_stage.py`](../../../models/watch_kinematic/watch_kinematic/partitioned_bridge_stage.py)
and are called through the public `PATTERN_BUILDERS` mapping. Do not expose a
pattern by calling an internal solver or review writer directly.

## Pattern 1

Pattern 1 generates central hour and minute hands with an off-center seconds
hand. Its card package is `central_hour_minute_offcenter_seconds`; the public
builder is `build_partitioned_bridge_stage`.

```powershell
python models/watch_kinematic/generate_watch.py --pattern 1 --seed 731 --max-attempts 3
```

## Pattern 2

Pattern 2 generates hour and minute displays on separate axes without a seconds
display. Its card package is `separate_hour_minute_no_seconds`; the public
builder is `build_separate_display_partitioned_bridge_stage`.

```powershell
python models/watch_kinematic/generate_watch.py --pattern 2 --seed 8459 --max-attempts 3
```

## Pattern 3

Pattern 3 generates independent hour and minute branches from the going train,
without a seconds display. Its card package is
`independent_hour_minute_no_seconds`; the public builder is
`build_pattern3_independent_display_complete_model`.

```powershell
python models/watch_kinematic/generate_watch.py --pattern 3 --seed 731 --max-attempts 3
```

The accepted original Pattern 4 implementation was promoted to the sole
canonical Pattern 3 and the superseded early Pattern 3 was removed. New code,
documentation, commands, and tests must use only the canonical Pattern 3
identity.

## Seeds And Publication

`--seed` makes the first attempt explicit. Without it, the entry point selects a
random 32-bit first seed. Retries use distinct random seeds, including after an
explicit first seed. Each attempt receives a private directory under a staging
directory in the target output location. Failed attempts are deleted and never
published.

`--output-dir` may name a missing directory or an existing empty directory; a
non-empty target fails. Without it, the target is the deterministic
system-temporary directory
`ontology-watch-pattern-<two-digit-pattern>-seed-<first-seed>` (for example,
`ontology-watch-pattern-01-seed-731`). The default target is created when
absent or reused when empty, and fails when non-empty. On success, the target
contains only the successful artifact paths plus `run_record.json`. The run
record reports the requested seed, all attempted seeds, the successful seed,
and the number of attempts.
