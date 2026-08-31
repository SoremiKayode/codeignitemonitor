"""Iterative disk scanner that does not follow directory links."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event


DEFAULT_EXCLUSIONS = {"System Volume Information", "Recovery", "WinSxS"}


@dataclass(slots=True)
class FileEntry:
    path: Path
    size_bytes: int


@dataclass(slots=True)
class StorageScanResult:
    root: Path
    files: list[FileEntry] = field(default_factory=list)
    inaccessible: list[Path] = field(default_factory=list)
    cancelled: bool = False

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self.files)

    def by_extension(self) -> Counter[str]:
        """Return bytes grouped by extension without expanding one entry per byte."""
        totals: Counter[str] = Counter()
        for item in self.files:
            totals[item.path.suffix.lower() or "[no extension]"] += item.size_bytes
        return totals


class StorageScanner:
    def scan(self, root: Path, cancel: Event | None = None, excluded_names: set[str] | None = None) -> StorageScanResult:
        root = root.expanduser().resolve()
        result = StorageScanResult(root=root)
        excluded = DEFAULT_EXCLUSIONS | (excluded_names or set())
        pending = [root]
        while pending:
            if cancel and cancel.is_set():
                result.cancelled = True
                break
            directory = pending.pop()
            try:
                for child in directory.iterdir():
                    if cancel and cancel.is_set():
                        result.cancelled = True
                        return result
                    try:
                        if child.is_symlink():
                            continue
                        if child.is_dir():
                            if child.name not in excluded:
                                pending.append(child)
                        elif child.is_file():
                            result.files.append(FileEntry(child, child.stat().st_size))
                    except OSError:
                        result.inaccessible.append(child)
            except OSError:
                result.inaccessible.append(directory)
        return result
