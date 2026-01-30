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
from .core.arrange import calculate_schedule
import datetime
import dateutil.parser

# Create Typer app
app = typer.Typer(
    name="gitauth",
    help="A CLI tool to rewrite Git commit authors and committers",
    add_completion=False,
)

# Rich console for pretty output
console = Console()

# Configure logging
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


@app.command()
def check(
    path: Optional[Path] = typer.Argument(
        None, help="Path to Git repository (default: current directory)"
    ),
    branch: Optional[str] = typer.Option(
        None, "--branch", "-b", help="Specific branch to analyze (default: all branches)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
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
        authors = detect_authors(repo, branch=branch)

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
        None, "--old-email", "-e", help="Old author email to search for"
    ),
    old_name: Optional[str] = typer.Option(
        None, "--old-name", "-n", help="Old author name to search for"
    ),
    all_commits: bool = typer.Option(False, "--all", "-a", help="Show all commits"),
    map_all: bool = typer.Option(
        False, "--map-all", help="Alias for --all: show all commits (same as --all)"
    ),
    choose_old: bool = typer.Option(
        False, "--choose-old", help="Interactively select author(s) to filter by"
    ),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of commits to show"),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Path to Git repository (default: current directory)"
    ),
    branch: Optional[str] = typer.Option(
        None, "--branch", "-b", help="Specific branch to analyze (default: all branches)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
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
            authors = detect_authors(repo, branch=branch)
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
                        repo, email=author.email, name=author.name, limit=limit, branch=branch
                    )
                    commits.extend(author_commits)

                # Remove duplicates and limit
                seen = set()
                unique_commits = []
                for c in commits:
                    if c["hash"] not in seen:
                        seen.add(c["hash"])
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
                        commit["hash"][:8],
                        commit["author_name"],
                        commit["author_email"],
                        (
                            commit["subject"][:60] + "..."
                            if len(commit["subject"]) > 60
                            else commit["subject"]
                        ),
                    )

                console.print(table)

                if total_count > limit:
                    console.print(f"\n[dim]... and {total_count - limit} more commits[/dim]")

                raise typer.Exit(0)

            except (ValueError, IndexError):
                console.print("[bold red]Invalid selection[/bold red]")
                raise typer.Exit(1)

        if all_commits:
            commits = find_commits_by_author(repo, limit=limit, branch=branch)
        else:
            if not old_email and not old_name:
                console.print(
                    "[bold red]Error:[/bold red] Must specify --old-email, --old-name, or --all"
                )
                raise typer.Exit(1)

            commits = find_commits_by_author(
                repo, email=old_email, name=old_name, limit=limit, branch=branch
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
                commit["hash"][:8],
                commit["author_name"],
                commit["author_email"],
                (
                    commit["subject"][:60] + "..."
                    if len(commit["subject"]) > 60
                    else commit["subject"]
                ),
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
        None, "--output", "-o", help="Output directory for backup (default: parent directory)"
    ),
    format: str = typer.Option("tar.gz", "--format", "-f", help="Backup format: 'zip' or 'tar.gz'"),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Path to Git repository (default: current directory)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
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
        None, "--old-email", "-e", help="Old author email to replace"
    ),
    old_name: Optional[str] = typer.Option(
        None, "--old-name", "-n", help="Old author name to replace"
    ),
    new_name: Optional[str] = typer.Option(
        None, "--new-name", "-N", help="New author name (optional with --choose-old)"
    ),
    new_email: Optional[str] = typer.Option(
        None, "--new-email", "-E", help="New author email (optional with --choose-old)"
    ),
    all_commits: bool = typer.Option(
        False, "--all", "-a", help="Rewrite all commits regardless of author"
    ),
    map_all: bool = typer.Option(
        False, "--map-all", help="Alias for --all: map all authors to the new identity"
    ),
    no_backup: bool = typer.Option(False, "--no-backup", help="Skip automatic backup"),
    choose_old: bool = typer.Option(
        False,
        "--choose-old",
        help="Interactively select author(s) to rewrite and choose new identity",
    ),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Path to Git repository (default: current directory)"
    ),
    branch: Optional[str] = typer.Option(
        None, "--branch", "-b", help="Specific branch to rewrite (default: current branch)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
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
            authors = detect_authors(repo, branch=branch)
            if not authors:
                console.print("[yellow]No authors found to choose from[/yellow]")
                raise typer.Exit(0)

            sorted_authors = sorted(authors, key=lambda a: a.name.lower())

            # Step 1: Select old author(s) to rewrite
            console.print("\n[bold cyan]Step 1: Select author(s) to rewrite[/bold cyan]\n")
            for i, a in enumerate(sorted_authors, start=1):
                console.print(f"  {i}. {a.name} <{a.email}>")

            old_choice = typer.prompt(
                "\nEnter author number(s) (comma-separated for multiple)", default="1"
            )
            try:
                old_indices = [int(x.strip()) - 1 for x in old_choice.split(",")]
                chosen_old_authors = [sorted_authors[idx] for idx in old_indices]
            except (ValueError, IndexError):
                console.print("[bold red]Invalid selection[/bold red]")
                raise typer.Exit(1)

            console.print(
                f"\n[bold green]Selected {len(chosen_old_authors)} author(s) to rewrite:[/bold green]"
            )
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
        elif choose_old and "selected_old_authors" in locals():
            console.print(
                f"  [yellow]Mode:[/yellow] Rewrite {len(selected_old_authors)} selected author(s)"
            )
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
        if choose_old and "selected_old_authors" in locals():
            total_count = 0
            for a in selected_old_authors:
                count = repo.count_commits_by_author(email=a.email, name=a.name)
                total_count += count
            console.print(
                f"\n[bold yellow]This will affect approximately {total_count} commit(s)[/bold yellow]"
            )
        elif not all_commits:
            count = repo.count_commits_by_author(email=old_email, name=old_name)
            console.print(
                f"\n[bold yellow]This will affect approximately {count} commit(s)[/bold yellow]"
            )

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

        if choose_old and "selected_old_authors" in locals():
            # Rewrite multiple authors sequentially
            for i, old_author in enumerate(selected_old_authors, start=1):
                console.print(
                    f"\n[dim]Processing author {i}/{len(selected_old_authors)}: {old_author.name} <{old_author.email}>[/dim]"
                )
                rewrite_history(
                    repo,
                    old_email=old_author.email,
                    old_name=old_author.name,
                    new_name=new_name,
                    new_email=new_email,
                    rewrite_all=False,
                )
        else:
            rewrite_history(
                repo,
                old_email=old_email,
                old_name=old_name,
                new_name=new_name,
                new_email=new_email,
                rewrite_all=all_commits,
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
    force: bool = typer.Option(False, "--force", "-f", help="Force push without confirmation"),
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote name"),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Path to Git repository (default: current directory)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
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
            ["git", "push", "--force-with-lease", remote, current_branch], check=False
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


@app.command()
def arrange(
    start_commit: Optional[str] = typer.Option(
        None, "--start-commit", "-s", help="Starting commit hash (oldest)"
    ),
    end_commit: Optional[str] = typer.Option(
        None, "--end-commit", "-e", help="Ending commit hash (newest)"
    ),
    commits: Optional[str] = typer.Option(
        None,
        "--commits",
        "-c",
        help="Range of commits (e.g. 'HEAD~10..HEAD' or '50' for last 50). Overrides start/end.",
    ),
    start_date: Optional[str] = typer.Option(None, "--start-date", help="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, "--end-date", help="End date (YYYY-MM-DD)"),
    start_time: Optional[str] = typer.Option(None, "--start-time", help="Daily start time (HH:MM)"),
    end_time: Optional[str] = typer.Option(None, "--end-time", help="Daily end time (HH:MM)"),
    timezone: Optional[str] = typer.Option(None, "--timezone", help="Timezone (e.g. 'UTC')"),
    skip_weekends: Optional[bool] = typer.Option(
        None, "--skip-weekends/--no-skip-weekends", help="Skip weekends"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Force execution without confirmation"),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Path to Git repository (default: current directory)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """
    Arrange commit dates over a specified timeline.
    """
    setup_logging(verbose)

    try:
        repo = GitRepo(str(path) if path else None)

        if not repo.has_commits():
            console.print("[yellow]Repository has no commits yet[/yellow]")
            raise typer.Exit(0)

        # Determine Commit Range
        git_range = None

        # If --commits is provided, use it (shortcut)
        if commits:
            if commits.isdigit():
                git_range = f"HEAD~{commits}..HEAD"
            else:
                git_range = commits
        else:
            # Interactive / Explict Start & End
            if not start_commit:
                console.print("\n[bold]Select Commit Range:[/bold]")
                start_commit = typer.prompt(
                    "Enter STARTING commit hash (oldest)", default="HEAD~10"
                )

            if not end_commit:
                end_commit = typer.prompt("Enter ENDING commit hash (newest)", default="HEAD")

            # Validation
            console.print("[dim]Validating commits...[/dim]")

            # 1. Verify existence
            for name, rev in [("Start", start_commit), ("End", end_commit)]:
                res = repo._run_command(["git", "rev-parse", "--verify", rev], check=False)
                if res.returncode != 0:
                    console.print(f"[bold red]Error:[/bold red] {name} commit '{rev}' not found.")
                    raise typer.Exit(1)
                # Update to full hash
                if name == "Start":
                    start_commit = res.stdout.strip()
                if name == "End":
                    end_commit = res.stdout.strip()

            # 2. Verify ancestry (start must be ancestor of end)
            res = repo._run_command(
                ["git", "merge-base", "--is-ancestor", start_commit, end_commit], check=False
            )
            if res.returncode != 0:
                console.print(
                    f"[bold red]Error:[/bold red] Start commit must be an ancestor of end commit."
                )
                raise typer.Exit(1)

            # Construct range
            # We want to INCLUDE start_commit.
            # git log start..end excludes start.
            # So we use start^..end, but if start is root, this fails.
            # Safe way: git log --ancestry-path start..end + explicit start?
            # Or check if start has parent.

            has_parent = (
                repo._run_command(["git", "rev-parse", f"{start_commit}^"], check=False).returncode
                == 0
            )
            if has_parent:
                git_range = f"{start_commit}^..{end_commit}"
            else:
                git_range = end_commit  # All commits up to end (root included)

        # Interactive Time/Date setup
        if not start_date:
            default_start = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
            start_date = typer.prompt("Enter start date (YYYY-MM-DD)", default=default_start)

        if not end_date:
            default_end = datetime.date.today().isoformat()
            end_date = typer.prompt("Enter end date (YYYY-MM-DD)", default=default_end)

        if not start_time:
            start_time = typer.prompt("Start time for potential commits (HH:MM)", default="09:00")

        if not end_time:
            end_time = typer.prompt("End time for potential commits (HH:MM)", default="17:00")

        if not timezone:
            import time

            # Default to empty string to indicate "Local" to the backend
            # We can show a hint in the prompt
            timezone = typer.prompt("Enter timezone (leave empty for Local)", default="")

        if skip_weekends is None:
            skip_weekends = typer.confirm("Do you want to skip weekends?", default=True)

        # Process Inputs
        try:
            s_date = dateutil.parser.parse(start_date).date()
            e_date = dateutil.parser.parse(end_date).date()
        except Exception:
            console.print("[bold red]Invalid date format[/bold red]")
            raise typer.Exit(1)

        # Fetch commits
        console.print("[bold]Fetching commits...[/bold]")

        # Get list of commits in the range
        cmd = ["git", "log", "--format=%H", git_range]
        result = repo._run_command(cmd, check=False)
        if result.returncode != 0:
            console.print(f"[bold red]Error listing commits: {result.stderr}[/bold red]")
            raise typer.Exit(1)

        commit_hashes = result.stdout.strip().splitlines()

        # If using start_commit (manual range), verify start_commit is in the list
        # If we used start^..end, it should be.
        # If start was root, we used 'end', which includes root.

        if not commit_hashes:
            console.print("[yellow]No commits found in range[/yellow]")
            raise typer.Exit(0)

        commit_objects = [{"hash": h} for h in commit_hashes]

        # Calculate Schedule
        console.print("[bold]Calculating new schedule...[/bold]")
        schedule = calculate_schedule(
            repo, commit_objects, s_date, e_date, start_time, end_time, timezone, skip_weekends
        )

        console.print(f"[bold green]Scheduled {len(schedule)} commits.[/bold green]")

        # Preview
        console.print("\n[bold]Preview (first 5):[/bold]")
        preview_count = 0
        for h, date_str in schedule.items():
            if preview_count < 5:
                console.print(f"  {h[:8]} -> {date_str}")
                preview_count += 1

        if not force:
            if not typer.confirm("\nDo you want to apply these changes?"):
                console.print("[yellow]Aborted[/yellow]")
                raise typer.Exit(0)

        # Apply changes
        # check if filter-repo is available
        if not repo.has_filter_repo():
            console.print("[bold red]git-filter-repo is required for this command.[/bold red]")
            console.print("Please install it: pip install git-filter-repo")
            raise typer.Exit(1)

        # We need to construct a robust way to pass this map to filter-repo.
        # It supports --commit-callback "..."
        # We can inline the schedule map into the callback script?
        # Or write a callback python script to a temp file.

        import json
        import tempfile

        # Backup Remotes
        # git-filter-repo deletes remotes; we need to restore them.
        remotes = {}
        try:
            remote_lines = (
                repo._run_command(["git", "remote", "-v"], check=False).stdout.strip().splitlines()
            )
            for line in remote_lines:
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    name, url = parts[0], parts[1]
                    # Only Store fetch or push? Usually they are same or pairs.
                    # We can just store one URL per name (last one overwrites, usually fine as push url is what matters? or we add both?)
                    # simpler: just `git remote add name url` works for single url.
                    remotes[name] = url
        except Exception:
            console.print(
                "[yellow]Warning: Could not backup remotes. You may need to re-add them.[/yellow]"
            )

        # Create a temp file with the mapping
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schedule, f)
            schedule_path = f.name

        # Create the callback script
        callback_script = f"""
import json
import datetime
try:
    with open(r'{schedule_path}', 'r') as f:
        schedule = json.load(f)
except Exception:
    schedule = {{}}

commit_hash = commit.original_id.decode('utf-8')
if commit_hash in schedule:
    new_date_iso = schedule[commit_hash]
    
    dt = datetime.datetime.fromisoformat(new_date_iso)
    timestamp = int(dt.timestamp())
    offset = dt.strftime('%z')
    date_bytes = f"{{timestamp}} {{offset}}".encode('ascii')
    
    commit.author_date = date_bytes
    commit.committer_date = date_bytes
"""
        # Run filter-repo
        # git filter-repo --commit-callback "..." --force
        console.print("\n[bold]Rewriting history...[/bold]")

        cmd = ["git", "filter-repo", "--force", "--commit-callback", callback_script]

        result = repo._run_command(cmd, check=False)

        # Cleanup temp file
        import os

        try:
            os.unlink(schedule_path)
        except:
            pass

        # Restore Remotes
        if remotes:
            console.print("[dim]Restoring remotes...[/dim]")
            for name, url in remotes.items():
                # check if exists first? filter-repo should have deleted them.
                # git remote add name url
                repo._run_command(["git", "remote", "add", name, url], check=False)

        if result.returncode != 0:
            console.print(f"[bold red]Error rewriting history: {result.stderr}[/bold red]")
            raise typer.Exit(1)

        console.print("\n[bold green]✓ History rewritten successfully![/bold green]")
        console.print(
            "\n[bold]Next steps:[/bold]\n"
            "  1. Verify the changes: [cyan]git log[/cyan]\n"
            "  2. Force push to remote: [cyan]gitauth push[/cyan]\n"
        )

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
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
