# sigmark

GPG signing for static site markdown content. Your key signs your writing, so readers can verify the post they are looking at is the one you actually wrote.

Works with Hugo, Jekyll, Zola, Eleventy, and any static site generator that uses YAML front matter.

## Why

Static hosting (GitHub Pages, Netlify, S3) is cheap but gives readers zero cryptographic attribution. HTTPS verifies the *host*, not the *author*. Git commit signing proves the *committer* but is invisible to readers who never clone the repo. CDN caches can go stale, accounts get compromised, look-alike domains exist.

For writing where attribution matters (academic critiques, research posts, signed opinions, health advocacy, anything that might be targeted for attribution-spoofing), sigmark gives you a way to make a verifiable claim:

> This post was written by me, on this date, and has not been altered since.

A reader can verify that claim against your published public key, without trusting GitHub, the CDN, or the DNS. Stale caches and tampered forks become detectable.

For a blog about cat photos this is overkill. For a blog where your name and your arguments are the product, it closes a real gap.

## How it works

Sigmark signs the **body** of each markdown file (everything below the closing `---` of the front matter) with GPG, then embeds the ASCII-armored detached signature in the front matter itself:

```yaml
---
title: "My Post"
date: 2026-02-17
tags: ["cryptography"]
gpg_sig: |
  -----BEGIN PGP SIGNATURE-----
  iQIzBAABCAAdFiEE...
  -----END PGP SIGNATURE-----
gpg_sig_date: "2026-02-17T14:30:00Z"
gpg_body_hash: "sha256:a1b2c3d4..."
---
The actual body text...
```

The signature travels with the file forever. No sidecar files, no external manifest, no server component. A copy-paste preserves the signature; a Hugo page bundle ships it alongside the content.

## Install

```bash
pip install sigmark
```

Requires `gpg` on your PATH and a secret key in your keyring.

## Quick start

```bash
# Sign one post (uses your default GPG key)
sigmark sign content/post/my-post/index.md

# Check what you have
sigmark status content/

# Verify a signed post
sigmark verify content/post/my-post/index.md
```

## Bulk-signing a Hugo site

Run from your Hugo site root. Sigmark walks directories recursively, skips files that are already signed with the current body hash, and leaves files without front matter untouched.

```bash
# Preview what would be signed (no changes made)
sigmark -n sign content/

# Sign every post (fast on re-runs: hash-based skip)
sigmark sign content/

# Status report across the whole site
sigmark status content/

# Machine-readable for CI
sigmark status --json content/ | jq '.total, .signed, .unsigned, .stale, .error'
```

### Deploy workflow

A typical flow: sign before every deploy, fail the deploy if any signature is invalid.

```bash
sigmark sign content/     # sign new/changed posts (cheap on re-runs)
sigmark verify content/   # exits 1 if anything is unsigned or tampered
hugo && deploy_step
```

Because signing is idempotent and hash-skipped, you can safely put `sigmark sign content/` in a pre-commit hook or a CI step without paying GPG's subprocess cost on unchanged files.

### Re-signing after key rotation or major edits

```bash
sigmark sign --force content/   # re-sign everything, ignoring cached hash
```

## Publishing your pubkey

A signature is only as trustworthy as the path a reader uses to get your public key. Sigmark ships a `wkd` subcommand that generates a Web Key Directory so readers can discover your key directly from your domain:

```bash
# Generate WKD files (auto-detects your email from your secret key)
sigmark wkd path/to/hugo/static/

# The command writes:
#   path/to/hugo/static/.well-known/openpgpkey/policy
#   path/to/hugo/static/.well-known/openpgpkey/hu/<zbase32-hash>
```

Deploy that directory to your site root; the pubkey is now reachable at `https://<your-domain>/.well-known/openpgpkey/hu/<hash>`. Any GPG client can find it:

```bash
gpg --auto-key-locate wkd --locate-keys you@your-domain.com
# Imports your key directly from your own site, over HTTPS, no keyserver needed.
```

This closes the trust loop: readers arrive at your site via DNS+TLS (trusting the domain), and the key used to verify your content is served from that same trusted origin. No third-party keyserver, no Keybase-style identity broker, no out-of-band key exchange.

Most static hosts need one small config tweak: serve the pubkey file with `Content-Type: application/octet-stream`. For Netlify, add to `netlify.toml`:

```toml
[[headers]]
  for = "/.well-known/openpgpkey/hu/*"
  [headers.values]
    Content-Type = "application/octet-stream"
```

## Commands

| Command | Description |
|---------|-------------|
| `sign [PATHS...]` | Sign markdown files with your default GPG key, or `--key ID` for a specific key. Skips already-signed files unless `--force`. |
| `verify [PATHS...]` | Cryptographic verification. Exits 1 on any failure, unsigned, or missing file. |
| `status [PATHS...]` | Signing coverage report. Classifies each file as signed / unsigned / stale / invalid / error. Use `--json` for machine-readable output. |
| `strip [PATHS...]` | Remove all `gpg_*` signature fields from front matter (useful before re-signing or publishing unsigned drafts). |
| `wkd <OUTPUT_DIR>` | Generate Web Key Directory files for publishing your pubkey. Drop `OUTPUT_DIR` into your static site's web root to make your key discoverable via `gpg --locate-keys`. |

All commands default to the current directory. Directories are walked recursively for `.md` files with YAML front matter.

### Global flags

- `-v, --verbose` : show GPG error details on verification failure
- `-n, --dry-run` : preview without modifying files (applies to `sign` and `strip`)

## Design notes

Three decisions that may surprise you:

### Body-only signing

Only the body below the closing `---` is signed. Front matter is mutable on purpose: Hugo adds generated metadata, you retag posts, themes require new fields. Excluding front matter from the signed content means you can change `tags:` without breaking the signature. Only semantic content changes invalidate it.

### SHA-256 hash alongside the signature

A `gpg_body_hash` is stored at sign time and used as a fast pre-check. On a 500-post site, `sigmark status` classifies staleness in milliseconds without spawning any GPG processes. It also lets `status` distinguish "stale" (the body was edited) from "invalid" (GPG signature fails even on the stored body), which is a much more useful diagnosis.

The hash is not a security boundary (an attacker can modify both body and hash). It is a caching and UX optimization. The GPG signature remains the sole authority on authenticity.

### Body normalization before signing

Before signing or hashing, the body is normalized: trailing whitespace stripped per line, exactly one trailing newline. Without this, a file round-tripped through a different editor (CRLF vs LF, auto-trim-whitespace on save) would fail to verify even though its semantic content is identical. Normalization makes the signature depend on what you wrote, not on how your editor saved it.

## Hugo integration

A ready-made verification badge is included. Copy `hugo/layouts/partials/gpg-badge.html` into your site's `layouts/partials/`, then add this to your single-post template (e.g. `layouts/_default/single.html`):

```html
{{ partial "gpg-badge.html" . }}
```

The badge shows a green "GPG Signed" indicator with the signing date, and an expandable block revealing the full ASCII-armored signature for manual verification.

## Manual verification

A reader with `gpg` can verify a signed post without any sigmark-specific tooling:

1. Save the body (everything after the second `---`) to `body.txt`. Normalize: strip trailing whitespace per line, ensure single trailing newline.
2. Copy the `gpg_sig` value from the front matter to `sig.asc`.
3. Import the author's public key (e.g. `gpg --recv-keys <fingerprint>`).
4. Run `gpg --verify sig.asc body.txt`.

If the output says "Good signature from ...", the post is authentic.

## Exit codes

- `sign` : exits 1 only if every input file errored and nothing was signed.
- `verify` : exits 1 on any unsigned, invalid, or errored file, or if no markdown files were found. A stale body (hash mismatch) fails GPG verification and appears as "Invalid".
- `strip` : always exits 0 (errors are reported per-file but do not fail the batch).
- `status` : exits 0 (status is a report; use `verify` in CI gates).

## License

MIT
