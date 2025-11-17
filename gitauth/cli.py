"""Command-line interface for GitAuth."""

import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .core.backup import create_backup
from .core.detect import detect_authors, find_commits_by_author
from .core.git_utils import GitError, GitRepo
from .core.rewrite import rewrite_history, RewriteError

# Create Typer app
app = typer.Typer(
    name="gitauth",
    help="A CLI tool to rewrite Git commit authors and committers",
    add_completion=False
)

# Rich console for pretty output
console = Console()

# Configure logging
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s'
    )


@app.command()
def check(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to Git repository (default: current directory)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output"
    )
):
    """
    List all unique authors in the repository.
    """
    setup_logging(verbose)

    try:
        repo = GitRepo(str(path) if path else None)

        if not repo.has_commits():
            console.print("[yellow]Repository has no commits yet[/yellow]")
            raise typer.Exit(0)

        console.print("[bold]Detecting authors...[/bold]")
        authors = detect_authors(repo)

        if not authors:
            console.print("[yellow]No authors found[/yellow]")
            raise typer.Exit(0)

        console.print(f"\n[bold green]Found {len(authors)} unique author(s):[/bold green]\n")

        # Create table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Name", style="green")
        table.add_column("Email", style="blue")

        for author in sorted(authors, key=lambda a: a.name.lower()):
            table.add_row(author.name, author.email)

        console.print(table)

    except GitError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def dry_run(
    old_email: Optional[str] = typer.Option(
        None,
        "--old-email",
        "-e",
        help="Old author email to search for"
    ),
    old_name: Optional[str] = typer.Option(
        None,
        "--old-name",
        "-n",
        help="Old author name to search for"
    ),
    all_commits: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all commits"
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-l",
        help="Maximum number of commits to show"
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to Git repository (default: current directory)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output"
    )
):
    """
    Preview which commits would be changed (dry run).
    """
    setup_logging(verbose)

    try:
        repo = GitRepo(str(path) if path else None)

        if not repo.has_commits():
            console.print("[yellow]Repository has no commits yet[/yellow]")
            raise typer.Exit(0)

        console.print("[bold]Finding commits...[/bold]")

        if all_commits:
            commits = find_commits_by_author(repo, limit=limit)
        else:
            if not old_email and not old_name:
                console.print(
                    "[bold red]Error:[/bold red] Must specify --old-email, --old-name, or --all"
                )
                raise typer.Exit(1)

            commits = find_commits_by_author(
                repo,
                email=old_email,
                name=old_name,
                limit=limit
            )

        if not commits:
            console.print("[yellow]No matching commits found[/yellow]")
            raise typer.Exit(0)

        total_count = len(commits)
        showing = min(total_count, limit)

        console.print(
            f"\n[bold green]Found {total_count} commit(s). Showing first {showing}:[/bold green]\n"
        )

        # Create table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Commit", style="yellow", width=10)
        table.add_column("Author", style="green")
        table.add_column("Email", style="blue")
        table.add_column("Subject", style="white", overflow="fold")

        for commit in commits[:limit]:
            table.add_row(
                commit['hash'][:8],
                commit['author_name'],
                commit['author_email'],
                commit['subject'][:60] + "..." if len(commit['subject']) > 60 else commit['subject']
            )

        console.print(table)

        if total_count > limit:
            console.print(f"\n[dim]... and {total_count - limit} more commits[/dim]")

    except GitError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def backup(
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for backup (default: parent directory)"
    ),
    format: str = typer.Option(
        "tar.gz",
        "--format",
        "-f",
        help="Backup format: 'zip' or 'tar.gz'"
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to Git repository (default: current directory)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output"
    )
):
    """
    Create a backup of the Git repository.
    """
    setup_logging(verbose)

    try:
        repo = GitRepo(str(path) if path else None)

        if format not in ["zip", "tar.gz"]:
            console.print("[bold red]Error:[/bold red] Format must be 'zip' or 'tar.gz'")
            raise typer.Exit(1)

        console.print("[bold]Creating backup...[/bold]")

        backup_path = create_backup(repo, output_dir=output_dir, format=format)  # type: ignore

        console.print(f"\n[bold green]✓ Backup created successfully:[/bold green]")
        console.print(f"  {backup_path}")

    except GitError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def rewrite(
    old_email: Optional[str] = typer.Option(
        None,
        "--old-email",
        "-e",
        help="Old author email to replace"
    ),
    old_name: Optional[str] = typer.Option(
        None,
        "--old-name",
        "-n",
        help="Old author name to replace"
    ),
    new_name: str = typer.Option(
        ...,
        "--new-name",
        "-N",
        help="New author name"
    ),
    new_email: str = typer.Option(
        ...,
        "--new-email",
        "-E",
        help="New author email"
    ),
    all_commits: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Rewrite all commits regardless of author"
    ),
    no_backup: bool = typer.Option(
        False,
        "--no-backup",
        help="Skip automatic backup"
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to Git repository (default: current directory)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output"
    )
):
    """
    Rewrite Git commit authors and committers.
    """
    setup_logging(verbose)

    try:
        repo = GitRepo(str(path) if path else None)

        # Validate repository state
        if not repo.has_commits():
            console.print("[yellow]Repository has no commits yet[/yellow]")
            raise typer.Exit(0)

        if not repo.is_clean():
            console.print(
                "[bold red]Error:[/bold red] Working directory is not clean. "
                "Please commit or stash your changes first."
            )
            raise typer.Exit(1)

        # Validate inputs
        if not all_commits and not old_email and not old_name:
            console.print(
                "[bold red]Error:[/bold red] Must specify --old-email, --old-name, or --all"
            )
            raise typer.Exit(1)

        # Show what will be changed
        console.print("\n[bold]Rewrite Configuration:[/bold]")
        if all_commits:
            console.print("  [yellow]Mode:[/yellow] Rewrite ALL commits")
        else:
            if old_email:
                console.print(f"  [yellow]Old Email:[/yellow] {old_email}")
            if old_name:
                console.print(f"  [yellow]Old Name:[/yellow] {old_name}")

        console.print(f"  [green]New Name:[/green] {new_name}")
        console.print(f"  [green]New Email:[/green] {new_email}")

        # Count affected commits
        if not all_commits:
            count = repo.count_commits_by_author(email=old_email, name=old_name)
            console.print(f"\n[bold yellow]This will affect approximately {count} commit(s)[/bold yellow]")

        # Warning
        console.print(
            "\n[bold red]⚠ Warning:[/bold red] This will rewrite Git history! "
            "This is a destructive operation."
        )

        # Create backup unless disabled
        if not no_backup:
            console.print("\n[bold]Creating backup before rewriting...[/bold]")
            backup_path = create_backup(repo, format="tar.gz")
            console.print(f"[dim]Backup saved to: {backup_path}[/dim]")

        # Confirm
        confirm = typer.confirm("\nDo you want to proceed?", default=False)
        if not confirm:
            console.print("[yellow]Aborted[/yellow]")
            raise typer.Exit(0)

        # Perform rewrite
        console.print("\n[bold]Rewriting history...[/bold]")

        rewrite_history(
            repo,
            old_email=old_email,
            old_name=old_name,
            new_name=new_name,
            new_email=new_email,
            rewrite_all=all_commits
        )

        console.print("\n[bold green]✓ History rewritten successfully![/bold green]")
        console.print(
            "\n[bold]Next steps:[/bold]\n"
            "  1. Verify the changes: [cyan]git log[/cyan]\n"
            "  2. Force push to remote: [cyan]gitauth push[/cyan] or [cyan]git push --force-with-lease[/cyan]\n"
            "  3. Notify collaborators to re-clone the repository"
        )

    except GitError as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)
    except RewriteError as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


@app.command()
def push(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force push without confirmation"
    ),
    remote: str = typer.Option(
        "origin",
        "--remote",
        "-r",
        help="Remote name"
    ),
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to Git repository (default: current directory)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output"
    )
):
    """
    Push rewritten history to remote repository.
    """
    setup_logging(verbose)

    try:
        repo = GitRepo(str(path) if path else None)

        # Check if remote exists
        if not repo.has_remote(remote):
            console.print(f"[bold red]Error:[/bold red] Remote '{remote}' not found")
            raise typer.Exit(1)

        remote_url = repo.get_remote_url(remote)
        current_branch = repo.get_current_branch()

        console.print("\n[bold]Push Configuration:[/bold]")
        console.print(f"  [yellow]Remote:[/yellow] {remote}")
        console.print(f"  [yellow]URL:[/yellow] {remote_url}")
        console.print(f"  [yellow]Branch:[/yellow] {current_branch}")

        # Warning
        console.print(
            "\n[bold red]⚠ Warning:[/bold red] This will force push rewritten history! "
            "All collaborators must re-clone or reset their local repositories."
        )

        # Confirm unless --force
        if not force:
            confirm = typer.confirm("\nDo you want to proceed?", default=False)
            if not confirm:
                console.print("[yellow]Aborted[/yellow]")
                raise typer.Exit(0)

        # Push with force-with-lease (safer than --force)
        console.print("\n[bold]Pushing to remote...[/bold]")

        result = repo._run_command(
            ["git", "push", "--force-with-lease", remote, current_branch],
            check=False
        )

        if result.returncode != 0:
            console.print(f"\n[bold red]Push failed:[/bold red]")
            console.print(result.stderr)
            raise typer.Exit(1)

        console.print("\n[bold green]✓ Successfully pushed to remote![/bold green]")
        console.print(
            "\n[bold]Important:[/bold] Notify all collaborators to:\n"
            "  1. Save any local work\n"
            "  2. Delete their local repository\n"
            "  3. Clone fresh from remote"
        )

    except GitError as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.callback()
def main():
    """
    GitAuth - Rewrite Git commit authors and committers safely.
    """
    pass


def cli():
    """Entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]Fatal error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
