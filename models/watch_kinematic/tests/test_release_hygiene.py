from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]


def tracked_files(*paths: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", *paths],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line and not line.endswith("/.gitkeep")]


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


def test_generated_model_outputs_are_ignored_but_watch_gitkeep_is_trackable():
    generated_outputs = [
        "models/watch_kinematic/outputs/generated.step",
        "models/planetary_reducer/outputs/generated.step",
    ]

    assert ignored_files(*generated_outputs) == generated_outputs
    assert ignored_files("models/watch_kinematic/outputs/.gitkeep") == []
