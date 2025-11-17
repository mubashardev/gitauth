# Interactive Author Selection Guide

## New Feature: `--choose-old`

The `--choose-old` flag provides an interactive workflow to select author(s) and map them to a new identity.

## How It Works

### Step 1: Select Old Author(s) to Rewrite
When you run `gitauth rewrite --choose-old`, you'll see a list of all authors in the repository:

```
Step 1: Select author(s) to rewrite

  1. Alice Developer <alice@example.com>
  2. Bob Smith <bob@company.com>
  3. Charlie Jones <charlie@gmail.com>

Enter author number(s) (comma-separated for multiple): 
```

**You can select:**
- Single author: `1`
- Multiple authors: `1,3` or `1, 2, 3`

### Step 2: Choose New Identity
After selecting old author(s), you choose the new identity:

```
Step 2: Choose new identity

Options:
  1. Select from existing authors
  2. Enter new author details

Enter choice (1 or 2): 
```

**Option 1: Select from existing authors**
- Useful when consolidating multiple identities into one existing identity
- Shows the same list of authors to pick from

**Option 2: Enter new author details**
- Enter a completely new name and email
- You'll be prompted for name and email if not provided via CLI flags

## Usage Examples

### Example 1: Map Multiple Authors to New Identity

```bash
# Interactive selection
gitauth rewrite --choose-old

# Follow the prompts:
# 1. Select authors: 1,2,3
# 2. Choose option 2 (new details)
# 3. Enter new name: "Unified Developer"
# 4. Enter new email: "unified@example.com"
```

### Example 2: Map Authors to Existing Identity

```bash
# Interactive selection
gitauth rewrite --choose-old

# Follow the prompts:
# 1. Select authors: 1,3
# 2. Choose option 1 (existing author)
# 3. Select author: 2
```

This maps authors 1 and 3 to author 2's identity.

### Example 3: Dry Run with Author Selection

```bash
# Preview commits from selected authors
gitauth dry-run --choose-old

# Select authors (e.g., 1,2) to see their commits
```

### Example 4: Pre-specify New Identity

```bash
# Skip the new identity prompt by providing it upfront
gitauth rewrite --choose-old \
  --new-name "New Developer" \
  --new-email "new@example.com"

# You'll only be asked to select old author(s)
# Then select option 2 to use the provided details
```

## Other Options

### Map All Authors to One

```bash
# Map ALL authors in the repo to a single identity
gitauth rewrite --all \
  --new-name "Single Author" \
  --new-email "single@example.com"

# Or use --map-all (alias for --all)
gitauth rewrite --map-all \
  --new-name "Single Author" \
  --new-email "single@example.com"
```

### Traditional Single Author Rewrite

```bash
# Rewrite specific email
gitauth rewrite \
  --old-email "old@example.com" \
  --new-name "New Name" \
  --new-email "new@example.com"
```

## Benefits

✅ **Multi-select**: Choose multiple old authors at once  
✅ **Flexible destination**: Pick existing author or enter new details  
✅ **Interactive**: No need to remember emails/names  
✅ **Preview**: Use with `dry-run` to see affected commits  
✅ **Safe**: Automatic backup before rewriting

## Full Workflow Example

```bash
# 1. Check current authors
gitauth check

# 2. Preview commits from specific authors
gitauth dry-run --choose-old
# Select authors: 1,2

# 3. Rewrite those authors to new identity
gitauth rewrite --choose-old
# Select authors: 1,2
# Choose option 2 (new details)
# Enter name: "Consolidated Dev"
# Enter email: "dev@team.com"
# Confirm: yes

# 4. Push changes
gitauth push
```

## Tips

- Use `gitauth check` first to see all authors
- Use `dry-run --choose-old` to preview before rewriting
- Select multiple authors with commas: `1,2,3`
- Spaces in selection are OK: `1, 2, 3`
- Automatic backup is created before rewriting (unless `--no-backup`)

---

**Note**: History rewriting is destructive. Always backup and coordinate with your team before force-pushing.
