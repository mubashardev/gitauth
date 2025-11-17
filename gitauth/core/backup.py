"""Repository backup functionality."""

import datetime
import logging
import os
import tarfile
import zipfile
from pathlib import Path
from typing import Literal, Optional

from .git_utils import GitRepo

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Exception raised for backup-related errors."""
    pass


def create_backup(
    repo: GitRepo,
    output_dir: Optional[Path] = None,
    format: Literal["zip", "tar.gz"] = "tar.gz"
) -> Path:
    """
    Create a backup of the Git repository.

    Args:
        repo: GitRepo instance
        output_dir: Directory to save backup (default: parent of repo)
        format: Backup format - "zip" or "tar.gz"

    Returns:
        Path to the created backup file

    Raises:
        BackupError: If backup creation fails
    """
    logger.info(f"Creating backup of repository at {repo.path}...")

    # Generate backup filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    repo_name = repo.path.name
    
    if format == "zip":
        backup_name = f"backup-{repo_name}-{timestamp}.zip"
    else:
        backup_name = f"backup-{repo_name}-{timestamp}.tar.gz"

    # Determine output directory
    if output_dir is None:
        output_dir = repo.path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    backup_path = output_dir / backup_name

    try:
        if format == "zip":
            _create_zip_backup(repo.path, backup_path)
        else:
            _create_tar_backup(repo.path, backup_path)

        file_size = backup_path.stat().st_size
        size_mb = file_size / (1024 * 1024)
        logger.info(f"Backup created successfully: {backup_path} ({size_mb:.2f} MB)")

        return backup_path

    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        # Clean up partial backup if it exists
        if backup_path.exists():
            backup_path.unlink()
        raise BackupError(f"Failed to create backup: {e}") from e


def _create_zip_backup(source_path: Path, backup_path: Path) -> None:
    """
    Create a ZIP backup of the repository.

    Args:
        source_path: Path to the repository
        backup_path: Path for the backup file
    """
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_path):
            # Skip some directories that shouldn't be backed up
            dirs[:] = [d for d in dirs if d not in ['.tox', '__pycache__', '.pytest_cache']]

            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(source_path.parent)
                zipf.write(file_path, arcname)
                logger.debug(f"Added to backup: {arcname}")


def _create_tar_backup(source_path: Path, backup_path: Path) -> None:
    """
    Create a TAR.GZ backup of the repository.

    Args:
        source_path: Path to the repository
        backup_path: Path for the backup file
    """
    def filter_func(tarinfo):
        """Filter function to exclude certain files/directories."""
        name = Path(tarinfo.name).name
        if name in ['.tox', '__pycache__', '.pytest_cache']:
            return None
        return tarinfo

    with tarfile.open(backup_path, 'w:gz') as tar:
        tar.add(
            source_path,
            arcname=source_path.name,
            filter=filter_func
        )
        logger.debug(f"Added repository to tar archive")


def restore_backup(backup_path: Path, target_dir: Optional[Path] = None) -> Path:
    """
    Restore a repository from a backup file.

    Args:
        backup_path: Path to the backup file
        target_dir: Directory to restore to (default: parent of backup)

    Returns:
        Path to the restored repository

    Raises:
        BackupError: If restoration fails
    """
    logger.info(f"Restoring backup from {backup_path}...")

    if not backup_path.exists():
        raise BackupError(f"Backup file not found: {backup_path}")

    # Determine target directory
    if target_dir is None:
        target_dir = backup_path.parent / "restored"
    else:
        target_dir = Path(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        if backup_path.suffix == '.zip':
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(target_dir)
        elif backup_path.name.endswith('.tar.gz'):
            with tarfile.open(backup_path, 'r:gz') as tar:
                tar.extractall(target_dir)
        else:
            raise BackupError(f"Unsupported backup format: {backup_path}")

        logger.info(f"Backup restored successfully to: {target_dir}")
        return target_dir

    except Exception as e:
        logger.error(f"Failed to restore backup: {e}")
        raise BackupError(f"Failed to restore backup: {e}") from e


def list_backups(directory: Path) -> list[Path]:
    """
    List all backup files in a directory.

    Args:
        directory: Directory to search for backups

    Returns:
        List of backup file paths
    """
    if not directory.exists():
        return []

    backups = []
    for item in directory.iterdir():
        if item.is_file() and item.name.startswith("backup-"):
            if item.suffix == '.zip' or item.name.endswith('.tar.gz'):
                backups.append(item)

    return sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)
