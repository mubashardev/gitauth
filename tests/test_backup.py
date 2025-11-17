"""Tests for backup module."""

import os
import tempfile
from pathlib import Path

import pytest

from gitauth.core.backup import create_backup, list_backups, restore_backup
from gitauth.core.git_utils import GitRepo


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


def test_create_backup_tar_gz(temp_git_repo):
    """Test creating a tar.gz backup."""
    repo = GitRepo(str(temp_git_repo))
    backup_path = create_backup(repo, format="tar.gz")

    assert backup_path.exists()
    assert backup_path.suffix == ".gz"
    assert backup_path.name.startswith("backup-")
    assert backup_path.stat().st_size > 0

    # Clean up
    backup_path.unlink()


def test_create_backup_zip(temp_git_repo):
    """Test creating a zip backup."""
    repo = GitRepo(str(temp_git_repo))
    backup_path = create_backup(repo, format="zip")

    assert backup_path.exists()
    assert backup_path.suffix == ".zip"
    assert backup_path.name.startswith("backup-")
    assert backup_path.stat().st_size > 0

    # Clean up
    backup_path.unlink()


def test_create_backup_custom_output_dir(temp_git_repo):
    """Test creating backup in custom directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "backups"

        repo = GitRepo(str(temp_git_repo))
        backup_path = create_backup(repo, output_dir=output_dir, format="tar.gz")

        assert backup_path.parent == output_dir
        assert backup_path.exists()

        # Clean up
        backup_path.unlink()


def test_list_backups(temp_git_repo):
    """Test listing backups in directory."""
    repo = GitRepo(str(temp_git_repo))

    # Create multiple backups
    backup1 = create_backup(repo, format="tar.gz")
    backup2 = create_backup(repo, format="zip")

    # List backups
    backups = list_backups(backup1.parent)

    assert len(backups) >= 2
    assert backup1 in backups
    assert backup2 in backups

    # Clean up
    backup1.unlink()
    backup2.unlink()


def test_list_backups_empty_directory():
    """Test listing backups in empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backups = list_backups(Path(tmpdir))
        assert len(backups) == 0


def test_restore_backup_tar_gz(temp_git_repo):
    """Test restoring from tar.gz backup."""
    repo = GitRepo(str(temp_git_repo))
    backup_path = create_backup(repo, format="tar.gz")

    with tempfile.TemporaryDirectory() as tmpdir:
        restore_dir = Path(tmpdir) / "restored"
        restored_path = restore_backup(backup_path, restore_dir)

        assert restored_path.exists()
        # Check that .git directory was restored
        git_dirs = list(restored_path.rglob(".git"))
        assert len(git_dirs) > 0

    # Clean up
    backup_path.unlink()


def test_restore_backup_zip(temp_git_repo):
    """Test restoring from zip backup."""
    repo = GitRepo(str(temp_git_repo))
    backup_path = create_backup(repo, format="zip")

    with tempfile.TemporaryDirectory() as tmpdir:
        restore_dir = Path(tmpdir) / "restored"
        restored_path = restore_backup(backup_path, restore_dir)

        assert restored_path.exists()
        # Check that .git directory was restored
        git_dirs = list(restored_path.rglob(".git"))
        assert len(git_dirs) > 0

    # Clean up
    backup_path.unlink()
