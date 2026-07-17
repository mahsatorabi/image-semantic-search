"""Command-line interface for AI Image Indexer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from ai_image_indexer import __version__
from ai_image_indexer.cloudflare.client import CloudflareAIClient, CloudflareAIError
from ai_image_indexer.cloudflare.setup import SetupError, run_setup
from ai_image_indexer.config import Settings
from ai_image_indexer.database.repository import ImageRepository
from ai_image_indexer.indexer.pipeline import IndexingPipeline
from ai_image_indexer.scanner.system_paths import resolve_scan_roots
from ai_image_indexer.search.engine import SearchEngine

console = Console()
err_console = Console(stderr=True)


def _load_settings() -> Settings:
    try:
        return Settings.from_env()
    except ValueError as exc:
        err_console.print(f"[red]Configuration error:[/red] {exc}")
        sys.exit(1)


@click.group()
@click.version_option(__version__, prog_name="image-indexer")
def main() -> None:
    """Local-first intelligent image indexing with Cloudflare Workers AI."""


def _run_indexing(
    settings: Settings,
    folders: list[Path],
    *,
    force: bool,
) -> None:
    settings.ensure_db_dir()

    console.print("[bold]Scanning folders:[/bold]")
    for folder in folders:
        console.print(f"  • {folder}")

    with ImageRepository(settings.db_path) as repo, CloudflareAIClient(settings) as ai:
        pipeline = IndexingPipeline(settings, repo, ai)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Indexing...", total=None)

            def on_progress(filename: str, current: int, total: int) -> None:
                progress.update(
                    task_id,
                    description=f"[cyan]{filename}[/cyan]",
                    total=total,
                    completed=current,
                )

            try:
                stats = pipeline.run(folders, force=force, on_progress=on_progress)
            except CloudflareAIError as exc:
                err_console.print(f"[red]Cloudflare AI error:[/red] {exc}")
                sys.exit(1)
            except FileNotFoundError as exc:
                err_console.print(f"[red]{exc}[/red]")
                sys.exit(1)

    console.print()
    console.print(f"[green]Done![/green] Scanned: {stats.scanned}")
    console.print(f"  Indexed: [green]{stats.indexed}[/green]")
    console.print(f"  Skipped: [yellow]{stats.skipped}[/yellow] (unchanged)")
    if stats.failed:
        console.print(f"  Failed:  [red]{stats.failed}[/red]")
    if stats.removed:
        console.print(f"  Removed: [dim]{stats.removed}[/dim] (deleted from disk)")


@main.command()
@click.option(
    "--login",
    is_flag=True,
    help="Authenticate via browser using wrangler login (requires Node.js/npm).",
)
@click.option(
    "--env-path",
    type=click.Path(path_type=Path),
    default=".env",
    show_default=True,
    help="Where to write Cloudflare credentials.",
)
@click.option("--no-verify", is_flag=True, help="Skip API/model verification after setup.")
@click.option("--no-browser", is_flag=True, help="Do not open Cloudflare dashboard in browser.")
def setup(login: bool, env_path: Path, no_verify: bool, no_browser: bool) -> None:
    """Connect to Cloudflare Workers AI and save credentials locally."""
    try:
        written = run_setup(
            env_path=env_path,
            login=login,
            verify=not no_verify,
            open_browser=not no_browser,
        )
    except SetupError as exc:
        err_console.print(f"[red]Setup failed:[/red] {exc}")
        sys.exit(1)

    console.print(f"[green]Cloudflare connected.[/green] Saved credentials to [bold]{written}[/bold]")
    console.print("Next: [bold]image-indexer run[/bold]  or  [bold]image-indexer scan <folder>[/bold]")


@main.command()
@click.option("--force", is_flag=True, help="Re-index all images, even if unchanged.")
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), help="Path to .env file.")
def run(force: bool, env_file: Path | None) -> None:
    """Index all images in default system folders (Pictures, Downloads, Desktop, ...)."""
    settings = Settings.from_env(env_file) if env_file else _load_settings()
    folders = resolve_scan_roots(list(settings.scan_paths))

    if not folders:
        err_console.print(
            "[red]No image folders found.[/red] Set AI_IMAGE_INDEXER_SCAN_PATHS or use "
            "[bold]image-indexer scan <folder>[/bold]."
        )
        sys.exit(1)

    _run_indexing(settings, folders, force=force)


@main.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--force", is_flag=True, help="Re-index all images, even if unchanged.")
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), help="Path to .env file.")
def scan(folder: Path, force: bool, env_file: Path | None) -> None:
    """Scan a specific folder, analyze images with AI, and store metadata locally."""
    settings = Settings.from_env(env_file) if env_file else _load_settings()
    _run_indexing(settings, [folder.resolve()], force=force)


@main.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, show_default=True, help="Max results to show.")
@click.option(
    "--threshold",
    "-t",
    default=0.25,
    show_default=True,
    type=float,
    help="Minimum similarity score (0-1). Results below this are hidden.",
)
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON (paths only).")
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), help="Path to .env file.")
def search(query: str, limit: int, threshold: float, as_json: bool, env_file: Path | None) -> None:
    """Search indexed images by natural language query."""
    settings = Settings.from_env(env_file) if env_file else _load_settings()

    with ImageRepository(settings.db_path) as repo, CloudflareAIClient(settings) as ai:
        engine = SearchEngine(repo, ai)
        try:
            results = engine.search(query, limit=limit, min_score=threshold)
        except CloudflareAIError as exc:
            err_console.print(f"[red]Cloudflare AI error:[/red] {exc}")
            sys.exit(1)

    if not results:
        if as_json:
            click.echo("[]")
        else:
            console.print(
                "[yellow]No results found.[/yellow] Run [bold]image-indexer run[/bold] first."
            )
        return

    if as_json:
        payload = [
            {
                "filepath": result.record.filepath,
                "filename": result.record.filename,
                "score": round(result.score, 4),
                "caption": result.record.caption,
            }
            for result in results
        ]
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    table = Table(title=f'Results for: "{query}"', show_lines=True)
    table.add_column("Score", style="cyan", width=8)
    table.add_column("File", style="green")
    table.add_column("Caption", style="white", max_width=60)

    for result in results:
        table.add_row(
            f"{result.score:.3f}",
            result.record.filepath,
            result.record.caption[:120] + ("..." if len(result.record.caption) > 120 else ""),
        )

    console.print(table)


@main.command("list")
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), help="Path to .env file.")
def list_images(env_file: Path | None) -> None:
    """List all indexed images with their descriptions."""
    settings = Settings.from_env(env_file) if env_file else _load_settings()

    with ImageRepository(settings.db_path) as repo:
        records = repo.export_all()

    if not records:
        console.print("[yellow]No indexed images found.[/yellow] Run [bold]image-indexer run[/bold] first.")
        return

    table = Table(title=f"All Indexed Images ({len(records)} total)", show_lines=True)
    table.add_column("File", style="green", max_width=40)
    table.add_column("Caption", style="white", max_width=60)
    table.add_column("Tags", style="cyan", max_width=30)

    for rec in records:
        tags = ", ".join(rec["tags"]) if isinstance(rec["tags"], list) else str(rec["tags"])
        caption = rec["caption"][:120] + ("..." if len(rec["caption"]) > 120 else "")
        table.add_row(rec["filename"], caption, tags)

    console.print(table)


@main.command()
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), help="Path to .env file.")
def stats(env_file: Path | None) -> None:
    """Show indexing statistics."""
    settings = Settings.from_env(env_file) if env_file else _load_settings()

    with ImageRepository(settings.db_path) as repo:
        data = repo.stats()

    table = Table(title="AI Image Indexer Stats")
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="cyan")

    table.add_row("Total indexed images", str(data["total_images"]))
    table.add_row("With embeddings", str(data["with_embeddings"]))
    table.add_row("Database size", f"{data['db_size_bytes'] / 1024:.1f} KB")
    table.add_row("Database path", str(data["db_path"]))

    console.print(table)


@main.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="image-index-export.json",
    show_default=True,
    help="Output file path.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "csv"], case_sensitive=False),
    default="json",
    show_default=True,
)
@click.option("--env-file", type=click.Path(exists=True, path_type=Path), help="Path to .env file.")
def export(output: Path, fmt: str, env_file: Path | None) -> None:
    """Export the image index to JSON or CSV."""
    settings = Settings.from_env(env_file) if env_file else _load_settings()

    with ImageRepository(settings.db_path) as repo:
        records = repo.export_all()

    if fmt == "json":
        output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        import csv

        if not records:
            output.write_text("", encoding="utf-8")
        else:
            with output.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=records[0].keys())
                writer.writeheader()
                for rec in records:
                    rec = dict(rec)
                    tags = rec["tags"]
                    rec["tags"] = ", ".join(tags) if isinstance(tags, list) else str(tags)
                    writer.writerow(rec)

    console.print(f"[green]Exported {len(records)} records to[/green] {output.resolve()}")
