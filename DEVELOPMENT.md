# GitAuth - Production Setup and Publishing Guide

## Quick Start

### 1. Install in Development Mode

```bash
# Clone or navigate to the project
cd gitauth

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### 2. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=gitauth tests/

# Run specific test file
pytest tests/test_git_utils.py -v
```

### 3. Format and Lint Code

```bash
# Format code with Black
black gitauth tests

# Lint with Ruff
ruff check gitauth tests

# Auto-fix issues
ruff check --fix gitauth tests
```

## Building for Distribution

### 1. Install Build Tools

```bash
pip install build twine
```

### 2. Build the Package

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build source distribution and wheel
python -m build
```

This creates:
- `dist/gitauth-1.0.0.tar.gz` (source distribution)
- `dist/gitauth-1.0.0-py3-none-any.whl` (wheel)

### 3. Check the Build

```bash
# Verify package metadata
twine check dist/*

# Test installation locally
pip install dist/gitauth-1.0.0-py3-none-any.whl
```

## Publishing to PyPI

### Test PyPI (Recommended First)

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Install from TestPyPI to test
pip install --index-url https://test.pypi.org/simple/ gitauth
```

### Production PyPI

```bash
# Upload to production PyPI
twine upload dist/*

# Verify installation
pip install gitauth
```

### Using PyPI API Tokens (Recommended)

1. Create an API token at https://pypi.org/manage/account/token/
2. Create `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-...your-token-here...

[testpypi]
username = __token__
password = pypi-...your-test-token-here...
```

## Version Management

Update version in `pyproject.toml`:

```toml
[project]
name = "gitauth"
version = "1.0.1"  # Update this
```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [created]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine
      - name: Build package
        run: python -m build
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

## Pre-Release Checklist

- [ ] All tests pass: `pytest`
- [ ] Code is formatted: `black .`
- [ ] No lint errors: `ruff check .`
- [ ] Version bumped in `pyproject.toml`
- [ ] `README.md` is up to date
- [ ] `CHANGELOG.md` is updated (if using)
- [ ] Built successfully: `python -m build`
- [ ] Package checks pass: `twine check dist/*`
- [ ] Tested on TestPyPI
- [ ] Git tag created: `git tag v1.0.0 && git push --tags`

## Common Issues

### ModuleNotFoundError

**Problem**: Package not found after installation

**Solution**: Ensure `pyproject.toml` has correct package discovery:

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["gitauth*"]
```

### Import Errors

**Problem**: Cannot import modules

**Solution**: Check that `__init__.py` exists in all package directories

### Missing Dependencies

**Problem**: Dependencies not installed

**Solution**: Ensure all dependencies are listed in `pyproject.toml`:

```toml
dependencies = [
    "typer[all]>=0.9.0",
]
```

## Manual Installation Test

```bash
# Create clean virtual environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install from wheel
pip install dist/gitauth-1.0.0-py3-none-any.whl

# Test CLI
gitauth --help
gitauth check

# Deactivate
deactivate
```

## Documentation

Generate documentation with Sphinx (optional):

```bash
pip install sphinx sphinx-rtd-theme
cd docs
sphinx-quickstart
make html
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/mubashardev/gitauth/issues
- Documentation: https://github.com/mubashardev/gitauth#readme
