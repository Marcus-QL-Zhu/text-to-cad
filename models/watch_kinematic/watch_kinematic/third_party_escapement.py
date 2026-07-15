"""Resolve the attributed Swiss-lever reference from its original archive."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import tempfile
import zipfile


REFERENCE_DIR = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "escapement"
    / "swiss_lever_grabcad_snapshot_15"
)
SOURCE_ARCHIVE = REFERENCE_DIR / "swiss-lever-watch-escapement-model-1.snapshot.15.zip"
EXTRACTION_DIR = REFERENCE_DIR / "_extracted"
SOURCE_STEP_RELATIVE = Path("Escapement Model.STEP")
SOURCE_ARCHIVE_SHA256 = "8c7a49df842f35cd748c0d7c5ffc0b3c118b6b5de0543bacb73b4683c3c35bff"


def resolve_escapement_step() -> Path:
    """Return the source STEP, extracting the verified archive when necessary."""

    step_path = EXTRACTION_DIR / SOURCE_STEP_RELATIVE
    if step_path.is_file():
        return step_path

    if not SOURCE_ARCHIVE.is_file():
        raise FileNotFoundError(
            f"Third-party escapement archive is missing: {SOURCE_ARCHIVE}"
        )
    archive_sha256 = hashlib.sha256(SOURCE_ARCHIVE.read_bytes()).hexdigest()
    if archive_sha256 != SOURCE_ARCHIVE_SHA256:
        raise ValueError(
            "Third-party escapement archive checksum mismatch: "
            f"expected {SOURCE_ARCHIVE_SHA256}, got {archive_sha256}"
        )

    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="escapement-extract-", dir=REFERENCE_DIR) as temp:
        temp_dir = Path(temp)
        with zipfile.ZipFile(SOURCE_ARCHIVE) as archive:
            for member in archive.infolist():
                destination = (temp_dir / member.filename).resolve()
                if temp_dir.resolve() not in destination.parents and destination != temp_dir.resolve():
                    raise ValueError(f"Unsafe archive path: {member.filename}")
            archive.extractall(temp_dir)
        if not (temp_dir / SOURCE_STEP_RELATIVE).is_file():
            raise FileNotFoundError(
                f"Archive does not contain {SOURCE_STEP_RELATIVE.as_posix()}"
            )
        if EXTRACTION_DIR.exists():
            shutil.rmtree(EXTRACTION_DIR)
        shutil.move(str(temp_dir), str(EXTRACTION_DIR))

    return step_path
