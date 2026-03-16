"""Markdown front matter parsing and rendering."""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from ruamel.yaml import YAML

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 4096  # Prevent line wrapping of long scalar values
_yaml.indent(mapping=2, sequence=4, offset=2)

# Remove the implicit timestamp resolver so dates stay as plain strings,
# preventing round-trip corruption (e.g. 2026-01-01 -> '2026-01-01').
_TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"
for _version, _resolvers in _yaml.resolver._version_implicit_resolver.items():
    for _key in list(_resolvers):
        _resolvers[_key] = [
            (tag, regexp) for tag, regexp in _resolvers[_key] if tag != _TIMESTAMP_TAG
        ]
for _key in list(_yaml.resolver.versioned_resolver):
    _yaml.resolver.versioned_resolver[_key] = [
        (tag, regexp)
        for tag, regexp in _yaml.resolver.versioned_resolver[_key]
        if tag != _TIMESTAMP_TAG
    ]


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


def resolve_paths(paths: list[Path]) -> list[Path]:
    """Expand files and directories into a list of .md files with front matter.

    Directories are walked recursively. Individual files are validated
    to have front matter. Raises FileNotFoundError for missing paths
    and ValueError for files without front matter.
    """
    result: list[Path] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        if path.is_file():
            parse(path.read_text(encoding="utf-8"))
            result.append(path)
        elif path.is_dir():
            for md_file in sorted(path.rglob("*.md")):
                try:
                    parse(md_file.read_text(encoding="utf-8"))
                    result.append(md_file)
                except ValueError:
                    continue
    return result
