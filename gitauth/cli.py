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
    map_all: bool = typer.Option(
        False,
        "--map-all",
        help="Alias for --all: show all commits (same as --all)"
    ),
    choose_old: bool = typer.Option(
        False,
        "--choose-old",
        help="Interactively select author(s) to filter by"
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

        # support --map-all as an alias for --all
        if map_all:
            all_commits = True

        # If user wants to choose an existing author interactively
        if choose_old:
            authors = detect_authors(repo)
            if not authors:
                console.print("[yellow]No authors found to choose from[/yellow]")
                raise typer.Exit(0)

            sorted_authors = sorted(authors, key=lambda a: a.name.lower())
            console.print("\n[bold]Select author(s) to filter by:[/bold]\n")
            for i, a in enumerate(sorted_authors, start=1):
                console.print(f"  {i}. {a.name} <{a.email}>")

            choice = typer.prompt("\nEnter author number (or comma-separated numbers)", default="1")
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                chosen_authors = [sorted_authors[idx] for idx in indices]
                
                # For dry-run, show commits from all selected authors
                commits = []
                for author in chosen_authors:
                    author_commits = find_commits_by_author(
                        repo, 
                        email=author.email, 
                        name=author.name,
                        limit=limit
                    )
                    commits.extend(author_commits)
                
                # Remove duplicates and limit
                seen = set()
                unique_commits = []
                for c in commits:
                    if c['hash'] not in seen:
                        seen.add(c['hash'])
                        unique_commits.append(c)
                
                commits = unique_commits[:limit]
                
                if not commits:
                    console.print("[yellow]No matching commits found[/yellow]")
                    raise typer.Exit(0)

                total_count = len(commits)
                showing = min(total_count, limit)

                console.print(
                    f"\n[bold green]Found {total_count} commit(s) from selected author(s). Showing first {showing}:[/bold green]\n"
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
                
                raise typer.Exit(0)
                
            except (ValueError, IndexError):
                console.print("[bold red]Invalid selection[/bold red]")
                raise typer.Exit(1)

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
    new_name: Optional[str] = typer.Option(
        None,
        "--new-name",
        "-N",
        help="New author name (optional with --choose-old)"
    ),
    new_email: Optional[str] = typer.Option(
        None,
        "--new-email",
        "-E",
        help="New author email (optional with --choose-old)"
    ),
    all_commits: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Rewrite all commits regardless of author"
    ),
    map_all: bool = typer.Option(
        False,
        "--map-all",
        help="Alias for --all: map all authors to the new identity"
    ),
    no_backup: bool = typer.Option(
        False,
        "--no-backup",
        help="Skip automatic backup"
    ),
    choose_old: bool = typer.Option(
        False,
        "--choose-old",
        help="Interactively select author(s) to rewrite and choose new identity"
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

        # support --map-all alias
        if map_all:
            all_commits = True

        # Interactive selection from existing authors
        if choose_old:
            authors = detect_authors(repo)
            if not authors:
                console.print("[yellow]No authors found to choose from[/yellow]")
                raise typer.Exit(0)

            sorted_authors = sorted(authors, key=lambda a: a.name.lower())
            
            # Step 1: Select old author(s) to rewrite
            console.print("\n[bold cyan]Step 1: Select author(s) to rewrite[/bold cyan]\n")
            for i, a in enumerate(sorted_authors, start=1):
                console.print(f"  {i}. {a.name} <{a.email}>")

            old_choice = typer.prompt("\nEnter author number(s) (comma-separated for multiple)", default="1")
            try:
                old_indices = [int(x.strip()) - 1 for x in old_choice.split(",")]
                chosen_old_authors = [sorted_authors[idx] for idx in old_indices]
            except (ValueError, IndexError):
                console.print("[bold red]Invalid selection[/bold red]")
                raise typer.Exit(1)

            console.print(f"\n[bold green]Selected {len(chosen_old_authors)} author(s) to rewrite:[/bold green]")
            for a in chosen_old_authors:
                console.print(f"  - {a.name} <{a.email}>")
            
            # Step 2: Choose new identity (from list or enter new)
            console.print("\n[bold cyan]Step 2: Choose new identity[/bold cyan]")
            console.print("\nOptions:")
            console.print("  1. Select from existing authors")
            console.print("  2. Enter new author details")
            
            new_choice = typer.prompt("\nEnter choice (1 or 2)", default="2")
            
            if new_choice == "1":
                # Select from existing authors
                console.print("\n[bold]Select new author:[/bold]\n")
                for i, a in enumerate(sorted_authors, start=1):
                    console.print(f"  {i}. {a.name} <{a.email}>")
                
                new_author_choice = typer.prompt("\nEnter author number", default="1")
                try:
                    new_idx = int(new_author_choice.strip()) - 1
                    chosen_new = sorted_authors[new_idx]
                    new_name = chosen_new.name
                    new_email = chosen_new.email
                except (ValueError, IndexError):
                    console.print("[bold red]Invalid selection[/bold red]")
                    raise typer.Exit(1)
            else:
                # Use provided new_name and new_email from command options
                # If not provided via CLI args, they'll be required and typer will prompt
                if not new_name or not new_email:
                    console.print("\n[bold yellow]Enter new author details:[/bold yellow]")
                    if not new_name:
                        new_name = typer.prompt("New author name")
                    if not new_email:
                        new_email = typer.prompt("New author email")
            
            console.print(f"\n[bold green]New identity:[/bold green] {new_name} <{new_email}>")
            
            # For rewrite logic: we need to handle multiple old authors
            # We'll create a mailmap or run multiple rewrites
            # For now, let's rewrite each old author to the new one
            # This will be handled by passing the info to rewrite_history
            
            # Store the selections for processing
            selected_old_authors = chosen_old_authors

        # Validate inputs
        if not choose_old and not all_commits and not old_email and not old_name:
            console.print(
                "[bold red]Error:[/bold red] Must specify --old-email, --old-name, --all, or --choose-old"
            )
            raise typer.Exit(1)
        
        # Validate new identity (required unless using --choose-old)
        if not choose_old and (not new_name or not new_email):
            console.print(
                "[bold red]Error:[/bold red] --new-name and --new-email are required (unless using --choose-old)"
            )
            raise typer.Exit(1)

        # Show what will be changed
        console.print("\n[bold]Rewrite Configuration:[/bold]")
        if all_commits:
            console.print("  [yellow]Mode:[/yellow] Rewrite ALL commits")
        elif choose_old and 'selected_old_authors' in locals():
            console.print(f"  [yellow]Mode:[/yellow] Rewrite {len(selected_old_authors)} selected author(s)")
            for a in selected_old_authors:
                console.print(f"    - {a.name} <{a.email}>")
        else:
            if old_email:
                console.print(f"  [yellow]Old Email:[/yellow] {old_email}")
            if old_name:
                console.print(f"  [yellow]Old Name:[/yellow] {old_name}")

        console.print(f"  [green]New Name:[/green] {new_name}")
        console.print(f"  [green]New Email:[/green] {new_email}")

        # Count affected commits
        if choose_old and 'selected_old_authors' in locals():
            total_count = 0
            for a in selected_old_authors:
                count = repo.count_commits_by_author(email=a.email, name=a.name)
                total_count += count
            console.print(f"\n[bold yellow]This will affect approximately {total_count} commit(s)[/bold yellow]")
        elif not all_commits:
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

        if choose_old and 'selected_old_authors' in locals():
            # Rewrite multiple authors sequentially
            for i, old_author in enumerate(selected_old_authors, start=1):
                console.print(f"\n[dim]Processing author {i}/{len(selected_old_authors)}: {old_author.name} <{old_author.email}>[/dim]")
                rewrite_history(
                    repo,
                    old_email=old_author.email,
                    old_name=old_author.name,
                    new_name=new_name,
                    new_email=new_email,
                    rewrite_all=False
                )
        else:
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
