# sigmark

GPG signing for static site markdown content.

Sign Hugo/static-site markdown files with GPG, embedding ASCII-armored signatures directly in YAML front matter. Verify authenticity, strip signatures, or check signing status across your content directory.

## Install

```bash
pip install sigmark
```

Requires GPG (`gpg`) to be installed and available on your `PATH`.

## Usage

```bash
# Sign all markdown files in a directory
sigmark sign --key you@example.com content/

# Sign a single file
sigmark sign --key you@example.com content/post/hello/index.md

# Verify signatures
sigmark verify content/

# Check signing status
sigmark status content/

# Remove signatures
sigmark strip content/
```

## How It Works

Sigmark signs only the **body** of each markdown file (everything below the closing `---` front-matter delimiter). The GPG signature is stored as a `signature` field in the YAML front matter:

```yaml
---
title: Hello World
date: 2026-01-01
signature: |
  -----BEGIN PGP SIGNATURE-----
  iQEzBAABCAAdFiEE...
  -----END PGP SIGNATURE-----
---
Your post body here.
```

This means front-matter changes (tags, categories, draft status) don't invalidate the signature, while any change to the actual content does.

## Commands

| Command | Description |
|---------|-------------|
| `sign --key <id> PATHS...` | Sign markdown files with GPG |
| `verify PATHS...` | Verify GPG signatures (exit 1 on failure) |
| `strip PATHS...` | Remove signature fields from front matter |
| `status PATHS...` | Report unsigned / valid / invalid per file |

All commands accept files and/or directories. Directories are walked recursively for `.md` files with YAML front matter. Global flags: `--verbose`, `--dry-run`.

## License

MIT
