"""Public three-pattern watch generation and retry orchestration."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    repository_root_text = str(REPOSITORY_ROOT)
    if repository_root_text not in sys.path:
        sys.path.insert(0, repository_root_text)
    from models.watch_kinematic.watch_kinematic.partitioned_bridge_stage import (
        build_partitioned_bridge_stage,
        build_pattern3_independent_display_complete_model,
        build_separate_display_partitioned_bridge_stage,
    )
else:
    from .watch_kinematic.partitioned_bridge_stage import (
        build_partitioned_bridge_stage,
        build_pattern3_independent_display_complete_model,
        build_separate_display_partitioned_bridge_stage,
    )


Builder = Callable[..., dict[str, Any]]
MAX_SEED_COUNT = 2**32
PATTERN_BUILDERS: dict[int, Builder] = {
    1: build_partitioned_bridge_stage,
    2: build_separate_display_partitioned_bridge_stage,
    3: build_pattern3_independent_display_complete_model,
}


@dataclass(frozen=True)
class GenerationResult:
    status: str
    pattern: int
    requested_seed: int | None
    successful_seed: int
    attempt_count: int
    attempted_seeds: tuple[int, ...]
    output_dir: Path
    step_path: Path
    report: dict[str, Any]


class WatchGenerationError(RuntimeError):
    """Raised when no seed produces an acceptable watch model."""

    def __init__(
        self,
        *,
        pattern: int,
        attempted_seeds: tuple[int, ...],
        failures: tuple[dict[str, Any], ...],
        output_dir: Path,
        run_record_path: Path,
    ) -> None:
        self.pattern = pattern
        self.attempted_seeds = attempted_seeds
        self.failures = failures
        self.output_dir = output_dir
        self.run_record_path = run_record_path
        super().__init__(
            f"watch pattern {pattern} generation failed after {len(attempted_seeds)} attempts; "
            f"see {run_record_path}"
        )


def generate_watch(
    pattern: int,
    seed: int | None,
    max_attempts: int,
    output_dir: Path | None,
) -> GenerationResult:
    """Generate one accepted watch pattern, retrying only with distinct seeds."""

    _validate_arguments(pattern, max_attempts)
    requested_seed = seed
    first_seed = seed if seed is not None else secrets.randbits(32)
    target = _prepare_output_dir(pattern, first_seed, output_dir)
    staging_root = Path(tempfile.mkdtemp(prefix=".watch-generation-attempts-", dir=target))
    attempted_seeds: list[int] = []
    failures: list[dict[str, Any]] = []
    current_seed = first_seed

    for attempt_number in range(1, max_attempts + 1):
        attempted_seeds.append(current_seed)
        attempt_dir = staging_root / f"attempt-{attempt_number:02d}-seed-{current_seed}"
        attempt_dir.mkdir()
        try:
            report = PATTERN_BUILDERS[pattern](
                attempt_dir,
                seed=current_seed,
                include_lightening=True,
            )
            attempt_step = _accepted_step_path(report, attempt_dir)
        except Exception as exc:
            failures.append({"seed": current_seed, "message": _failure_message(exc)})
            shutil.rmtree(attempt_dir)
        else:
            published_report, step_path = _publish_success(report, attempt_dir, attempt_step, target)
            shutil.rmtree(staging_root)
            run_record = {
                "status": "pass",
                "pattern": pattern,
                "requested_seed": requested_seed,
                "successful_seed": current_seed,
                "attempt_count": len(attempted_seeds),
                "attempted_seeds": attempted_seeds,
                "failures": failures,
                "output_dir": str(target),
                "step_path": str(step_path),
            }
            _write_run_record(target, run_record)
            return GenerationResult(
                status="pass",
                pattern=pattern,
                requested_seed=requested_seed,
                successful_seed=current_seed,
                attempt_count=len(attempted_seeds),
                attempted_seeds=tuple(attempted_seeds),
                output_dir=target,
                step_path=step_path,
                report=published_report,
            )

        if attempt_number < max_attempts:
            current_seed = _fresh_seed(attempted_seeds)

    shutil.rmtree(staging_root)
    run_record = {
        "status": "fail",
        "pattern": pattern,
        "requested_seed": requested_seed,
        "attempt_count": len(attempted_seeds),
        "attempted_seeds": attempted_seeds,
        "failures": failures,
        "output_dir": str(target),
    }
    run_record_path = _write_run_record(target, run_record)
    raise WatchGenerationError(
        pattern=pattern,
        attempted_seeds=tuple(attempted_seeds),
        failures=tuple(failures),
        output_dir=target,
        run_record_path=run_record_path,
    )


def _validate_arguments(pattern: int, max_attempts: int) -> None:
    if isinstance(pattern, bool) or not isinstance(pattern, int) or pattern not in PATTERN_BUILDERS:
        raise ValueError("pattern must be one of 1, 2, or 3")
    if (
        isinstance(max_attempts, bool)
        or not isinstance(max_attempts, int)
        or not 1 <= max_attempts <= MAX_SEED_COUNT
    ):
        raise ValueError(f"max_attempts must be an integer from 1 through {MAX_SEED_COUNT}")


def _prepare_output_dir(pattern: int, first_seed: int, output_dir: Path | None) -> Path:
    target = (
        Path(output_dir)
        if output_dir is not None
        else Path(tempfile.gettempdir()) / f"ontology-watch-pattern-{pattern:02d}-seed-{first_seed}"
    ).expanduser().resolve()
    if target.exists():
        if not target.is_dir():
            raise FileExistsError(f"output directory path is not a directory: {target}")
        if any(target.iterdir()):
            raise FileExistsError(f"output directory is not empty: {target}")
    else:
        target.mkdir(parents=True)
    return target


def _accepted_step_path(report: dict[str, Any], attempt_dir: Path) -> Path:
    if not isinstance(report, dict) or report.get("status") != "pass":
        status = report.get("status") if isinstance(report, dict) else type(report).__name__
        raise ValueError(f"builder report status is {status!r}; expected 'pass'")
    artifacts = report.get("artifacts")
    raw_step = artifacts.get("step") if isinstance(artifacts, dict) else None
    if not isinstance(raw_step, (str, Path)) or not str(raw_step):
        raise ValueError("pass report did not identify an existing STEP")
    step_path = Path(raw_step)
    if not step_path.is_absolute():
        step_path = attempt_dir / step_path
    step_path = step_path.resolve()
    try:
        step_path.relative_to(attempt_dir.resolve())
    except ValueError as exc:
        raise ValueError("pass report STEP is outside its isolated attempt directory") from exc
    if not step_path.is_file():
        raise ValueError("pass report did not identify an existing STEP")
    return step_path


def _fresh_seed(attempted_seeds: list[int]) -> int:
    attempted = set(attempted_seeds)
    while True:
        candidate = secrets.randbits(32)
        if candidate not in attempted:
            return candidate


def _publish_success(
    report: dict[str, Any],
    attempt_dir: Path,
    attempt_step: Path,
    target: Path,
) -> tuple[dict[str, Any], Path]:
    for child in attempt_dir.iterdir():
        shutil.move(str(child), str(target / child.name))
    published_report = _remap_paths(report, attempt_dir.resolve(), target)
    step_path = target / attempt_step.relative_to(attempt_dir.resolve())
    published_report["artifacts"]["step"] = str(step_path)
    report_path = published_report.get("artifacts", {}).get("report_json")
    if report_path:
        published_report_path = Path(report_path)
        if published_report_path.is_file():
            published_report_path.write_text(
                json.dumps(published_report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    return published_report, step_path


def _remap_paths(value: Any, old_root: Path, new_root: Path) -> Any:
    if isinstance(value, dict):
        return {key: _remap_paths(item, old_root, new_root) for key, item in value.items()}
    if isinstance(value, list):
        return [_remap_paths(item, old_root, new_root) for item in value]
    if isinstance(value, tuple):
        return tuple(_remap_paths(item, old_root, new_root) for item in value)
    if isinstance(value, (str, Path)):
        path = Path(value)
        if not path.is_absolute():
            return value
        try:
            relative = path.resolve().relative_to(old_root.resolve())
        except (OSError, ValueError):
            return value
        remapped = new_root.resolve() / relative
        return str(remapped) if isinstance(value, str) else remapped
    return value


def _failure_message(exc: Exception) -> str:
    return str(exc) or exc.__class__.__name__


def _write_run_record(output_dir: Path, record: dict[str, Any]) -> Path:
    path = output_dir / "run_record.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _explorer_review_url(viewer_stdout: str, result: GenerationResult) -> str:
    payload = None
    for line in reversed(viewer_stdout.splitlines()):
        if line.lstrip().startswith("{"):
            payload = json.loads(line)
            break
    base_url = payload.get("url") if isinstance(payload, dict) else None
    if not isinstance(base_url, str) or not base_url:
        raise ValueError("native Viewer command did not return a review URL")
    relative_step = result.step_path.resolve().relative_to(result.output_dir.resolve()).as_posix()
    parsed = urlsplit(base_url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("file", relative_step))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pattern", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--open", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = generate_watch(
            pattern=args.pattern,
            seed=args.seed,
            max_attempts=args.max_attempts,
            output_dir=args.output_dir,
        )
    except WatchGenerationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (ValueError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": result.status,
                "pattern": result.pattern,
                "requested_seed": result.requested_seed,
                "successful_seed": result.successful_seed,
                "attempt_count": result.attempt_count,
                "attempted_seeds": result.attempted_seeds,
                "output_dir": str(result.output_dir),
                "step_path": str(result.step_path),
            },
            indent=2,
        )
    )
    if args.open:
        artifact_command = [
            sys.executable,
            "skills/cad/scripts/step",
            "--kind",
            "assembly",
            str(result.step_path),
        ]
        viewer_command = [
            "npm",
            "--prefix",
            "viewer",
            "run",
            "agent:start",
            "--",
            "--host",
            "127.0.0.1",
            "--dir",
            str(result.output_dir),
            "--json",
        ]
        try:
            subprocess.run(artifact_command, cwd=REPOSITORY_ROOT, check=True)
            viewer_result = subprocess.run(
                viewer_command,
                cwd=REPOSITORY_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            review_url = _explorer_review_url(viewer_result.stdout, result)
        except subprocess.CalledProcessError as exc:
            print(f"native watch review command failed with exit code {exc.returncode}", file=sys.stderr)
            return exc.returncode if exc.returncode else 1
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"native watch review command failed: {exc}", file=sys.stderr)
            return 1
        print(f"Explorer URL: {review_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
