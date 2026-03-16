"""sigmark CLI entry point."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

from sigmark import __version__, gpg, markdown

console = Console(stderr=True)


@click.group()
@click.version_option(version=__version__, prog_name="sigmark")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("-n", "--dry-run", is_flag=True, help="Preview without making changes")
@click.pass_context
def main(ctx: click.Context, verbose: bool, dry_run: bool) -> None:
    """GPG signing for static site markdown content."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run


@main.command()
@click.option("--key", default=None, help="GPG key ID or email for signing (uses default key if omitted)")
@click.option(
    "--gpg-home",
    type=click.Path(exists=True, path_type=Path),  # type: ignore[type-var]
    default=None,
    hidden=True,
    help="Custom GPG home directory (for testing)",
)
@click.option("--force", is_flag=True, help="Re-sign files even if signature is current")
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))  # type: ignore[type-var]
@click.pass_context
def sign(
    ctx: click.Context,
    key: str | None,
    gpg_home: Path | None,
    force: bool,
    paths: tuple[Path, ...],
) -> None:
    """Sign markdown files with GPG."""
    dry_run = ctx.obj["dry_run"]
    if not paths:
        paths = (Path("."),)
    files = markdown.resolve_paths(list(paths))
    signed = 0
    skipped = 0
    errors = 0
    for md_file in files:
        try:
            fm, body = markdown.parse(md_file.read_text(encoding="utf-8"))
            current_hash = markdown.compute_body_hash(body)

            # Skip if already signed with current hash, unless --force
            if not force and "gpg_sig" in fm and fm.get("gpg_body_hash") == current_hash:
                skipped += 1
                continue

            if dry_run:
                console.print(f"[yellow]Would sign:[/yellow] {md_file}")
                signed += 1
                continue

            sig = gpg.sign(markdown.normalize_body(body), key=key, gpg_home=gpg_home)
            fm["gpg_sig"] = sig
            fm["gpg_sig_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            fm["gpg_body_hash"] = current_hash
            md_file.write_text(markdown.render(fm, body), encoding="utf-8")
            console.print(f"[green]Signed:[/green] {md_file}")
            signed += 1
        except Exception as exc:
            errors += 1
            console.print(f"[red]Error:[/red] {md_file}: {exc}")
    console.print(f"Signed {signed}, skipped {skipped}, errors {errors}")
    if errors and not signed:
        raise SystemExit(1)


@main.command()
@click.option(
    "--gpg-home",
    type=click.Path(exists=True, path_type=Path),  # type: ignore[type-var]
    default=None,
    hidden=True,
)
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))  # type: ignore[type-var]
@click.pass_context
def verify(ctx: click.Context, gpg_home: Path | None, paths: tuple[Path, ...]) -> None:
    """Verify GPG signatures on markdown files."""
    verbose = ctx.obj["verbose"]
    if not paths:
        paths = (Path("."),)
    files = markdown.resolve_paths(list(paths))
    if not files:
        console.print("[red]No markdown files found[/red]")
        raise SystemExit(1)
    all_valid = True
    for md_file in files:
        try:
            fm, body = markdown.parse(md_file.read_text(encoding="utf-8"))
            sig = fm.get("gpg_sig")
            if not sig:
                console.print(f"[red]Unsigned:[/red] {md_file}")
                all_valid = False
                continue
            result = gpg.verify(markdown.normalize_body(body), sig, gpg_home=gpg_home)
            if result.valid:
                console.print(f"[green]Valid:[/green] {md_file}")
            else:
                console.print(f"[red]Invalid:[/red] {md_file}")
                if verbose and result.error:
                    console.print(f"  {result.error}")
                all_valid = False
        except Exception as exc:
            console.print(f"[red]Error:[/red] {md_file}: {exc}")
            all_valid = False
    if not all_valid:
        raise SystemExit(1)


@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))  # type: ignore[type-var]
@click.pass_context
def strip(ctx: click.Context, paths: tuple[Path, ...]) -> None:
    """Remove GPG signatures from markdown files."""
    dry_run = ctx.obj["dry_run"]
    if not paths:
        paths = (Path("."),)
    files = markdown.resolve_paths(list(paths))
    sig_fields = ("gpg_sig", "gpg_sig_date", "gpg_body_hash")
    for md_file in files:
        fm, body = markdown.parse(md_file.read_text(encoding="utf-8"))
        if not any(f in fm for f in sig_fields):
            continue
        for field in sig_fields:
            fm.pop(field, None)
        if dry_run:
            console.print(f"[yellow]Would strip:[/yellow] {md_file}")
        else:
            md_file.write_text(markdown.render(fm, body), encoding="utf-8")
            console.print(f"[green]Stripped:[/green] {md_file}")


def _classify_file(md_file: Path, gpg_home: Path | None) -> str:
    """Determine the signing status of a single markdown file.

    Returns one of: "unsigned", "stale", "signed", "invalid".
    """
    fm, body = markdown.parse(md_file.read_text(encoding="utf-8"))
    sig = fm.get("gpg_sig")
    if not sig:
        return "unsigned"

    current_hash = markdown.compute_body_hash(body)
    stored_hash = fm.get("gpg_body_hash")
    if stored_hash and stored_hash != current_hash:
        return "stale"

    result = gpg.verify(markdown.normalize_body(body), sig, gpg_home=gpg_home)
    return "signed" if result.valid else "invalid"


@main.command()
@click.option(
    "--gpg-home",
    type=click.Path(exists=True, path_type=Path),  # type: ignore[type-var]
    default=None,
    hidden=True,
)
@click.option("--json", "use_json", is_flag=True, help="Output JSON report")
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))  # type: ignore[type-var]
@click.pass_context
def status(
    ctx: click.Context,
    gpg_home: Path | None,
    use_json: bool,
    paths: tuple[Path, ...],
) -> None:
    """Report signing status of markdown files."""
    if not paths:
        paths = (Path("."),)
    files = markdown.resolve_paths(list(paths))
    file_statuses: list[dict] = []
    for md_file in files:
        try:
            file_status = _classify_file(md_file, gpg_home)
        except Exception as exc:
            console.print(f"[red]Error:[/red] {md_file}: {exc}")
            file_status = "error"
        file_statuses.append({"path": str(md_file), "status": file_status})

    if use_json:
        counts = Counter(f["status"] for f in file_statuses)
        report = {
            "total": len(file_statuses),
            "signed": counts.get("signed", 0),
            "unsigned": counts.get("unsigned", 0),
            "stale": counts.get("stale", 0),
            "invalid": counts.get("invalid", 0),
            "files": file_statuses,
        }
        click.echo(json.dumps(report, indent=2))
    else:
        status_styles = {
            "signed": "[green]Valid:[/green]",
            "unsigned": "[dim]Unsigned:[/dim]",
            "stale": "[yellow]Stale:[/yellow]",
            "invalid": "[red]Invalid:[/red]",
            "error": "[red]Error:[/red]",
        }
        for entry in file_statuses:
            style = status_styles[entry["status"]]
            console.print(f"{style} {entry['path']}")
