"""Git utilities for repository operations and validation."""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Base exception for Git-related errors."""
    pass


class GitRepo:
    """Represents a Git repository with utility methods."""

    def __init__(self, path: Optional[str] = None):
        """
        Initialize a GitRepo instance.

        Args:
            path: Path to the Git repository. If None, uses current directory.
        """
        self.path = Path(path) if path else Path.cwd()
        self._validate_repo()

    def _validate_repo(self) -> None:
        """Validate that the path is a Git repository."""
        if not self._is_git_repo():
            raise GitError(f"{self.path} is not a Git repository")

    def _is_git_repo(self) -> bool:
        """Check if the current path is a Git repository."""
        git_dir = self.path / ".git"
        return git_dir.exists() or self._run_command(
            ["git", "rev-parse", "--git-dir"],
            check=False,
            capture_output=True
        ).returncode == 0

    def _run_command(
        self,
        cmd: list[str],
        check: bool = True,
        capture_output: bool = True,
        env: Optional[dict] = None
    ) -> subprocess.CompletedProcess:
        """
        Run a command in the repository directory.

        Args:
            cmd: Command and arguments as a list
            check: Whether to raise on non-zero exit code
            capture_output: Whether to capture stdout/stderr
            env: Optional environment variables

        Returns:
            CompletedProcess instance
        """
        logger.debug(f"Running command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.path,
                check=check,
                capture_output=capture_output,
                text=True,
                env=env
            )
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}")
            logger.error(f"Exit code: {e.returncode}")
            if e.stderr:
                logger.error(f"Error output: {e.stderr}")
            raise GitError(f"Git command failed: {e.stderr}") from e
        except FileNotFoundError as e:
            raise GitError(f"Command not found: {cmd[0]}") from e

    def is_clean(self) -> bool:
        """
        Check if the working directory is clean (no uncommitted changes).

        Returns:
            True if clean, False otherwise
        """
        result = self._run_command(
            ["git", "status", "--porcelain"],
            check=False
        )
        return result.returncode == 0 and not result.stdout.strip()

    def get_current_branch(self) -> str:
        """
        Get the current branch name.

        Returns:
            Branch name
        """
        result = self._run_command(["git", "branch", "--show-current"])
        return result.stdout.strip()

    def has_commits(self) -> bool:
        """
        Check if the repository has any commits.

        Returns:
            True if repository has commits, False otherwise
        """
        result = self._run_command(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True
        )
        return result.returncode == 0

    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        """
        Get the URL of a remote.

        Args:
            remote: Remote name (default: "origin")

        Returns:
            Remote URL or None if not found
        """
        result = self._run_command(
            ["git", "config", "--get", f"remote.{remote}.url"],
            check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def has_filter_repo(self) -> bool:
        """
        Check if git-filter-repo is installed.

        Returns:
            True if git-filter-repo is available, False otherwise
        """
        # Try as a git subcommand first
        result = subprocess.run(
            ["git", "filter-repo", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True

        # Try as a standalone command
        return shutil.which("git-filter-repo") is not None

    def validate_email(self, email: str) -> bool:
        """
        Validate email format.

        Args:
            email: Email address to validate

        Returns:
            True if valid, False otherwise
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def get_all_commits(self) -> list[str]:
        """
        Get all commit hashes in the repository.

        Returns:
            List of commit hashes
        """
        result = self._run_command(["git", "rev-list", "--all"])
        return result.stdout.strip().split('\n') if result.stdout.strip() else []

    def get_commit_info(self, commit_hash: str) -> dict:
        """
        Get detailed information about a commit.

        Args:
            commit_hash: Commit hash

        Returns:
            Dictionary with commit information
        """
        format_str = "%H%n%an%n%ae%n%cn%n%ce%n%at%n%ct%n%s"
        result = self._run_command(["git", "show", "-s", f"--format={format_str}", commit_hash])

        lines = result.stdout.strip().split('\n')
        return {
            'hash': lines[0],
            'author_name': lines[1],
            'author_email': lines[2],
            'committer_name': lines[3],
            'committer_email': lines[4],
            'author_timestamp': lines[5],
            'committer_timestamp': lines[6],
            'subject': lines[7] if len(lines) > 7 else ''
        }

    def count_commits_by_author(self, email: Optional[str] = None, name: Optional[str] = None) -> int:
        """
        Count commits by a specific author.

        Args:
            email: Author email to filter by
            name: Author name to filter by

        Returns:
            Number of commits
        """
        cmd = ["git", "rev-list", "--all", "--count"]

        if email:
            cmd.extend(["--author", email])
        if name:
            cmd.extend(["--author", name])

        result = self._run_command(cmd)
        return int(result.stdout.strip())

    def create_backup_ref(self) -> str:
        """
        Create a backup reference before rewriting history.

        Returns:
            Name of the backup reference
        """
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_ref = f"refs/original/backup_{timestamp}"

        current_branch = self.get_current_branch()
        self._run_command(["git", "update-ref", backup_ref, current_branch])

        logger.info(f"Created backup reference: {backup_ref}")
        return backup_ref

    def has_remote(self, remote: str = "origin") -> bool:
        """
        Check if a remote exists.

        Args:
            remote: Remote name

        Returns:
            True if remote exists, False otherwise
        """
        result = self._run_command(
            ["git", "remote", "get-url", remote],
            check=False,
            capture_output=True
        )
        return result.returncode == 0
