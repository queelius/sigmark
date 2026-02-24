"""Markdown front matter parsing and rendering."""
from __future__ import annotations

import re

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
