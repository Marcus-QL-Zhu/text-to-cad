import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
ASSET = (
    ROOT
    / "models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15"
)
ASSET_REPO_PATH = ASSET.relative_to(ROOT).as_posix()
SOURCE_METADATA = {
    "title": "Swiss Lever Watch Escapement Model",
    "creator": "David Velez",
    "source_url": "https://grabcad.com/library/swiss-lever-watch-escapement-model-1",
    "published_date": "2020-11-16",
    "snapshot_name": "swiss-lever-watch-escapement-model-1.snapshot.15.zip",
    "snapshot_sha256": (
        "8c7a49df842f35cd748c0d7c5ffc0b3c118b6b5de0543bacb73b4683c3c35bff"
    ),
    "usage_policy": (
        "GrabCAD attributed non-commercial public use; commercial public use "
        "requires creator permission"
    ),
}
# Canonical values from `git -c core.autocrlf=false archive` at the accepted commit.
CANONICAL_PAYLOAD = {
    "Escape Wheel.STL": (
        22_384,
        "eb3e2915fc3f7130aee78c03f86421f17f0cd068a2202d746677fce8c1c90332",
    ),
    "Escapement Model.STEP": (
        1_190_969,
        "313e49a2c323b84d68c2aa47df92ef0c1368338601df83cc9e320cde751c4eae",
    ),
    "exp.png": (
        366_797,
        "281c955a7ed0c863ad2abe48e3fdc8cf674e15f374bac45f72357eb92d062df0",
    ),
    "openSCAD/Balance Wheel Pin.DXF": (
        19_235,
        "20e535fbef03d6ff4dbcc7066aa6c42486c05e1477de565725d28241c573d7b7",
    ),
    "openSCAD/Balance Wheel.DXF": (
        22_329,
        "a44fb72eb4405d092c47d1345665c65805c3d34594c8d1b8f41e63108cd7bf5e",
    ),
    "openSCAD/Escapamento.scad": (
        3_743,
        "efd4a74a715f3b25a0a3d0cff9e1d6f51f784a1e1028bd97b2adf5eaa73b4a78",
    ),
    "openSCAD/Escapamento.stl": (
        3_063_092,
        "8141af942847e88ed9b20085fdd5992699d8d356197269f1be41766c27bc13e9",
    ),
    "openSCAD/Escape Wheel.DXF": (
        27_479,
        "42e3366fe93cb5104d813b3cff3bd35b6ec8943b0883aa4c8d19788e14c1704d",
    ),
    "openSCAD/notas.txt": (
        182,
        "d2dfa7e83d80f0965fbd336f8babab73d8a2abe0e1645708773c708b4d25238d",
    ),
    "openSCAD/Pallets.DXF": (
        24_000,
        "267d58aa05e14329c4ba7f40d0c2689079580543b0a7a9a0508420c3839d444b",
    ),
    "render1.png": (
        582_953,
        "19c371dff29c8ff1cd9588f322b2e8243276d894b98173cc0259baa1524e6ff5",
    ),
    "render2.png": (
        552_069,
        "a6a42e5ee039648986bcf0cd3e7c8281b11f112e1db37e1df8232f2b6cc7bcda",
    ),
}
PAYLOAD_FILES = set(CANONICAL_PAYLOAD)
LFS_PAYLOAD_FILES = {
    "Escape Wheel.STL",
    "Escapement Model.STEP",
    "openSCAD/Balance Wheel Pin.DXF",
    "openSCAD/Balance Wheel.DXF",
    "openSCAD/Escapamento.stl",
    "openSCAD/Escape Wheel.DXF",
    "openSCAD/Pallets.DXF",
}
NON_LFS_TEXT_FILES = {
    "openSCAD/Escapamento.scad",
    "openSCAD/notas.txt",
}
DOCUMENTATION_FILES = {"README.md", "LICENSE.grabcad.md"}
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
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def git_attributes(relative_path: str) -> dict[str, str]:
    repository_path = f"{ASSET_REPO_PATH}/{relative_path}"
    output = subprocess.run(
        [
            "git",
            "check-attr",
            "filter",
            "diff",
            "merge",
            "text",
            "--",
            repository_path,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {
        attribute: value
        for line in output.splitlines()
        for _, attribute, value in [line.split(": ", 2)]
    }


def test_complete_escapement_payload_is_published():
    source = json.loads((ASSET / "SOURCE.json").read_text(encoding="utf-8"))

    for key, expected in SOURCE_METADATA.items():
        assert source[key] == expected
    assert source["files"] == {
        relative_path: sha256
        for relative_path, (_, sha256) in CANONICAL_PAYLOAD.items()
    }
    assert (ASSET / "Escapement Model.STEP").exists()
    for relative_path, (expected_size, expected_sha256) in CANONICAL_PAYLOAD.items():
        payload = (ASSET / relative_path).read_bytes()
        assert len(payload) == expected_size
        assert hashlib.sha256(payload).hexdigest() == expected_sha256


def test_hash_manifest_covers_payload_without_documentation_recursion():
    source = json.loads((ASSET / "SOURCE.json").read_text(encoding="utf-8"))
    distributed_payload = {
        path.relative_to(ASSET).as_posix()
        for path in ASSET.rglob("*")
        if path.is_file()
        and path.name not in {"SOURCE.json", "README.md", "LICENSE.grabcad.md"}
    }

    assert distributed_payload == PAYLOAD_FILES
    assert set(source["files"]) == distributed_payload
    assert set(source["files"]).isdisjoint(DOCUMENTATION_FILES)


def test_git_index_preserves_canonical_payload_bytes_and_lfs_objects():
    for relative_path, (expected_size, expected_sha256) in CANONICAL_PAYLOAD.items():
        repository_path = f"{ASSET_REPO_PATH}/{relative_path}"
        staged = git_bytes("show", f":{repository_path}")

        if relative_path in LFS_PAYLOAD_FILES:
            assert staged == (
                "version https://git-lfs.github.com/spec/v1\n"
                f"oid sha256:{expected_sha256}\n"
                f"size {expected_size}\n"
            ).encode("ascii")
        else:
            assert len(staged) == expected_size
            assert hashlib.sha256(staged).hexdigest() == expected_sha256
            assert staged == (ASSET / relative_path).read_bytes()


def test_payload_attributes_disable_checkout_text_conversion():
    for relative_path in LFS_PAYLOAD_FILES:
        attributes = git_attributes(relative_path)
        assert attributes == {
            "filter": "lfs",
            "diff": "lfs",
            "merge": "lfs",
            "text": "unset",
        }

    for relative_path in NON_LFS_TEXT_FILES:
        attributes = git_attributes(relative_path)
        assert attributes["diff"] == "unset"
        assert attributes["merge"] == "unset"
        assert attributes["text"] == "unset"


def test_redistribution_notices_preserve_required_policy_language():
    notices = [
        ROOT / "THIRD_PARTY_ASSETS.md",
        ASSET / "README.md",
        ASSET / "LICENSE.grabcad.md",
    ]

    for notice_path in notices:
        notice = notice_path.read_text(encoding="utf-8")
        assert NOTICE_TEXT in notice
        for link in GUIDANCE_LINKS:
            assert link in notice
