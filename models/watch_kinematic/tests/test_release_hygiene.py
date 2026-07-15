from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
WATCH_OUTPUT_GITKEEP = "models/watch_kinematic/outputs/.gitkeep"
MODEL_EXTENSIONS = {
    ".step", ".stp", ".stl", ".glb", ".gltf", ".3mf", ".obj", ".ply",
    ".iges", ".igs", ".brep", ".fcstd", ".sldprt", ".sldasm", ".x_t",
    ".x_b", ".jt", ".sat", ".sab", ".dxf", ".dwg", ".gcode",
}
THIRD_PARTY_ARCHIVE = (
    "models/watch_kinematic/references/escapement/"
    "swiss_lever_grabcad_snapshot_15/"
    "swiss-lever-watch-escapement-model-1.snapshot.15.zip"
)


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


def test_no_model_or_drawing_format_is_tracked():
    tracked = git_files()
    offenders = [path for path in tracked if Path(path).suffix.lower() in MODEL_EXTENSIONS]
    assert offenders == []


def test_model_formats_are_ignored_outside_output_directories_too():
    candidates = [
        "models/reference_assemblies/example.step",
        "docs/public/hero/example.glb",
        "scratch/example.dxf",
    ]
    assert ignored_files(*candidates) == candidates


def test_only_the_original_third_party_archive_is_the_binary_model_source():
    assert git_files(THIRD_PARTY_ARCHIVE) == [THIRD_PARTY_ARCHIVE]


def test_watch_output_gitkeep_exists_is_tracked_and_unignored():
    assert (ROOT / WATCH_OUTPUT_GITKEEP).is_file()
    assert git_files(WATCH_OUTPUT_GITKEEP) == [WATCH_OUTPUT_GITKEEP]
    assert ignored_files(WATCH_OUTPUT_GITKEEP) == []
