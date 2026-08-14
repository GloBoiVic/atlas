"""Deterministic source provenance for explicitly registered Strategies.

This module is deliberately a registration-time utility.  Evaluation code must
receive the resulting snapshot and never read the filesystem.
"""

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from struct import pack


class SourceValidationError(ValueError):
    """One or more allow-listed source files are not safe to archive."""

    def __init__(self, errors: tuple[str, ...]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True, slots=True)
class SourceFileSnapshot:
    """The exact decoded source and raw byte length for one source path."""

    relative_path: str
    source: str
    byte_length: int

    @property
    def raw_bytes(self) -> bytes:
        return self.source.encode("utf-8")


@dataclass(frozen=True, slots=True)
class SourceArchive:
    """Immutable provenance retained from an explicit local source allow-list."""

    files: tuple[SourceFileSnapshot, ...]
    fingerprint: str

    @property
    def manifest(self) -> tuple[tuple[str, int], ...]:
        return tuple((item.relative_path, item.byte_length) for item in self.files)

    @property
    def exact_source_snapshot(self) -> tuple[tuple[str, bytes], ...]:
        return tuple((item.relative_path, item.raw_bytes) for item in self.files)


_OBVIOUS_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?:OANDA|AWS|STRIPE)[_-]?(?:API|ACCESS|SECRET)?[_-]?KEY\s*[:=]"),
)


def _path_error(path: str, message: str) -> str:
    return f"source_files[{path!r}]: {message}"


def _validate_relative_path(path: str) -> tuple[str, ...]:
    errors: list[str] = []
    if type(path) is not str or not path:
        return (_path_error(str(path), "must be a non-empty POSIX path"),)
    parsed = PurePosixPath(path)
    if "\\" in path or parsed.is_absolute() or not path.startswith("backend/"):
        errors.append(_path_error(path, "must be a relative POSIX path under backend/"))
    if any(part in ("", ".", "..") for part in path.split("/")):
        errors.append(
            _path_error(path, "must not contain empty, '.', or '..' segments")
        )
    return tuple(errors)


def _has_symlink_component(root: Path, relative_path: str) -> bool:
    current = root
    for part in relative_path.split("/"):
        current /= part
        if current.is_symlink():
            return True
    return False


def archive_source(root: Path, source_files: tuple[str, ...]) -> SourceArchive:
    """Read and frame exactly the explicitly allow-listed UTF-8 source files."""

    errors: list[str] = []
    if type(source_files) is not tuple:
        errors.append("source_files: must be a tuple of paths")
        source_files = ()
    duplicates = {path for path in source_files if source_files.count(path) > 1}
    for path in duplicates:
        errors.append(_path_error(str(path), "duplicate path"))

    valid_paths: list[str] = []
    for path in source_files:
        path_errors = _validate_relative_path(path)
        errors.extend(path_errors)
        if not path_errors:
            valid_paths.append(path)

    snapshots: list[SourceFileSnapshot] = []
    if not errors:
        for relative_path in sorted(valid_paths):
            candidate = root / Path(*relative_path.split("/"))
            try:
                if _has_symlink_component(root, relative_path):
                    raise OSError("symlink component is not allowed")
                if not candidate.is_file():
                    raise OSError("file does not exist or is not a regular file")
                raw = candidate.read_bytes()
                source = raw.decode("utf-8", errors="strict")
                if any(pattern.search(source) for pattern in _OBVIOUS_SECRET_PATTERNS):
                    raise OSError("source appears to contain an obvious secret")
            except UnicodeDecodeError:
                errors.append(_path_error(relative_path, "must be valid UTF-8"))
            except OSError as error:
                errors.append(_path_error(relative_path, str(error)))
            else:
                snapshots.append(SourceFileSnapshot(relative_path, source, len(raw)))

    if errors:
        raise SourceValidationError(tuple(sorted(errors)))

    frame = bytearray(pack(">Q", len(snapshots)))
    for item in snapshots:
        path_bytes = item.relative_path.encode("utf-8")
        content = item.raw_bytes
        frame.extend(pack(">Q", len(path_bytes)))
        frame.extend(path_bytes)
        frame.extend(pack(">Q", len(content)))
        frame.extend(content)
    return SourceArchive(tuple(snapshots), sha256(frame).hexdigest())


def fingerprint_source(root: Path, source_files: tuple[str, ...]) -> str:
    """Return the lowercase framed SHA-256 without exposing mutable file state."""

    return archive_source(root, source_files).fingerprint
