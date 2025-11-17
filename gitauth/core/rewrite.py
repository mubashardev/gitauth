"""Git history rewriting functionality using filter-repo or filter-branch."""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from .git_utils import GitRepo

logger = logging.getLogger(__name__)


class RewriteError(Exception):
    """Exception raised for rewrite-related errors."""
    pass


class RewriteEngine:
    """Base class for Git history rewriting engines."""

    def __init__(self, repo: GitRepo):
        """
        Initialize a RewriteEngine.

        Args:
            repo: GitRepo instance
        """
        self.repo = repo

    def rewrite(
        self,
        old_email: Optional[str] = None,
        old_name: Optional[str] = None,
        new_name: Optional[str] = None,
        new_email: Optional[str] = None,
        rewrite_all: bool = False
    ) -> None:
        """
        Rewrite commit authors/committers.

        Args:
            old_email: Old author email to replace
            old_name: Old author name to replace
            new_name: New author name
            new_email: New author email
            rewrite_all: If True, rewrite all commits regardless of author

        Raises:
            RewriteError: If rewrite fails
        """
        raise NotImplementedError("Subclasses must implement rewrite()")


class FilterRepoEngine(RewriteEngine):
    """Rewrite engine using git-filter-repo."""

    def rewrite(
        self,
        old_email: Optional[str] = None,
        old_name: Optional[str] = None,
        new_name: Optional[str] = None,
        new_email: Optional[str] = None,
        rewrite_all: bool = False
    ) -> None:
        """
        Rewrite commit authors using git-filter-repo.

        Args:
            old_email: Old author email to replace
            old_name: Old author name to replace
            new_name: New author name
            new_email: New author email
            rewrite_all: If True, rewrite all commits regardless of author
        """
        logger.info("Using git-filter-repo for rewriting...")

        # Create mailmap content
        mailmap_content = self._create_mailmap(
            old_email, old_name, new_name, new_email, rewrite_all
        )

        # Write mailmap to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mailmap', delete=False) as f:
            f.write(mailmap_content)
            mailmap_path = f.name

        try:
            logger.debug(f"Mailmap content:\n{mailmap_content}")

            # Run git-filter-repo with mailmap
            cmd = [
                "git", "filter-repo",
                "--force",
                "--mailmap", mailmap_path
            ]

            result = self.repo._run_command(cmd, check=False)

            if result.returncode != 0:
                raise RewriteError(
                    f"git-filter-repo failed with exit code {result.returncode}\n"
                    f"Error: {result.stderr}"
                )

            logger.info("Successfully rewrote history using git-filter-repo")

        finally:
            # Clean up temporary mailmap file
            Path(mailmap_path).unlink(missing_ok=True)

    def _create_mailmap(
        self,
        old_email: Optional[str],
        old_name: Optional[str],
        new_name: Optional[str],
        new_email: Optional[str],
        rewrite_all: bool
    ) -> str:
        """
        Create mailmap content for git-filter-repo.

        Mailmap format: New Name <new@email.com> <old@email.com>
        or: New Name <new@email.com> Old Name <old@email.com>

        Args:
            old_email: Old author email
            old_name: Old author name
            new_name: New author name
            new_email: New author email
            rewrite_all: If True, match all authors

        Returns:
            Mailmap content as string
        """
        if rewrite_all:
            # For rewriting all commits, we need to get all unique authors
            # and create mailmap entries for each
            from .detect import detect_authors

            authors = detect_authors(self.repo)
            lines = []
            for author in authors:
                lines.append(f"{new_name} <{new_email}> {author.name} <{author.email}>")
            return '\n'.join(lines)

        # Build mailmap entry for specific author
        if old_email and old_name:
            # Both name and email specified
            return f"{new_name} <{new_email}> {old_name} <{old_email}>"
        elif old_email:
            # Only email specified - match any name with this email
            return f"{new_name} <{new_email}> <{old_email}>"
        elif old_name:
            # Only name specified - this is tricky with mailmap
            # We need to find the email(s) associated with this name
            from .detect import detect_authors

            authors = detect_authors(self.repo)
            lines = []
            for author in authors:
                if author.name.lower() == old_name.lower():
                    lines.append(f"{new_name} <{new_email}> {author.name} <{author.email}>")

            if not lines:
                raise RewriteError(f"No authors found with name: {old_name}")

            return '\n'.join(lines)
        else:
            raise RewriteError("Must specify old_email, old_name, or rewrite_all")


class FilterBranchEngine(RewriteEngine):
    """Rewrite engine using git-filter-branch (fallback)."""

    def rewrite(
        self,
        old_email: Optional[str] = None,
        old_name: Optional[str] = None,
        new_name: Optional[str] = None,
        new_email: Optional[str] = None,
        rewrite_all: bool = False
    ) -> None:
        """
        Rewrite commit authors using git-filter-branch.

        Args:
            old_email: Old author email to replace
            old_name: Old author name to replace
            new_name: New author name
            new_email: New author email
            rewrite_all: If True, rewrite all commits regardless of author
        """
        logger.info("Using git-filter-branch for rewriting...")
        logger.warning(
            "git-filter-branch is deprecated. Consider installing git-filter-repo for better performance."
        )

        # Create the filter script
        filter_script = self._create_filter_script(
            old_email, old_name, new_name, new_email, rewrite_all
        )

        logger.debug(f"Filter script:\n{filter_script}")

        # Set environment for filter-branch
        env = os.environ.copy()
        env['FILTER_BRANCH_SQUELCH_WARNING'] = '1'

        # Remove backup refs if they exist
        self._remove_original_refs()

        try:
            # Run git-filter-branch
            cmd = [
                "git", "filter-branch",
                "--force",
                "--env-filter", filter_script,
                "--tag-name-filter", "cat",
                "--", "--branches", "--tags"
            ]

            result = self.repo._run_command(cmd, check=False, env=env)

            if result.returncode != 0:
                raise RewriteError(
                    f"git-filter-branch failed with exit code {result.returncode}\n"
                    f"Error: {result.stderr}"
                )

            logger.info("Successfully rewrote history using git-filter-branch")

            # Clean up
            self._remove_original_refs()

        except Exception as e:
            logger.error(f"Rewrite failed: {e}")
            raise

    def _create_filter_script(
        self,
        old_email: Optional[str],
        old_name: Optional[str],
        new_name: Optional[str],
        new_email: Optional[str],
        rewrite_all: bool
    ) -> str:
        """
        Create bash script for git-filter-branch env-filter.

        Args:
            old_email: Old author email
            old_name: Old author name
            new_name: New author name
            new_email: New author email
            rewrite_all: If True, match all authors

        Returns:
            Bash script as string
        """
        if rewrite_all:
            # Rewrite all commits
            return f'''
export GIT_AUTHOR_NAME="{new_name}"
export GIT_AUTHOR_EMAIL="{new_email}"
export GIT_COMMITTER_NAME="{new_name}"
export GIT_COMMITTER_EMAIL="{new_email}"
'''

        conditions = []

        if old_email:
            conditions.append(f'[ "$GIT_AUTHOR_EMAIL" = "{old_email}" ]')
        if old_name:
            conditions.append(f'[ "$GIT_AUTHOR_NAME" = "{old_name}" ]')

        if not conditions:
            raise RewriteError("Must specify old_email, old_name, or rewrite_all")

        condition = " && ".join(conditions) if len(conditions) > 1 else conditions[0]

        script = f'''
if {condition}
then
    export GIT_AUTHOR_NAME="{new_name}"
    export GIT_AUTHOR_EMAIL="{new_email}"
    export GIT_COMMITTER_NAME="{new_name}"
    export GIT_COMMITTER_EMAIL="{new_email}"
fi
'''
        return script

    def _remove_original_refs(self) -> None:
        """Remove refs/original/* references created by filter-branch."""
        try:
            self.repo._run_command(
                ["git", "for-each-ref", "--format=%(refname)", "refs/original/"],
                check=False
            )
            # If there are refs, remove them
            self.repo._run_command(
                ["git", "update-ref", "-d", "refs/original/refs/heads/master"],
                check=False
            )
            # Remove the entire refs/original directory
            original_dir = self.repo.path / ".git" / "refs" / "original"
            if original_dir.exists():
                import shutil
                shutil.rmtree(original_dir)
        except Exception as e:
            logger.debug(f"Could not remove original refs: {e}")


def get_rewrite_engine(repo: GitRepo) -> RewriteEngine:
    """
    Get the appropriate rewrite engine based on availability.

    Args:
        repo: GitRepo instance

    Returns:
        RewriteEngine instance (FilterRepoEngine or FilterBranchEngine)
    """
    if repo.has_filter_repo():
        logger.info("git-filter-repo is available")
        return FilterRepoEngine(repo)
    else:
        logger.warning("git-filter-repo not found, falling back to git-filter-branch")
        return FilterBranchEngine(repo)


def rewrite_history(
    repo: GitRepo,
    old_email: Optional[str] = None,
    old_name: Optional[str] = None,
    new_name: Optional[str] = None,
    new_email: Optional[str] = None,
    rewrite_all: bool = False,
    use_filter_repo: Optional[bool] = None
) -> None:
    """
    Rewrite Git history to change author information.

    Args:
        repo: GitRepo instance
        old_email: Old author email to replace
        old_name: Old author name to replace
        new_name: New author name
        new_email: New author email
        rewrite_all: If True, rewrite all commits regardless of author
        use_filter_repo: Force use of filter-repo (True) or filter-branch (False).
                        If None, automatically choose based on availability.

    Raises:
        RewriteError: If rewrite fails
    """
    # Validate inputs
    if not new_name or not new_email:
        raise RewriteError("new_name and new_email are required")

    if not repo.validate_email(new_email):
        raise RewriteError(f"Invalid email format: {new_email}")

    if not rewrite_all and not old_email and not old_name:
        raise RewriteError("Must specify old_email, old_name, or use rewrite_all=True")

    # Get appropriate engine
    if use_filter_repo is True:
        if not repo.has_filter_repo():
            raise RewriteError("git-filter-repo is not installed")
        engine = FilterRepoEngine(repo)
    elif use_filter_repo is False:
        engine = FilterBranchEngine(repo)
    else:
        engine = get_rewrite_engine(repo)

    # Perform rewrite
    engine.rewrite(
        old_email=old_email,
        old_name=old_name,
        new_name=new_name,
        new_email=new_email,
        rewrite_all=rewrite_all
    )
