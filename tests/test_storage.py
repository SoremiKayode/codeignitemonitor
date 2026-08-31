from pathlib import Path

from netwatch.monitors.storage.duplicate import find_duplicates
from netwatch.monitors.storage.scanner import StorageScanner


def test_scanner_finds_files_and_groups_extensions(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "b.bin").write_bytes(b"abc")
    result = StorageScanner().scan(tmp_path)
    assert result.total_bytes == 8
    assert result.by_extension() == {".txt": 5, ".bin": 3}


def test_duplicate_finder_hashes_only_matching_candidates(tmp_path: Path) -> None:
    (tmp_path / "one.dat").write_bytes(b"same data")
    (tmp_path / "two.dat").write_bytes(b"same data")
    result = StorageScanner().scan(tmp_path)
    groups = find_duplicates(result.files)
    assert [[entry.path.name for entry in group] for group in groups] == [["one.dat", "two.dat"]]
