#!/usr/bin/env python3
"""Compare root filesystem layer identities from two OCI image archives.

The command exits 0 only when the uncompressed rootfs diff IDs match. When they
differ, it prints the first differing layer and the /proc and /sys metadata from
that layer, then exits 1. This makes the current rootless reproducibility defect
a normal red regression rather than a golden-file workaround.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


INDEX_MEDIA_TYPES = {
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
}


@dataclass(frozen=True)
class OCIImage:
    archive: Path
    blobs: dict[str, bytes]
    manifest: dict[str, Any]
    config: dict[str, Any]

    @classmethod
    def load(cls, archive: Path) -> "OCIImage":
        with tarfile.open(archive, mode="r:*") as stream:
            files: dict[str, bytes] = {}
            for member in stream.getmembers():
                if not member.isfile():
                    continue
                source = stream.extractfile(member)
                if source is None:
                    continue
                files[member.name.removeprefix("./")] = source.read()

        try:
            index = json.loads(files["index.json"])
        except KeyError as exc:
            raise ValueError(f"{archive}: missing index.json") from exc

        blobs: dict[str, bytes] = {}
        for name, data in files.items():
            parts = name.split("/")
            if len(parts) == 3 and parts[0] == "blobs":
                blobs[f"{parts[1]}:{parts[2]}"] = data

        descriptors = index.get("manifests", [])
        if len(descriptors) != 1:
            raise ValueError(
                f"{archive}: expected one top-level manifest, found {len(descriptors)}"
            )

        descriptor = descriptors[0]
        while descriptor.get("mediaType") in INDEX_MEDIA_TYPES:
            nested = json.loads(cls._blob(blobs, descriptor["digest"], archive))
            nested_descriptors = nested.get("manifests", [])
            if len(nested_descriptors) != 1:
                raise ValueError(
                    f"{archive}: expected one platform manifest, found "
                    f"{len(nested_descriptors)}"
                )
            descriptor = nested_descriptors[0]

        manifest = json.loads(cls._blob(blobs, descriptor["digest"], archive))
        config_descriptor = manifest.get("config") or {}
        config_digest = config_descriptor.get("digest")
        if not config_digest:
            raise ValueError(f"{archive}: image manifest has no config digest")
        config = json.loads(cls._blob(blobs, config_digest, archive))
        return cls(archive=archive, blobs=blobs, manifest=manifest, config=config)

    @staticmethod
    def _blob(blobs: dict[str, bytes], digest: str, archive: Path) -> bytes:
        try:
            return blobs[digest]
        except KeyError as exc:
            raise ValueError(f"{archive}: missing blob {digest}") from exc

    @property
    def diff_ids(self) -> list[str]:
        rootfs = self.config.get("rootfs") or {}
        return list(rootfs.get("diff_ids") or [])

    @property
    def layers(self) -> list[dict[str, Any]]:
        return list(self.manifest.get("layers") or [])


def member_type(member: tarfile.TarInfo) -> str:
    if member.isdir():
        return "directory"
    if member.isfile():
        return "file"
    if member.issym():
        return "symlink"
    if member.islnk():
        return "hardlink"
    if member.ischr():
        return "char-device"
    if member.isblk():
        return "block-device"
    if member.isfifo():
        return "fifo"
    return repr(member.type)


def runtime_mountpoint_entries(blob: bytes) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as layer:
        for member in layer.getmembers():
            name = member.name.removeprefix("./").rstrip("/")
            if name not in {"proc", "sys"} and not name.startswith(("proc/", "sys/")):
                continue
            entries.append(
                {
                    "name": name,
                    "type": member_type(member),
                    "mode": f"{member.mode:04o}",
                    "uid": member.uid,
                    "gid": member.gid,
                    "size": member.size,
                    "mtime": member.mtime,
                    "linkname": member.linkname,
                    "pax_headers": dict(sorted(member.pax_headers.items())),
                }
            )
    return entries


def first_difference(left: list[str], right: list[str]) -> int | None:
    for index, pair in enumerate(zip(left, right, strict=False)):
        if pair[0] != pair[1]:
            return index
    if len(left) != len(right):
        return min(len(left), len(right))
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("rootful", type=Path)
    parser.add_argument("rootless", type=Path)
    args = parser.parse_args()

    rootful = OCIImage.load(args.rootful)
    rootless = OCIImage.load(args.rootless)
    difference = first_difference(rootful.diff_ids, rootless.diff_ids)

    summary: dict[str, Any] = {
        "rootful_archive": str(rootful.archive),
        "rootless_archive": str(rootless.archive),
        "rootful_diff_ids": rootful.diff_ids,
        "rootless_diff_ids": rootless.diff_ids,
        "first_differing_layer": difference,
    }

    if difference is None:
        summary["result"] = "rootfs-identical"
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    summary["result"] = "rootfs-different"
    for label, image in (("rootful", rootful), ("rootless", rootless)):
        if difference >= len(image.layers):
            summary[f"{label}_layer"] = None
            summary[f"{label}_runtime_mountpoints"] = []
            continue
        descriptor = image.layers[difference]
        digest = descriptor["digest"]
        summary[f"{label}_layer"] = descriptor
        try:
            summary[f"{label}_runtime_mountpoints"] = runtime_mountpoint_entries(
                image.blobs[digest]
            )
        except tarfile.TarError as exc:
            summary[f"{label}_runtime_mountpoints_error"] = str(exc)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
