import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ASSET = (
    ROOT
    / "models/watch_kinematic/references/escapement/swiss_lever_grabcad_snapshot_15"
)
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
PAYLOAD_FILES = {
    "Escape Wheel.STL",
    "Escapement Model.STEP",
    "exp.png",
    "openSCAD/Balance Wheel Pin.DXF",
    "openSCAD/Balance Wheel.DXF",
    "openSCAD/Escapamento.scad",
    "openSCAD/Escapamento.stl",
    "openSCAD/Escape Wheel.DXF",
    "openSCAD/notas.txt",
    "openSCAD/Pallets.DXF",
    "render1.png",
    "render2.png",
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


def test_complete_escapement_payload_is_published():
    source = json.loads((ASSET / "SOURCE.json").read_text(encoding="utf-8"))

    for key, expected in SOURCE_METADATA.items():
        assert source[key] == expected
    assert set(source["files"]) == PAYLOAD_FILES
    assert (ASSET / "Escapement Model.STEP").exists()
    for relative_path, expected in source["files"].items():
        actual = hashlib.sha256((ASSET / relative_path).read_bytes()).hexdigest()
        assert actual == expected


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
