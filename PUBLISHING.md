# Publishing GitAuth to PyPI - Step by Step Guide

## Prerequisites

1. **PyPI Account**: You need an account on https://pypi.org
   - Username: `mubshr`
   
2. **Test PyPI Account** (recommended): https://test.pypi.org
   - Username: `mubshr`

## Step 1: Get API Tokens

### For Test PyPI (recommended first)
1. Go to https://test.pypi.org/manage/account/token/
2. Click "Add API token"
3. Name: `gitauth-test`
4. Scope: "Entire account" or "Project: gitauth"
5. Copy the token (starts with `pypi-`)

### For Production PyPI
1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name: `gitauth`
4. Scope: "Entire account" or "Project: gitauth"
5. Copy the token (starts with `pypi-`)

## Step 2: Configure PyPI Credentials

Create `~/.pypirc` file:

```bash
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR-PRODUCTION-TOKEN-HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR-TEST-TOKEN-HERE
EOF

chmod 600 ~/.pypirc
```

**Replace the tokens with your actual tokens from Step 1!**

## Step 3: Install Build Tools

```bash
pip3 install --upgrade build twine
```

## Step 4: Build the Package

```bash
cd "/Users/mubasharhussain/Developer/Python Projects/gitauth"

# Clean previous builds
rm -rf dist/ build/ *.egg-info gitauth.egg-info

# Build source distribution and wheel
python3 -m build
```

This creates:
- `dist/gitauth-1.0.0.tar.gz`
- `dist/gitauth-1.0.0-py3-none-any.whl`

## Step 5: Check the Package

```bash
# Verify the package
twine check dist/*
```

You should see:
```
Checking dist/gitauth-1.0.0-py3-none-any.whl: PASSED
Checking dist/gitauth-1.0.0.tar.gz: PASSED
```

## Step 6: Test on Test PyPI (Recommended)

```bash
# Upload to Test PyPI
twine upload --repository testpypi dist/*
```

Enter your Test PyPI credentials when prompted (or use the token from ~/.pypirc).

### Install from Test PyPI

```bash
# Create a test environment
python3 -m venv test_env
source test_env/bin/activate

# Install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ gitauth

# Test it
gitauth --help

# Deactivate when done
deactivate
rm -rf test_env
```

## Step 7: Publish to Production PyPI

Once you've tested on Test PyPI and everything works:

```bash
# Upload to production PyPI
twine upload dist/*
```

Enter your PyPI credentials when prompted.

## Step 8: Verify Installation

```bash
# Create a clean environment
python3 -m venv verify_env
source verify_env/bin/activate

# Install from PyPI
pip install gitauth

# Test
gitauth --help
gitauth check

# Clean up
deactivate
rm -rf verify_env
```

## Step 9: Create Git Tag and Push

```bash
cd "/Users/mubasharhussain/Developer/Python Projects/gitauth"

# Initialize git if not already done
git init
git add .
git commit -m "Initial release v1.0.0"

# Add your GitHub repo as remote
git remote add origin https://github.com/mubashardev/gitauth.git

# Create and push tag
git tag v1.0.0
git push -u origin main
git push --tags
```

## Troubleshooting

### "Package already exists"
If you get this error, you need to bump the version:
1. Edit `pyproject.toml` and change version to `1.0.1`
2. Edit `gitauth/__init__.py` and change `__version__` to `1.0.1`
3. Rebuild: `python3 -m build`
4. Upload again

### "Invalid credentials"
Make sure you're using the API token, not your password:
- Username: `__token__`
- Password: `pypi-...` (your actual token)

### "twine not found"
```bash
pip3 install --upgrade twine
```

## Quick Reference Commands

```bash
# Full publishing workflow
cd "/Users/mubasharhussain/Developer/Python Projects/gitauth"
rm -rf dist/ build/ *.egg-info
python3 -m build
twine check dist/*
twine upload --repository testpypi dist/*  # Test first
twine upload dist/*                         # Production
```

## After Publishing

1. Check your package page: https://pypi.org/project/gitauth/
2. Update the README badge (optional):
   ```markdown
   [![PyPI](https://img.shields.io/pypi/v/gitauth.svg)](https://pypi.org/project/gitauth/)
   ```

3. Announce it! Share on:
   - Twitter/X
   - Reddit (r/Python)
   - Dev.to
   - Your blog

## Version Updates

When releasing new versions:

1. Update version in `pyproject.toml`
2. Update version in `gitauth/__init__.py`
3. Create CHANGELOG entry (optional)
4. Build and upload:
   ```bash
   rm -rf dist/
   python3 -m build
   twine upload dist/*
   ```
5. Create git tag:
   ```bash
   git tag v1.0.1
   git push --tags
   ```

---

**Ready to publish!** Follow the steps above and your package will be live on PyPI. 🚀
