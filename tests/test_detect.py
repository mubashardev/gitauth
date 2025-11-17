"""Tests for detect module."""

import os
import tempfile
from pathlib import Path

import pytest

from gitauth.core.detect import Author, detect_authors, find_commits_by_author
from gitauth.core.git_utils import GitRepo


@pytest.fixture
def multi_author_repo():
    """Create a repository with multiple authors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo"
        repo_path.mkdir()

        # Initialize git repo
        os.system(f"cd {repo_path} && git init")

        # Create commits with different authors
        authors = [
            ("Alice", "alice@example.com"),
            ("Bob", "bob@example.com"),
            ("Charlie", "charlie@example.com"),
        ]

        for i, (name, email) in enumerate(authors):
            test_file = repo_path / f"file{i}.txt"
            test_file.write_text(f"content {i}")
            os.system(f"cd {repo_path} && git config user.name '{name}'")
            os.system(f"cd {repo_path} && git config user.email '{email}'")
            os.system(f"cd {repo_path} && git add file{i}.txt")
            os.system(f"cd {repo_path} && git commit -m 'Commit {i}'")

        yield repo_path


def test_author_equality():
    """Test Author equality comparison."""
    author1 = Author("John Doe", "john@example.com")
    author2 = Author("John Doe", "john@example.com")
    author3 = Author("Jane Doe", "jane@example.com")

    assert author1 == author2
    assert author1 != author3


def test_author_hash():
    """Test Author is hashable."""
    author1 = Author("John Doe", "john@example.com")
    author2 = Author("John Doe", "john@example.com")

    authors_set = {author1, author2}
    assert len(authors_set) == 1  # Should be deduplicated


def test_author_repr():
    """Test Author string representation."""
    author = Author("John Doe", "john@example.com")
    assert str(author) == "John Doe <john@example.com>"


def test_detect_authors(multi_author_repo):
    """Test detecting all authors in repository."""
    repo = GitRepo(str(multi_author_repo))
    authors = detect_authors(repo)

    assert len(authors) == 3
    author_emails = {author.email for author in authors}
    assert "alice@example.com" in author_emails
    assert "bob@example.com" in author_emails
    assert "charlie@example.com" in author_emails


def test_find_commits_by_email(multi_author_repo):
    """Test finding commits by author email."""
    repo = GitRepo(str(multi_author_repo))
    commits = find_commits_by_author(repo, email="alice@example.com")

    assert len(commits) >= 1
    assert all(c['author_email'] == "alice@example.com" for c in commits)


def test_find_commits_by_name(multi_author_repo):
    """Test finding commits by author name."""
    repo = GitRepo(str(multi_author_repo))
    commits = find_commits_by_author(repo, name="Bob")

    assert len(commits) >= 1
    assert all(c['author_name'] == "Bob" for c in commits)


def test_find_commits_limit(multi_author_repo):
    """Test limiting number of commits returned."""
    repo = GitRepo(str(multi_author_repo))
    commits = find_commits_by_author(repo, limit=2)

    assert len(commits) <= 2
