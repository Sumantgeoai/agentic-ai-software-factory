from __future__ import annotations

from .contracts import ArtifactSet, CodeBundle, GeneratedFile


def assemble_artifacts(sets: list[ArtifactSet]) -> CodeBundle:
    files: dict[str, GeneratedFile] = {}
    for artifact_set in sets:
        for file in artifact_set.files:
            existing = files.get(file.path)
            if existing is not None and existing.content != file.content:
                raise ValueError(f"Conflicting generated artifact: {file.path}")
            files[file.path] = file
    return CodeBundle(files=list(files.values()))
