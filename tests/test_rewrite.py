"""Tests for rewrite module."""

import os
import tempfile
from pathlib import Path

import pytest

from gitauth.core.git_utils import GitRepo
from gitauth.core.rewrite import get_rewrite_engine, rewrite_history, RewriteError


@pytest.fixture
def temp_git_repo():
    """Create a temporary Git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo"
        repo_path.mkdir()

        # Initialize git repo
        os.system(f"cd {repo_path} && git init")
        os.system(f"cd {repo_path} && git config user.name 'Old Name'")
        os.system(f"cd {repo_path} && git config user.email 'old@example.com'")

        # Create initial commits
        for i in range(3):
            test_file = repo_path / f"file{i}.txt"
            test_file.write_text(f"content {i}")
            os.system(f"cd {repo_path} && git add file{i}.txt")
            os.system(f"cd {repo_path} && git commit -m 'Commit {i}'")

        yield repo_path


def test_get_rewrite_engine(temp_git_repo):
    """Test getting appropriate rewrite engine."""
    repo = GitRepo(str(temp_git_repo))
    engine = get_rewrite_engine(repo)

    assert engine is not None
    assert hasattr(engine, 'rewrite')


def test_rewrite_history_missing_new_name(temp_git_repo):
    """Test rewrite_history raises error when new_name is missing."""
    repo = GitRepo(str(temp_git_repo))

    with pytest.raises(RewriteError, match="new_name and new_email are required"):
        rewrite_history(
            repo,
            old_email="old@example.com",
            new_email="new@example.com"
        )


def test_rewrite_history_missing_new_email(temp_git_repo):
    """Test rewrite_history raises error when new_email is missing."""
    repo = GitRepo(str(temp_git_repo))

    with pytest.raises(RewriteError, match="new_name and new_email are required"):
        rewrite_history(
            repo,
            old_email="old@example.com",
            new_name="New Name"
        )


def test_rewrite_history_invalid_email(temp_git_repo):
    """Test rewrite_history raises error for invalid email."""
    repo = GitRepo(str(temp_git_repo))

    with pytest.raises(RewriteError, match="Invalid email format"):
        rewrite_history(
            repo,
            old_email="old@example.com",
            new_name="New Name",
            new_email="invalid-email"
        )


def test_rewrite_history_missing_criteria(temp_git_repo):
    """Test rewrite_history raises error when no criteria specified."""
    repo = GitRepo(str(temp_git_repo))

    with pytest.raises(RewriteError, match="Must specify"):
        rewrite_history(
            repo,
            new_name="New Name",
            new_email="new@example.com"
        )


# Note: Full integration tests for actual rewriting would require
# git-filter-repo or would modify the git history, which is complex
# to test in unit tests. These tests focus on validation logic.
# Integration tests should be run in a separate test suite.
