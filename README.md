# sigmark

GPG signing for static site markdown content. Works with Hugo, Jekyll, Zola, Eleventy, and any static site generator that uses YAML front matter.

## Install

```bash
pip install sigmark
```

Requires `gpg` on your PATH.

## Usage

```bash
# Sign all markdown in current directory (uses default GPG key)
sigmark sign

# Sign a specific directory
sigmark sign content/

# Use a specific GPG key
sigmark sign --key lex@metafunctor.com content/

# Re-sign everything (including already-signed)
sigmark sign --force

# Check signing status (instant, uses body hash)
sigmark status content/
sigmark status --json content/

# Verify signatures cryptographically
sigmark verify content/

# Remove all signatures
sigmark strip content/

# Dry run (preview without changes)
sigmark -n sign content/
```

## What it does

Signs the **body** of markdown files (everything below the `---` front matter) with GPG and stores the signature in front matter:

```yaml
title: "My Post"
date: 2026-02-17
tags: ["cryptography"]
gpg_sig: |
  -----BEGIN PGP SIGNATURE-----
  iQIzBAABCAAdFiEE...
  -----END PGP SIGNATURE-----
gpg_sig_date: "2026-02-17T14:30:00Z"
gpg_body_hash: "sha256:a1b2c3d4..."
```

Only the body is signed. You can freely change tags, categories, and other metadata without invalidating the signature.

### Staleness detection

A SHA-256 body hash is stored at sign time. `sigmark sign` (without `--force`) skips files whose body hasn't changed, making it cheap to run on every deploy. `sigmark status` uses the hash for instant staleness detection without invoking GPG.

## Commands

| Command | Description |
|---------|-------------|
| `sign [PATHS...]` | Sign markdown files (default key, or `--key ID`) |
| `verify [PATHS...]` | Cryptographic verification (exit 1 on failure) |
| `status [PATHS...]` | Signing coverage report (`--json` for machine output) |
| `strip [PATHS...]` | Remove all signature fields from front matter |

All commands default to current directory. Directories are walked recursively for `.md` files with YAML front matter. Global flags: `-v` (verbose), `-n` (dry-run).

## Hugo integration

Copy `hugo/layouts/partials/gpg-badge.html` into your site's `layouts/partials/`, then:

```html
{{ partial "gpg-badge.html" . }}
```

Renders a "GPG Signed" badge with expandable signature details.

## Manual verification

```bash
# Extract body (everything after second ---) to body.txt
# Copy gpg_sig value to sig.asc
gpg --verify sig.asc body.txt
```

## License

MIT
