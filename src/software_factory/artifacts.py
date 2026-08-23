from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .contracts import ArtifactSet, CodeBundle, GeneratedFile, ReleaseArtifact


def assemble_artifacts(sets: list[ArtifactSet]) -> CodeBundle:
    files: dict[str, GeneratedFile] = {}
    for artifact_set in sets:
        for file in artifact_set.files:
            existing = files.get(file.path)
            if existing is not None and existing.content != file.content:
                raise ValueError(f"Conflicting generated artifact: {file.path}")
            files[file.path] = file
    return CodeBundle(files=list(files.values()))


class ReleaseManager:
    def create(self, project_dir: Path, files: list[str]) -> ReleaseArtifact:
        project_dir = project_dir.resolve()
        metadata_dir = project_dir / ".factory"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        release_path = metadata_dir / "release.zip"
        temp_path = metadata_dir / "release.zip.tmp"

        source_files = sorted(set(files))
        if not source_files:
            raise ValueError("Cannot create an empty release")
        manifest_files: list[dict[str, object]] = []
        with ZipFile(temp_path, "w", compression=ZIP_DEFLATED) as archive:
            for relative in source_files:
                path = (project_dir / relative).resolve()
                if project_dir not in path.parents or not path.is_file():
                    raise ValueError(f"Release source is outside workspace or missing: {relative}")
                data = path.read_bytes()
                manifest_files.append(
                    {
                        "path": relative,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "bytes": len(data),
                    }
                )
                self._writestr(archive, relative, data)
            manifest = json.dumps(
                {"schema_version": 1, "files": manifest_files},
                indent=2,
                sort_keys=True,
            ).encode("utf-8")
            self._writestr(archive, "release-manifest.json", manifest)
        os.replace(temp_path, release_path)
        digest = hashlib.sha256(release_path.read_bytes()).hexdigest()
        return ReleaseArtifact(
            path=str(release_path),
            sha256=digest,
            file_count=len(source_files),
        )

    @staticmethod
    def _writestr(archive: ZipFile, name: str, data: bytes) -> None:
        info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, data)
