"""Staged duplicate detection; full SHA-256 runs only for viable candidates."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from .scanner import FileEntry


def _hash(path: Path, limit: int | None = None) -> str:
    digest = hashlib.sha256()
    remaining = limit
    with path.open("rb") as handle:
        while chunk := handle.read(min(1024 * 1024, remaining) if remaining else 1024 * 1024):
            digest.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
                if remaining <= 0:
                    break
    return digest.hexdigest()


def find_duplicates(files: list[FileEntry], partial_bytes: int = 64 * 1024) -> list[list[FileEntry]]:
    by_size: dict[int, list[FileEntry]] = defaultdict(list)
    for item in files:
        if item.size_bytes:
            by_size[item.size_bytes].append(item)
    matches: list[list[FileEntry]] = []
    for candidates in by_size.values():
        if len(candidates) < 2:
            continue
        partial: dict[str, list[FileEntry]] = defaultdict(list)
        for item in candidates:
            try:
                partial[_hash(item.path, partial_bytes)].append(item)
            except OSError:
                continue
        for stage_two in partial.values():
            if len(stage_two) < 2:
                continue
            full: dict[str, list[FileEntry]] = defaultdict(list)
            for item in stage_two:
                try:
                    full[_hash(item.path)].append(item)
                except OSError:
                    continue
            matches.extend(sorted(group, key=lambda item: str(item.path).casefold()) for group in full.values() if len(group) > 1)
    return sorted(matches, key=lambda group: str(group[0].path).casefold())
