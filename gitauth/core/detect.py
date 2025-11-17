"""Author detection functionality for Git repositories."""

import logging
from typing import Optional

from .git_utils import GitRepo

logger = logging.getLogger(__name__)


class Author:
    """Represents a Git author/committer."""

    def __init__(self, name: str, email: str):
        """
        Initialize an Author instance.

        Args:
            name: Author name
            email: Author email
        """
        self.name = name
        self.email = email

    def __eq__(self, other):
        """Check equality based on name and email."""
        if not isinstance(other, Author):
            return False
        return self.name == other.name and self.email == other.email

    def __hash__(self):
        """Make Author hashable for use in sets."""
        return hash((self.name, self.email))

    def __repr__(self):
        """String representation of Author."""
        return f"{self.name} <{self.email}>"

    def __str__(self):
        """String representation of Author."""
        return self.__repr__()


def detect_authors(repo: GitRepo) -> set[Author]:
    """
    Detect all unique authors in the repository.

    Args:
        repo: GitRepo instance

    Returns:
        Set of unique Author instances
    """
    logger.info("Detecting authors in repository...")

    # Get all unique authors
    result = repo._run_command([
        "git", "log", "--all", "--format=%an|%ae"
    ])

    authors = set()
    for line in result.stdout.strip().split('\n'):
        if line:
            parts = line.split('|')
            if len(parts) == 2:
                name, email = parts
                authors.add(Author(name, email))

    logger.info(f"Found {len(authors)} unique authors")
    return authors


def detect_committers(repo: GitRepo) -> set[Author]:
    """
    Detect all unique committers in the repository.

    Args:
        repo: GitRepo instance

    Returns:
        Set of unique Author instances (committers)
    """
    logger.info("Detecting committers in repository...")

    # Get all unique committers
    result = repo._run_command([
        "git", "log", "--all", "--format=%cn|%ce"
    ])

    committers = set()
    for line in result.stdout.strip().split('\n'):
        if line:
            parts = line.split('|')
            if len(parts) == 2:
                name, email = parts
                committers.add(Author(name, email))

    logger.info(f"Found {len(committers)} unique committers")
    return committers


def find_commits_by_author(
    repo: GitRepo,
    email: Optional[str] = None,
    name: Optional[str] = None,
    limit: Optional[int] = None
) -> list[dict]:
    """
    Find commits by a specific author.

    Args:
        repo: GitRepo instance
        email: Author email to filter by
        name: Author name to filter by
        limit: Maximum number of commits to return

    Returns:
        List of commit information dictionaries
    """
    logger.info(f"Finding commits by author (email={email}, name={name})...")

    cmd = ["git", "log", "--all", "--format=%H|%an|%ae|%s"]

    if email:
        cmd.extend(["--author", email])
    elif name:
        cmd.extend(["--author", name])

    result = repo._run_command(cmd)

    commits = []
    for line in result.stdout.strip().split('\n'):
        if line:
            parts = line.split('|', 3)
            if len(parts) >= 4:
                commit_info = {
                    'hash': parts[0],
                    'author_name': parts[1],
                    'author_email': parts[2],
                    'subject': parts[3]
                }
                commits.append(commit_info)

                if limit and len(commits) >= limit:
                    break

    logger.info(f"Found {len(commits)} commits")
    return commits


def matches_author(
    commit_info: dict,
    old_email: Optional[str] = None,
    old_name: Optional[str] = None
) -> bool:
    """
    Check if a commit matches the specified author criteria.

    Args:
        commit_info: Dictionary with commit information
        old_email: Email to match (case-insensitive)
        old_name: Name to match (case-insensitive)

    Returns:
        True if commit matches criteria, False otherwise
    """
    if old_email and old_name:
        # Both must match
        email_match = commit_info['author_email'].lower() == old_email.lower()
        name_match = commit_info['author_name'].lower() == old_name.lower()
        return email_match and name_match
    elif old_email:
        # Only email must match
        return commit_info['author_email'].lower() == old_email.lower()
    elif old_name:
        # Only name must match
        return commit_info['author_name'].lower() == old_name.lower()
    else:
        # No criteria - matches all
        return True
