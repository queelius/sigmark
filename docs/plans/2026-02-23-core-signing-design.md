# Core Signing Functionality Design

## Summary

Implement GPG signing of markdown file bodies, with signatures embedded as a `signature` field in YAML front matter. Four CLI subcommands: sign, verify, strip, status.

## Decisions

- **Signature storage:** YAML front matter `signature:` field (ASCII-armored detached signature)
- **What gets signed:** Body only (everything below closing `---`). Front matter is excluded.
- **Key selection:** Explicit `--key <email-or-id>` flag required for signing
- **Input scope:** Accept files and/or directories. Directories walked recursively for `.md` files with front matter.

## Module Structure

```
src/sigmark/
  __init__.py       # existing — package metadata
  cli.py            # existing — add sign/verify/strip/status subcommands
  markdown.py       # parse/reassemble markdown with YAML front matter
  gpg.py            # GPG sign/verify via subprocess
```

## markdown.py

- `parse(text: str) -> tuple[dict, str]` — split markdown into (front_matter_dict, body_str)
- `render(front_matter: dict, body: str) -> str` — reassemble into complete markdown file
- `resolve_paths(paths: list[Path]) -> list[Path]` — expand files/directories into list of `.md` files with front matter

## gpg.py

- `sign(body: str, key: str, gpg_home: Path | None = None) -> str` — produce ASCII-armored detached signature via `gpg --armor --detach-sign --local-user <key>`
- `verify(body: str, signature: str, gpg_home: Path | None = None) -> VerifyResult` — verify detached signature against body
- `VerifyResult` dataclass: `valid: bool`, `key_id: str | None`, `error: str | None`

## CLI Subcommands

All accept one or more `PATHS` (files or directories).

| Command | Behavior |
|---------|----------|
| `sigmark sign --key <id> PATHS...` | Sign body, write `signature` field into front matter |
| `sigmark verify PATHS...` | Verify signature against body, report pass/fail |
| `sigmark strip PATHS...` | Remove `signature` field from front matter |
| `sigmark status PATHS...` | Report each file as: signed-valid, signed-invalid, unsigned |

Global flags `--verbose` and `--dry-run` already exist on the CLI group.

## Data Flow

### Signing
```
read file -> parse(text) -> (front_matter, body)
                                     |
                         gpg.sign(body, key) -> signature_str
                                     |
                     front_matter["signature"] = signature_str
                                     |
                     render(front_matter, body) -> write file
```

### Verification
```
read file -> parse(text) -> (front_matter, body)
                                     |
               signature = front_matter.get("signature")
                                     |
                 gpg.verify(body, signature) -> VerifyResult
```
