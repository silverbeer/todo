# Todo - AI-Powered Terminal Task Manager

An intelligent, terminal-based todo application designed for developers who live in the command line. Features AI-powered task enrichment, gamification, and beautiful terminal UI.

## Features

- **Simple CLI**: Dead simple workflow: `todo add "task"` -> `todo done <id>`
- **AI Enrichment**: Automatic categorization, sizing, and recurrence detection
- **Gamification**: Points, levels, streaks, and achievements to stay motivated
- **Beautiful UI**: Rich terminal formatting with colors, tables, and progress bars
- **Developer-Friendly**: Natural language date parsing, JSON output, auto-completion

## Prerequisites

- **Python 3.13+** (will be installed automatically by uv)
- **uv** - Modern Python package manager

### Installing uv

If you don't have `uv` installed:

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.sh | iex"

# Alternative: via pip
pip install uv
```

## Setup and Installation

### 1. Clone and Setup the Project

```bash
# Clone the repository
git clone <your-repo-url>
cd todo

# Install Python 3.13 and all dependencies
uv sync --dev

# This command will:
# - Install Python 3.13 automatically if not present
# - Create a virtual environment
# - Install all project dependencies and dev tools
```

### 2. Install Development Tools (Pre-commit Hooks)

```bash
# Install pre-commit hooks (runs quality checks before each commit)
uv run pre-commit install

# Test that hooks work
uv run pre-commit run --all-files
```

### 3. Configure API Keys (Optional)

For AI features, copy the example environment file and add your API keys:

```bash
cp .env.example .env
# Edit .env with your OpenAI/Anthropic API keys
```

## Using the Todo App

### Basic Commands

```bash
# Show help and available commands
todo --help

# Show version
todo version

# Add a new task (basic implementation for now)
todo add "Buy groceries"
todo add "Fix the leaky faucet"

# Future commands (not implemented yet):
todo list              # Show all tasks
todo done 1           # Mark task 1 as complete
todo stats            # Show productivity stats
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests with coverage report
uv run pytest --cov-report=html
# Then open htmlcov/index.html in your browser
```

## Development Tools Guide

This project uses modern Python tools for code quality. Here's how to use each one:

### 1. Ruff - Lightning-fast Linter and Formatter

**Ruff** replaces multiple tools (black, isort, flake8, etc.) with a single, fast tool.

```bash
# Check for linting issues (style, imports, complexity, etc.)
uv run ruff check .

# Auto-fix issues where possible
uv run ruff check --fix .

# Format code (similar to Black)
uv run ruff format .

# Check specific files
uv run ruff check src/todo/cli/main.py
```

**Common Ruff fixes:**
- Removes unused imports
- Sorts imports
- Fixes line length issues
- Enforces consistent quotes
- Removes trailing whitespace

### 2. MyPy - Static Type Checking

**MyPy** checks that your type hints are correct and catches type-related bugs.

```bash
# Type-check the entire src/ directory
uv run mypy src/

# Check specific files
uv run mypy src/todo/cli/main.py

# Get detailed error information
uv run mypy src/ --show-error-codes

# Check if types are missing
uv run mypy src/ --warn-missing-type-stubs
```

**Common MyPy errors:**
- Missing type annotations
- Incompatible types
- Unreachable code
- Missing return statements

### 3. Pytest - Testing Framework

**Pytest** runs your tests and measures code coverage.

```bash
# Run all tests
uv run pytest

# Run tests with coverage (shows which code is tested)
uv run pytest --cov=src/todo

# Run only tests that match a pattern
uv run pytest -k "test_basic"

# Run tests in a specific directory
uv run pytest tests/unit/

# Show detailed output for failing tests
uv run pytest -v --tb=short
```

### 4. Pre-commit Hooks - Automated Quality Checks

**Pre-commit** automatically runs quality checks before you commit code.

```bash
# Install hooks (one-time setup)
uv run pre-commit install

# Run all hooks manually on all files
uv run pre-commit run --all-files

# Run hooks on staged files only
uv run pre-commit run

# Update hook versions
uv run pre-commit autoupdate

# Skip hooks for a single commit (not recommended)
git commit -m "message" --no-verify
```

**What the hooks do:**
- **ruff-lint**: Checks code style and complexity
- **ruff-format**: Auto-formats code
- **trailing-whitespace**: Removes extra spaces at line ends
- **end-of-file-fixer**: Ensures files end with a newline
- **check-yaml/toml**: Validates configuration files
- **check-merge-conflict**: Prevents committing merge conflicts

### 5. Coverage - Test Coverage Analysis

**Coverage** shows how much of your code is tested.

```bash
# Run tests with coverage
uv run pytest --cov=src/todo

# Generate HTML coverage report
uv run pytest --cov=src/todo --cov-report=html
# Then open htmlcov/index.html

# Generate terminal coverage report
uv run pytest --cov=src/todo --cov-report=term-missing

# Check coverage without running tests
uv run coverage report
uv run coverage html
```

## Complete Development Workflow

Here's the recommended workflow when developing:

### 1. Making Changes

```bash
# Make your code changes
# Add/edit files in src/todo/

# Format code
uv run ruff format .

# Check for issues and auto-fix
uv run ruff check --fix .

# Run type checking
uv run mypy src/

# Run tests
uv run pytest
```

### 2. Before Committing

```bash
# Run all quality checks
uv run pre-commit run --all-files

# If everything passes, commit
git add .
git commit -m "Your commit message"

# The pre-commit hooks will run automatically
# If they fail, fix the issues and commit again
```

### 3. Quick Quality Check Script

Create this simple script to check everything at once:

```bash
# Run this command to check everything
echo "🔍 Formatting..." && uv run ruff format . && \
echo "🔍 Linting..." && uv run ruff check . && \
echo "🔍 Type checking..." && uv run mypy src/ && \
echo "🔍 Testing..." && uv run pytest && \
echo "✅ All checks passed!"
```

## Troubleshooting

### Common Issues

**1. "command not found: uv"**
```bash
# Install uv first
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart your terminal
```

**2. "Python 3.13 not found"**
```bash
# Let uv install it for you
uv python install 3.13
```

**3. Pre-commit hooks failing**
```bash
# Let the hooks auto-fix issues
uv run pre-commit run --all-files
# Then commit again
```

**4. Import errors when running todo**
```bash
# Make sure you're using uv run
uv run todo --help
# Not just: todo --help
```

**5. Tests failing with coverage errors**
```bash
# Lower coverage requirement temporarily
uv run pytest --cov-fail-under=0
```

### Getting Help

- **uv help**: `uv --help` or visit https://docs.astral.sh/uv/
- **ruff help**: `uv run ruff --help` or visit https://docs.astral.sh/ruff/
- **mypy help**: `uv run mypy --help` or visit https://mypy.readthedocs.io/
- **pytest help**: `uv run pytest --help` or visit https://docs.pytest.org/

## Technology Stack Details

- **Python 3.13** - Latest Python with performance improvements
- **uv** - Fast Python package manager (replacement for pip + virtualenv)
- **Typer** - Modern CLI framework with excellent developer experience
- **Rich** - Beautiful terminal formatting and colors
- **Pydantic** - Data validation using Python type hints
- **PydanticAI** - Type-safe AI framework
- **DuckDB** - Fast embedded database (like SQLite but for analytics)
- **Ruff** - Extremely fast Python linter and formatter
- **MyPy** - Static type checker for Python
- **Pytest** - Testing framework with fixtures and parametrization
- **Pre-commit** - Git hooks for code quality

## Project Structure

```
todo/
├── src/todo/              # Main application code
│   ├── ai/                # AI enrichment modules
│   ├── cli/               # Command-line interface
│   ├── core/              # Core business logic
│   └── db/                # Database operations
├── tests/                 # Test files
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── e2e/               # End-to-end tests
├── docs/                  # Implementation documentation
├── pyproject.toml         # Project configuration (replaces setup.py, requirements.txt)
├── .pre-commit-config.yaml # Pre-commit hook configuration
└── README.md              # This file
```

## License

MIT License - see LICENSE file for details.
