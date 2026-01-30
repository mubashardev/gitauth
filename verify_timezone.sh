#!/bin/bash
set -e

# Cleanup
rm -rf test_repo_arrange
mkdir -p test_repo_arrange
cd test_repo_arrange

# Setup Repo
git init
git config user.name "Test User"
git config user.email "test@example.com"

# Create Commits
for i in {1..5}; do
    echo "content $i" > file_$i.txt
    git add .
    git commit -m "Commit $i" --date="2023-01-01T12:00:00"
done

# Get Hashes
START_HASH=$(git rev-parse HEAD~4) 
END_HASH=$(git rev-parse HEAD)

echo "Arranging from $START_HASH to $END_HASH"

# Run Arrange - using default (empty) timezone by NOT providing --timezone
# Note: In non-interactive mode (which --force implies somewhat, or flags), 
# if we don't provide --timezone, the defaults from Typer option are None.
# The CLI logic says: if not timezone: prompt...
# BUT if we are running with flags, we should be able to skip prompting?
# The CLI only prompts if arguments are MISSING.
# Wait, the CLI logic says: `if not timezone: timezone = typer.prompt(...)`. 
# This happens unconditionally if the argument is not provided.
# So I must provide an EMPTY string as argument to simulate "empty input" if checking logic?
# actually if I provide --timezone "", typer might pass it as empty string.

gitauth arrange \
  --start-commit "$START_HASH" \
  --end-commit "$END_HASH" \
  --start-date "2023-06-01" \
  --end-date "2023-06-05" \
  --start-time "09:00" \
  --end-time "17:00" \
  --timezone "" \
  --skip-weekends \
  --force \
  --verbose

echo "Success!"
