"""sigmark CLI entry point."""
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from sigmark import __version__, gpg, markdown

console = Console()


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
@click.option("--key", required=True, help="GPG key ID or email for signing")
@click.option(
    "--gpg-home",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    hidden=True,
    help="Custom GPG home directory (for testing)",
)
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def sign(ctx: click.Context, key: str, gpg_home: Path | None, paths: tuple[Path, ...]) -> None:
    """Sign markdown files with GPG."""
    dry_run = ctx.obj["dry_run"]
    files = markdown.resolve_paths(list(paths))
    for md_file in files:
        fm, body = markdown.parse(md_file.read_text())
        sig = gpg.sign(body, key=key, gpg_home=gpg_home)
        fm["signature"] = sig
        if dry_run:
            console.print(f"[yellow]Would sign:[/yellow] {md_file}")
        else:
            md_file.write_text(markdown.render(fm, body))
            console.print(f"[green]Signed:[/green] {md_file}")


@main.command()
@click.option(
    "--gpg-home",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    hidden=True,
)
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def verify(ctx: click.Context, gpg_home: Path | None, paths: tuple[Path, ...]) -> None:
    """Verify GPG signatures on markdown files."""
    verbose = ctx.obj["verbose"]
    files = markdown.resolve_paths(list(paths))
    all_valid = True
    for md_file in files:
        fm, body = markdown.parse(md_file.read_text())
        sig = fm.get("signature")
        if not sig:
            console.print(f"[red]Unsigned:[/red] {md_file}")
            all_valid = False
            continue
        result = gpg.verify(body, sig, gpg_home=gpg_home)
        if result.valid:
            console.print(f"[green]Valid:[/green] {md_file}")
        else:
            console.print(f"[red]Invalid:[/red] {md_file}")
            if verbose and result.error:
                console.print(f"  {result.error}")
            all_valid = False
    if not all_valid:
        raise SystemExit(1)


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def strip(ctx: click.Context, paths: tuple[Path, ...]) -> None:
    """Remove GPG signatures from markdown files."""
    dry_run = ctx.obj["dry_run"]
    files = markdown.resolve_paths(list(paths))
    for md_file in files:
        fm, body = markdown.parse(md_file.read_text())
        if "signature" not in fm:
            continue
        del fm["signature"]
        if dry_run:
            console.print(f"[yellow]Would strip:[/yellow] {md_file}")
        else:
            md_file.write_text(markdown.render(fm, body))
            console.print(f"[green]Stripped:[/green] {md_file}")


@main.command()
@click.option(
    "--gpg-home",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    hidden=True,
)
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def status(ctx: click.Context, gpg_home: Path | None, paths: tuple[Path, ...]) -> None:
    """Report signing status of markdown files."""
    files = markdown.resolve_paths(list(paths))
    for md_file in files:
        fm, body = markdown.parse(md_file.read_text())
        sig = fm.get("signature")
        if not sig:
            console.print(f"[dim]Unsigned:[/dim] {md_file}")
            continue
        result = gpg.verify(body, sig, gpg_home=gpg_home)
        if result.valid:
            console.print(f"[green]Valid:[/green] {md_file}")
        else:
            console.print(f"[red]Invalid:[/red] {md_file}")
