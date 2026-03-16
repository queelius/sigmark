"""Markdown front matter parsing and rendering."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml


class _StringDateLoader(yaml.SafeLoader):
    """YAML loader that keeps date-like scalars as strings."""


# Remove the implicit date resolver so dates stay as plain strings.
_StringDateLoader.yaml_implicit_resolvers = {
    k: [(tag, regexp) for tag, regexp in v if tag != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.copy().items()
}


def parse(text: str) -> tuple[dict, str]:
    """Split markdown into (front_matter_dict, body_str).

    Front matter is delimited by opening and closing ``---`` lines.
    Body is everything after the closing delimiter.
    Raises ValueError if no front matter is found.
    """
    match = re.match(r"\A---\n(.*?)^---\n(.*)\Z", text, re.DOTALL | re.MULTILINE)
    if not match:
        raise ValueError("No YAML front matter found")
    fm_raw, body = match.group(1), match.group(2)
    front_matter = yaml.load(fm_raw, Loader=_StringDateLoader) or {}
    return front_matter, body


def render(front_matter: dict, body: str) -> str:
    """Reassemble front matter dict and body into a markdown string."""
    if front_matter:
        fm_str = yaml.dump(front_matter, default_flow_style=False, sort_keys=False)
    else:
        fm_str = ""
    return f"---\n{fm_str}---\n{body}"


def normalize_body(body: str) -> str:
    """Normalize body text for reproducible signing.

    Strips trailing whitespace per line, ensures single trailing newline.
    """
    if not body or body.isspace():
        return ""
    lines = body.rstrip("\n").split("\n")
    lines = [line.rstrip() for line in lines]
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
            parse(path.read_text())
            result.append(path)
        elif path.is_dir():
            for md_file in sorted(path.rglob("*.md")):
                try:
                    parse(md_file.read_text())
                    result.append(md_file)
                except ValueError:
                    continue
    return result
