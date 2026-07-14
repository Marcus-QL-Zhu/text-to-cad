from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
WATCH_OUTPUT_GITKEEP = "models/watch_kinematic/outputs/.gitkeep"


def git_files(*paths: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def tracked_files(*paths: str) -> list[str]:
    return [line for line in git_files(*paths) if line and not line.endswith("/.gitkeep")]


def ignored_files(*paths: str) -> list[str]:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", *paths],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def test_generated_model_outputs_are_not_tracked():
    assert tracked_files(
        "models/watch_kinematic/outputs",
        "models/planetary_reducer/outputs",
    ) == []


def test_generated_model_outputs_are_ignored():
    generated_outputs = [
        "models/watch_kinematic/outputs/generated.step",
        "models/planetary_reducer/outputs/generated.step",
    ]

    assert ignored_files(*generated_outputs) == generated_outputs


def test_watch_output_gitkeep_exists_is_tracked_and_unignored():
    assert (ROOT / WATCH_OUTPUT_GITKEEP).is_file()
    assert git_files(WATCH_OUTPUT_GITKEEP) == [WATCH_OUTPUT_GITKEEP]
    assert ignored_files(WATCH_OUTPUT_GITKEEP) == []
