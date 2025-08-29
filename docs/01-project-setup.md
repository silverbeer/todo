# Project Setup - Implementation Plan

## Overview
This document outlines the initial project setup using modern Python tooling with uv, pyproject.toml, and comprehensive quality tooling.

## Step 1: Initialize Project Structure

### Create Directory Structure
```bash
mkdir -p todo/src/todo
mkdir -p todo/tests/{unit,integration,e2e}
mkdir -p todo/src/todo/{ai,cli,core,db}
cd todo
```

### Initialize uv Project
```bash
# Initialize new project with uv
uv init --name todo --python ">=3.13"

# Verify Python version
uv python install 3.13
uv python pin 3.13
```

## Step 2: Configure pyproject.toml

### Core Configuration
```toml
[project]
name = "todo"
version = "0.1.0"
description = "AI-powered terminal todo application for developers"
authors = [{name = "Your Name", email = "your.email@example.com"}]
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.13"
keywords = ["todo", "cli", "ai", "productivity", "terminal"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Topic :: Office/Business :: Scheduling",
    "Topic :: Utilities",
]

dependencies = [
    "typer[all]>=0.12.0",
    "rich>=13.7.0",
    "pydantic>=2.8.0",
    "pydantic-ai>=0.0.13",
    "duckdb>=1.0.0",
    "openai>=1.40.0",
    "anthropic>=0.34.0",
    "python-dotenv>=1.0.0",
    "click>=8.1.7",  # Required by typer
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=5.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.14.0",
    "mypy>=1.11.0",
    "ruff>=0.6.0",
    "pre-commit>=3.8.0",
    "coverage[toml]>=7.6.0",
    "types-requests>=2.32.0",
]

[project.scripts]
todo = "todo.cli.main:app"

[project.urls]
Homepage = "https://github.com/yourusername/todo"
Repository = "https://github.com/yourusername/todo"
Documentation = "https://github.com/yourusername/todo/blob/main/README.md"
"Bug Tracker" = "https://github.com/yourusername/todo/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/todo"]
```

### Tool Configuration
```toml
[tool.ruff]
target-version = "py313"
line-length = 88
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "ARG", # flake8-unused-arguments
    "SIM", # flake8-simplify
    "TCH", # flake8-type-checking
]
ignore = [
    "E501",  # Line too long (handled by formatter)
    "B008",  # Do not perform function calls in argument defaults
    "B905",  # `zip()` without an explicit `strict=` parameter
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["ARG", "S101"]  # Allow unused args and asserts in tests

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

[[tool.mypy.overrides]]
module = "tests.*"
allow_untyped_defs = true

[tool.pytest.ini_options]
minversion = "8.0"
addopts = [
    "--strict-markers",
    "--strict-config",
    "--cov=src/todo",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-report=xml:coverage.xml",
    "--cov-fail-under=90",
]
testpaths = ["tests"]
filterwarnings = [
    "error",
    "ignore::UserWarning",
    "ignore::DeprecationWarning",
]

[tool.coverage.run]
source = ["src/todo"]
branch = true
omit = [
    "tests/*",
    "*/migrations/*",
    "*/__main__.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]
```

## Step 3: Initialize Development Environment

### Install Dependencies
```bash
# Install main dependencies
uv add typer[all] rich pydantic pydantic-ai duckdb openai anthropic python-dotenv

# Install development dependencies
uv add --dev pytest pytest-cov pytest-asyncio pytest-mock mypy ruff pre-commit coverage
```

### Setup Pre-commit Hooks
```bash
# Initialize pre-commit
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

## Step 4: Create Initial Files

### Environment Configuration (.env.example)
```env
# AI Provider Configuration
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Default AI Provider (openai or anthropic)
DEFAULT_AI_PROVIDER=openai

# Application Configuration
TODO_DATABASE_PATH=~/.local/share/todo/todos.db
TODO_CONFIG_PATH=~/.config/todo/config.toml
LOG_LEVEL=INFO

# Development Settings
PYTEST_CURRENT_TEST=true
```

### .gitignore
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Testing
.coverage
.pytest_cache/
htmlcov/
coverage.xml
*.cover
*.py,cover
.hypothesis/

# Type checking
.mypy_cache/
.dmypy.json
dmypy.json

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Application specific
*.db
*.sqlite
*.sqlite3
config.toml
logs/

# OS
.DS_Store
Thumbs.db
```

### Basic Package Structure
```bash
# Create empty __init__.py files
touch src/todo/__init__.py
touch src/todo/ai/__init__.py
touch src/todo/cli/__init__.py
touch src/todo/core/__init__.py
touch src/todo/db/__init__.py
touch tests/__init__.py
```

## Step 5: Verification Steps

### Verify Setup
```bash
# Check uv environment
uv run python --version
uv run python -c "import typer, rich, pydantic; print('Dependencies imported successfully')"

# Run initial linting
uv run ruff check .
uv run mypy src/

# Run initial tests (will be empty initially)
uv run pytest

# Verify pre-commit hooks
uv run pre-commit run --all-files
```

### Create Basic CLI Entry Point
```python
# src/todo/cli/main.py
"""Main CLI application entry point."""

import typer
from rich.console import Console

console = Console()
app = typer.Typer(
    name="todo",
    help="AI-powered terminal todo application for developers",
    add_completion=False,
)

@app.command()
def version() -> None:
    """Show application version."""
    console.print("todo version 0.1.0")

if __name__ == "__main__":
    app()
```

### Test Installation
```bash
# Install in development mode
uv pip install -e .

# Test CLI command
todo version
```

## Step 6: Success Criteria

- [ ] uv project initialized with Python 3.13
- [ ] All dependencies installed correctly
- [ ] pyproject.toml configured with all tools
- [ ] Pre-commit hooks installed and passing
- [ ] Basic CLI entry point working
- [ ] Directory structure matches specification
- [ ] No linting or type checking errors
- [ ] Initial test suite running (even if empty)

## Next Steps
After completing this setup:
1. Move to `02-data-models.md` to define Pydantic models
2. All subsequent development should maintain the quality standards established here
3. Every commit should pass pre-commit hooks
4. Test coverage should remain above 90%

## Common Issues and Solutions

### uv Not Found
```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Python 3.13 Not Available
```bash
# Let uv install Python 3.13
uv python install 3.13
```

### Pre-commit Hook Failures
```bash
# Fix automatically where possible
uv run ruff check --fix .
uv run ruff format .

# Re-run hooks
uv run pre-commit run --all-files
```
