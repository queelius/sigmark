"""Markdown front matter parsing and rendering."""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 4096  # avoid wrapping long scalars (PGP signatures); see KNOWN_ISSUES.md
_yaml.indent(mapping=2, sequence=4, offset=2)

# Strip the implicit timestamp resolver so date scalars stay as `str`, not
# `datetime.date`. ruamel.yaml stores resolvers in two private structures that
# both feed the parser: `_version_implicit_resolver` (per-spec-version) drives
# scalar typing, and `versioned_resolver` (first-char dispatch) is consulted
# at parse time. Both must be cleaned or dates re-acquire the timestamp tag.
_TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"


def _strip_timestamp(table: dict) -> None:
    for key in list(table):
        table[key] = [(t, rx) for t, rx in table[key] if t != _TIMESTAMP_TAG]


for _resolvers in _yaml.resolver._version_implicit_resolver.values():
    _strip_timestamp(_resolvers)
_strip_timestamp(_yaml.resolver.versioned_resolver)


def parse(text: str) -> tuple[dict, str]:
    """Split markdown into (front_matter_dict, body_str).

    Front matter is delimited by opening and closing ``---`` lines.
    Body is everything after the closing delimiter.
    Raises ValueError if no front matter is found.
    """
    # Normalize CRLF to LF for cross-platform compatibility
    text = text.replace("\r\n", "\n")
    match = re.match(r"\A---\n(.*?)^---\n(.*)\Z", text, re.DOTALL | re.MULTILINE)
    if not match:
        raise ValueError("No YAML front matter found")
    fm_raw, body = match.group(1), match.group(2)
    front_matter = _yaml.load(fm_raw) or {}
    return front_matter, body


def render(front_matter: dict, body: str) -> str:
    """Reassemble front matter dict and body into a markdown string."""
    if front_matter:
        buf = io.StringIO()
        _yaml.dump(front_matter, buf)
        fm_str = buf.getvalue()
    else:
        fm_str = ""
    return f"---\n{fm_str}---\n{body}"


def normalize_body(body: str) -> str:
    """Normalize body text for reproducible signing.

    Strips trailing whitespace per line, ensures single trailing newline.
    """
    if not body or body.isspace():
        return ""
    lines = [line.rstrip() for line in body.rstrip("\n").split("\n")]
    return "\n".join(lines) + "\n"


def compute_body_hash(body: str) -> str:
    """Compute SHA-256 hash of normalized body text.

    Returns a prefixed hash string like 'sha256:abc123...'.
    """
    normalized = normalize_body(body)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_files(paths: list[Path]) -> list[Path]:
    """Expand files and directories into a flat list of .md file paths.

    Explicit file arguments are returned as-is (callers validate).
    Directories are walked recursively; only files with an opening
    ``---\\n`` (likely YAML front matter) are included, others skipped.
    Raises FileNotFoundError for missing paths.
    """
    result: list[Path] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            for md_file in sorted(path.rglob("*.md")):
                # Cheap header sniff; full parse happens in callers' try/except.
                try:
                    with md_file.open("rb") as f:
                        if f.readline().rstrip(b"\r\n") == b"---":
                            result.append(md_file)
                except OSError:
                    continue
    return result
