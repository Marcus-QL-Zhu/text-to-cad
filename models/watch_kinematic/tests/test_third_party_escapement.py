import hashlib
import json
from pathlib import Path
import subprocess

from watch_kinematic.third_party_escapement import (
    EXTRACTION_DIR,
    SOURCE_ARCHIVE,
    SOURCE_ARCHIVE_SHA256,
    resolve_escapement_step,
)


ROOT = Path(__file__).resolve().parents[3]
ASSET = SOURCE_ARCHIVE.parent
ARCHIVE_REPO_PATH = SOURCE_ARCHIVE.relative_to(ROOT).as_posix()
NOTICE_TEXT = (
    "These CAD files remain owned by their original creator, David Velez.\n"
    "They are not covered by the repository license.\n"
    "Original model: "
    "https://grabcad.com/library/swiss-lever-watch-escapement-model-1\n"
    "Public non-commercial redistribution requires attribution under GrabCAD guidance.\n"
    "Commercial public use requires explicit permission from the creator.\n"
    "Removing this payload makes the generated watch power chain mechanically incomplete."
)
GUIDANCE_LINKS = {
    "https://help.grabcad.com/article/246-how-can-models-be-used-and-shared",
    "https://help.grabcad.com/article/149-community-values-and-guidelines",
}


def git_bytes(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True
    ).stdout


def test_original_archive_is_the_only_published_model_payload():
    source = json.loads((ASSET / "SOURCE.json").read_text(encoding="utf-8"))

    assert SOURCE_ARCHIVE.is_file()
    assert hashlib.sha256(SOURCE_ARCHIVE.read_bytes()).hexdigest() == SOURCE_ARCHIVE_SHA256
    assert source["snapshot_sha256"] == SOURCE_ARCHIVE_SHA256

    tracked = subprocess.run(
        ["git", "ls-files", "--", ASSET.relative_to(ROOT).as_posix()],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert tracked == [
        f"{ASSET.relative_to(ROOT).as_posix()}/LICENSE.grabcad.md",
        f"{ASSET.relative_to(ROOT).as_posix()}/README.md",
        f"{ASSET.relative_to(ROOT).as_posix()}/SOURCE.json",
        ARCHIVE_REPO_PATH,
    ]


def test_original_archive_is_stored_through_lfs():
    pointer = git_bytes("show", f":{ARCHIVE_REPO_PATH}").decode("ascii")
    assert pointer == (
        "version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{SOURCE_ARCHIVE_SHA256}\n"
        f"size {SOURCE_ARCHIVE.stat().st_size}\n"
    )


def test_verified_archive_extracts_required_step_to_ignored_cache():
    step_path = resolve_escapement_step()
    assert step_path == EXTRACTION_DIR / "Escapement Model.STEP"
    assert step_path.is_file()
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", step_path.relative_to(ROOT).as_posix()],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert ignored == step_path.relative_to(ROOT).as_posix()


def test_redistribution_notices_preserve_required_policy_language():
    notices = [ROOT / "THIRD_PARTY_ASSETS.md", ASSET / "README.md", ASSET / "LICENSE.grabcad.md"]
    for notice_path in notices:
        notice = notice_path.read_text(encoding="utf-8")
        assert NOTICE_TEXT in notice
        for link in GUIDANCE_LINKS:
            assert link in notice
