import json
from pathlib import Path
import subprocess
import sys

import pytest

from models.watch_kinematic import generate_watch as generate_watch_module
from models.watch_kinematic.generate_watch import (
    GenerationResult,
    PATTERN_BUILDERS,
    WatchGenerationError,
    _remap_paths,
    generate_watch,
    main,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / "models" / "watch_kinematic" / "generate_watch.py"


def _passing_result(output_dir: Path, seed: int) -> dict:
    step = output_dir / "model.step"
    step.write_text(f"seed={seed}", encoding="utf-8")
    return {"status": "pass", "artifacts": {"step": str(step)}}


def _generation_result(tmp_path: Path) -> GenerationResult:
    step_path = tmp_path / "model.step"
    step_path.write_text("ok", encoding="utf-8")
    return GenerationResult(
        status="pass",
        pattern=2,
        requested_seed=41,
        successful_seed=41,
        attempt_count=1,
        attempted_seeds=(41,),
        output_dir=tmp_path,
        step_path=step_path,
        report={"status": "pass", "artifacts": {"step": str(step_path)}},
    )


def test_public_pattern_mapping_uses_accepted_builders():
    assert PATTERN_BUILDERS[1].__name__ == "build_partitioned_bridge_stage"
    assert PATTERN_BUILDERS[2].__name__ == "build_separate_display_partitioned_bridge_stage"
    assert PATTERN_BUILDERS[3].__name__ == "build_pattern3_independent_display_complete_model"


def test_failed_seed_retries_in_isolated_directories_without_publishing_failed_step(monkeypatch, tmp_path):
    attempted = []
    attempt_dirs = []
    random_seeds = iter((7333, 7444))

    def fake_builder(output_dir, *, seed, include_lightening=True):
        attempted.append(seed)
        attempt_dirs.append(Path(output_dir))
        assert include_lightening is True
        if len(attempted) == 1:
            (Path(output_dir) / "failed.step").write_text("failed", encoding="utf-8")
            raise ValueError("solver failed")
        return _passing_result(Path(output_dir), seed)

    monkeypatch.setitem(PATTERN_BUILDERS, 3, fake_builder)
    monkeypatch.setattr(generate_watch_module.secrets, "randbits", lambda _bits: next(random_seeds))

    result = generate_watch(pattern=3, seed=7333, max_attempts=2, output_dir=tmp_path)

    assert result.status == "pass"
    assert result.requested_seed == 7333
    assert result.successful_seed == 7444
    assert result.attempt_count == 2
    assert result.attempted_seeds == (7333, 7444)
    assert attempted == [7333, 7444]
    assert len(set(attempt_dirs)) == 2
    assert all(path != tmp_path for path in attempt_dirs)
    assert all(tmp_path not in path.parents for path in attempt_dirs)
    assert result.step_path == tmp_path / "model.step"
    assert result.step_path.is_file()
    assert not list(tmp_path.rglob("failed.step"))
    assert not [path for path in tmp_path.iterdir() if path.is_dir()]


def test_random_first_seed_and_retries_are_distinct(monkeypatch, tmp_path):
    attempted = []
    random_seeds = iter((101, 101, 202))

    def fake_builder(output_dir, *, seed, include_lightening=True):
        attempted.append(seed)
        if len(attempted) == 1:
            return {"status": "fail", "artifacts": {}}
        return _passing_result(Path(output_dir), seed)

    monkeypatch.setitem(PATTERN_BUILDERS, 1, fake_builder)
    monkeypatch.setattr(generate_watch_module.secrets, "randbits", lambda _bits: next(random_seeds))

    result = generate_watch(pattern=1, seed=None, max_attempts=2, output_dir=tmp_path)

    assert result.requested_seed is None
    assert result.attempted_seeds == (101, 202)
    assert result.successful_seed == 202
    assert attempted == [101, 202]


def test_success_run_record_captures_attempts_and_failures(monkeypatch, tmp_path):
    def fake_builder(output_dir, *, seed, include_lightening=True):
        if seed == 17:
            raise RuntimeError("hard validation failed")
        return _passing_result(Path(output_dir), seed)

    monkeypatch.setitem(PATTERN_BUILDERS, 2, fake_builder)
    monkeypatch.setattr(generate_watch_module.secrets, "randbits", lambda _bits: 23)

    result = generate_watch(pattern=2, seed=17, max_attempts=2, output_dir=tmp_path)
    record = json.loads((tmp_path / "run_record.json").read_text(encoding="utf-8"))

    assert record == {
        "status": "pass",
        "pattern": 2,
        "requested_seed": 17,
        "successful_seed": 23,
        "attempt_count": 2,
        "attempted_seeds": [17, 23],
        "failures": [{"seed": 17, "message": "hard validation failed"}],
        "output_dir": str(tmp_path.resolve()),
        "step_path": str(result.step_path),
    }


def test_all_attempts_fail_writes_failed_record_without_successful_seed_or_step(monkeypatch, tmp_path):
    def fake_builder(output_dir, *, seed, include_lightening=True):
        failed_step = Path(output_dir) / f"failed-{seed}.step"
        failed_step.write_text("failed", encoding="utf-8")
        return {"status": "fail", "artifacts": {"step": str(failed_step)}}

    monkeypatch.setitem(PATTERN_BUILDERS, 2, fake_builder)
    monkeypatch.setattr(generate_watch_module.secrets, "randbits", lambda _bits: 29)

    with pytest.raises(WatchGenerationError, match="failed after 2 attempts") as raised:
        generate_watch(pattern=2, seed=19, max_attempts=2, output_dir=tmp_path)

    error = raised.value
    assert error.attempted_seeds == (19, 29)
    assert error.run_record_path == tmp_path.resolve() / "run_record.json"
    record = json.loads(error.run_record_path.read_text(encoding="utf-8"))
    assert record["status"] == "fail"
    assert record["attempt_count"] == 2
    assert record["attempted_seeds"] == [19, 29]
    assert len(record["failures"]) == 2
    assert "successful_seed" not in record
    assert not list(tmp_path.rglob("*.step"))
    assert [path.name for path in tmp_path.iterdir()] == ["run_record.json"]


def test_pass_report_without_existing_step_is_rejected(monkeypatch, tmp_path):
    def fake_builder(output_dir, *, seed, include_lightening=True):
        missing = Path(output_dir) / "missing.step"
        return {"status": "pass", "artifacts": {"step": str(missing)}}

    monkeypatch.setitem(PATTERN_BUILDERS, 1, fake_builder)

    with pytest.raises(WatchGenerationError) as raised:
        generate_watch(pattern=1, seed=5, max_attempts=1, output_dir=tmp_path)

    assert "existing STEP" in raised.value.failures[0]["message"]
    assert not list(tmp_path.rglob("*.step"))


@pytest.mark.parametrize("pattern", [0, 4, "1", True])
def test_invalid_pattern_is_rejected(pattern, tmp_path):
    with pytest.raises(ValueError, match="pattern"):
        generate_watch(pattern=pattern, seed=1, max_attempts=1, output_dir=tmp_path)


@pytest.mark.parametrize("max_attempts", [0, -1, 2**32 + 1, 1.5, True])
def test_invalid_max_attempts_is_rejected(max_attempts, tmp_path):
    with pytest.raises(ValueError, match="max_attempts"):
        generate_watch(pattern=1, seed=1, max_attempts=max_attempts, output_dir=tmp_path)


def test_default_output_root_uses_temp_directory_pattern_and_first_seed(monkeypatch, tmp_path):
    monkeypatch.setitem(PATTERN_BUILDERS, 1, lambda output_dir, *, seed, include_lightening=True: _passing_result(Path(output_dir), seed))
    monkeypatch.setattr(generate_watch_module.tempfile, "gettempdir", lambda: str(tmp_path))

    result = generate_watch(pattern=1, seed=99, max_attempts=1, output_dir=None)

    assert result.output_dir == tmp_path / "ontology-watch-pattern-01-seed-99"


def test_nonempty_output_directory_is_not_overwritten(monkeypatch, tmp_path):
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="not empty"):
        generate_watch(pattern=1, seed=1, max_attempts=1, output_dir=tmp_path)

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_cli_rejects_invalid_pattern():
    with pytest.raises(SystemExit) as raised:
        main(["--pattern", "4"])

    assert raised.value.code == 2


@pytest.mark.parametrize(
    "command",
    [
        [sys.executable, str(SCRIPT_PATH), "--help"],
        [sys.executable, "-m", "models.watch_kinematic.generate_watch", "--help"],
    ],
    ids=("direct-script", "module"),
)
def test_cli_help_works_for_direct_script_and_module_invocation(command):
    result = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--pattern {1,2,3}" in result.stdout
    assert "--max-attempts" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--open" in result.stdout


def test_remap_paths_recurses_through_dict_list_and_tuple(tmp_path):
    attempt = (tmp_path / "attempt").resolve()
    published = (tmp_path / "published").resolve()
    nested = attempt / "nested" / "model.step"
    payload = {
        "dict_value": str(nested),
        "list_value": [nested],
        "tuple_value": (str(nested),),
    }

    remapped = _remap_paths(payload, attempt, published)
    expected = published / "nested" / "model.step"

    assert remapped["dict_value"] == str(expected)
    assert remapped["list_value"] == [expected]
    assert remapped["tuple_value"] == (str(expected),)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path equivalence contract")
def test_remap_paths_accepts_equivalent_windows_case_and_separator_variants(tmp_path):
    attempt = (tmp_path / "AttemptRoot").resolve()
    published = (tmp_path / "published").resolve()
    variant_root = str(attempt).swapcase().replace("\\", "/")
    variant = f"{variant_root}/nested/model.step"

    remapped = _remap_paths(variant, attempt, published)

    assert Path(remapped) == published / "nested" / "model.step"


def test_remap_paths_does_not_remap_sibling_with_shared_text_prefix(tmp_path):
    attempt = (tmp_path / "attempt").resolve()
    published = (tmp_path / "published").resolve()
    sibling = attempt.with_name(f"{attempt.name}-backup") / "model.step"

    remapped = _remap_paths(str(sibling), attempt, published)

    assert remapped == str(sibling)


def test_open_calls_native_artifact_and_viewer_commands_in_order(monkeypatch, tmp_path):
    result = _generation_result(tmp_path)
    calls = []
    monkeypatch.setattr(generate_watch_module, "generate_watch", lambda **_kwargs: result)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"url":"http://127.0.0.1:4173/?dir=C%3A%2Ftmp%2Fwatch","port":4173,"action":"reuse"}\n',
        )

    monkeypatch.setattr(generate_watch_module.subprocess, "run", fake_run)

    exit_code = main(["--pattern", "2", "--seed", "41", "--max-attempts", "1", "--output-dir", str(tmp_path), "--open"])

    assert exit_code == 0
    assert calls == [
        (
            [
                sys.executable,
                "skills/cad/scripts/step",
                "--kind",
                "assembly",
                str(result.step_path),
            ],
            {
                "cwd": Path(generate_watch_module.__file__).resolve().parents[2],
                "check": True,
            },
        ),
        (
            [
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
            ],
            {
                "cwd": Path(generate_watch_module.__file__).resolve().parents[2],
                "check": True,
                "capture_output": True,
                "text": True,
            },
        ),
    ]


def test_open_prints_native_explorer_review_url(monkeypatch, tmp_path, capsys):
    result = _generation_result(tmp_path)
    monkeypatch.setattr(generate_watch_module, "generate_watch", lambda **_kwargs: result)

    def fake_run(command, **_kwargs):
        stdout = ""
        if command[:4] == ["npm", "--prefix", "viewer", "run"]:
            stdout = (
                "CAD Viewer already running\n"
                '{"url":"http://127.0.0.1:4173/?dir=C%3A%2Ftmp%2Fwatch","port":4173,"action":"reuse"}\n'
            )
        return subprocess.CompletedProcess(command, 0, stdout=stdout)

    monkeypatch.setattr(generate_watch_module.subprocess, "run", fake_run)

    assert main(["--pattern", "2", "--open"]) == 0

    assert (
        "Explorer URL: "
        "http://127.0.0.1:4173/?dir=C%3A%2Ftmp%2Fwatch&file=model.step"
    ) in capsys.readouterr().out


def test_open_native_step_failure_returns_nonzero(monkeypatch, tmp_path):
    result = _generation_result(tmp_path)
    monkeypatch.setattr(generate_watch_module, "generate_watch", lambda **_kwargs: result)

    def fail_run(command, *, cwd, check):
        raise subprocess.CalledProcessError(7, command)

    monkeypatch.setattr(generate_watch_module.subprocess, "run", fail_run)

    assert main(["--pattern", "2", "--open"]) == 7


def test_cli_all_fail_domain_error_returns_nonzero(monkeypatch, tmp_path):
    run_record_path = tmp_path / "run_record.json"

    def fail_generation(**_kwargs):
        raise WatchGenerationError(
            pattern=3,
            attempted_seeds=(11,),
            failures=({"seed": 11, "message": "solver failed"},),
            output_dir=tmp_path,
            run_record_path=run_record_path,
        )

    monkeypatch.setattr(generate_watch_module, "generate_watch", fail_generation)

    assert main(["--pattern", "3"]) != 0
