"""Tests for git_utils module."""

import os
import tempfile
from pathlib import Path

import pytest

from gitauth.core.git_utils import GitError, GitRepo


@pytest.fixture
def temp_git_repo():
    """Create a temporary Git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test_repo"
        repo_path.mkdir()

        # Initialize git repo
        os.system(f"cd {repo_path} && git init")
        os.system(f"cd {repo_path} && git config user.name 'Test User'")
        os.system(f"cd {repo_path} && git config user.email 'test@example.com'")

        # Create initial commit
        test_file = repo_path / "test.txt"
        test_file.write_text("test content")
        os.system(f"cd {repo_path} && git add test.txt")
        os.system(f"cd {repo_path} && git commit -m 'Initial commit'")

        yield repo_path


def test_git_repo_init_valid(temp_git_repo):
    """Test GitRepo initialization with valid repository."""
    repo = GitRepo(str(temp_git_repo))
    assert repo.path == temp_git_repo


def test_git_repo_init_invalid():
    """Test GitRepo initialization with invalid repository."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(GitError):
            GitRepo(tmpdir)


def test_is_clean_true(temp_git_repo):
    """Test is_clean returns True for clean repository."""
    repo = GitRepo(str(temp_git_repo))
    assert repo.is_clean() is True


def test_is_clean_false(temp_git_repo):
    """Test is_clean returns False for dirty repository."""
    repo = GitRepo(str(temp_git_repo))

    # Create uncommitted change
    test_file = temp_git_repo / "new.txt"
    test_file.write_text("new content")

    assert repo.is_clean() is False


def test_get_current_branch(temp_git_repo):
    """Test getting current branch name."""
    repo = GitRepo(str(temp_git_repo))
    branch = repo.get_current_branch()
    assert branch in ["main", "master"]  # Could be either depending on Git version


def test_has_commits_true(temp_git_repo):
    """Test has_commits returns True when repository has commits."""
    repo = GitRepo(str(temp_git_repo))
    assert repo.has_commits() is True


def test_validate_email_valid():
    """Test email validation with valid emails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test"
        repo_path.mkdir()
        os.system(f"cd {repo_path} && git init")

        repo = GitRepo(str(repo_path))

        assert repo.validate_email("test@example.com") is True
        assert repo.validate_email("user.name@domain.co.uk") is True
        assert repo.validate_email("test+tag@example.com") is True


def test_validate_email_invalid():
    """Test email validation with invalid emails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "test"
        repo_path.mkdir()
        os.system(f"cd {repo_path} && git init")

        repo = GitRepo(str(repo_path))

        assert repo.validate_email("invalid") is False
        assert repo.validate_email("invalid@") is False
        assert repo.validate_email("@example.com") is False
        assert repo.validate_email("no-at-sign.com") is False


def test_get_all_commits(temp_git_repo):
    """Test getting all commit hashes."""
    repo = GitRepo(str(temp_git_repo))
    commits = repo.get_all_commits()

    assert len(commits) >= 1
    assert all(len(commit) == 40 for commit in commits)  # SHA-1 hashes are 40 chars


def test_get_commit_info(temp_git_repo):
    """Test getting commit information."""
    repo = GitRepo(str(temp_git_repo))
    commits = repo.get_all_commits()

    info = repo.get_commit_info(commits[0])

    assert 'hash' in info
    assert 'author_name' in info
    assert 'author_email' in info
    assert 'subject' in info
    assert info['author_name'] == 'Test User'
    assert info['author_email'] == 'test@example.com'
