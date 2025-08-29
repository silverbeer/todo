# Quality Assurance - Implementation Plan

> **⚠️ IMPORTANT**: Review this document before implementation. As we develop the application, requirements may change and this documentation should be updated to reflect any modifications to the quality assurance processes and tooling.

## Overview
This document outlines comprehensive quality assurance processes for the todo application, including pre-commit hooks, code formatting, linting, type checking, security scanning, and CI/CD integration. The goal is to maintain consistent, high-quality code throughout development.

## Quality Standards

### Code Quality Metrics
- **Type Safety**: 100% mypy compliance with strict mode
- **Code Coverage**: Minimum 95%, target 98%
- **Lint Score**: Zero ruff violations in production code
- **Security**: Zero high/critical vulnerabilities from safety checks
- **Documentation**: All public APIs documented with type hints
- **Performance**: CLI commands respond within 200ms for typical usage

### Development Workflow
1. **Pre-commit hooks** catch issues before commit
2. **Automated formatting** ensures consistent style
3. **Static analysis** catches bugs early
4. **Test validation** maintains functionality
5. **Security scanning** prevents vulnerabilities
6. **Documentation validation** keeps docs current

## Pre-commit Hook Configuration

### .pre-commit-config.yaml
```yaml
# .pre-commit-config.yaml
repos:
  # Code formatting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.8
    hooks:
      # Linter
      - id: ruff
        name: ruff-lint
        description: "Run ruff linter"
        args: [--fix, --exit-non-zero-on-fix]
        types_or: [python, pyi]
      # Formatter
      - id: ruff-format
        name: ruff-format
        description: "Run ruff formatter"
        types_or: [python, pyi]

  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.1
    hooks:
      - id: mypy
        name: mypy
        description: "Run mypy type checker"
        additional_dependencies:
          - types-requests
          - types-python-dateutil
        args: [--strict, --show-error-codes]
        exclude: ^(tests/|docs/)

  # Security scanning
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        name: bandit
        description: "Run bandit security scanner"
        args: [-r, src/]
        exclude: ^tests/

  # Dependency security
  - repo: local
    hooks:
      - id: safety
        name: safety
        description: "Check dependencies for security vulnerabilities"
        entry: uv run safety check
        language: system
        files: ^(pyproject\.toml|uv\.lock)$
        pass_filenames: false

  # General pre-commit hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
        name: trailing-whitespace
        description: "Remove trailing whitespace"
      - id: end-of-file-fixer
        name: end-of-file-fixer
        description: "Ensure files end with newline"
      - id: check-yaml
        name: check-yaml
        description: "Validate YAML files"
      - id: check-toml
        name: check-toml
        description: "Validate TOML files"
      - id: check-json
        name: check-json
        description: "Validate JSON files"
      - id: check-merge-conflict
        name: check-merge-conflict
        description: "Check for merge conflict markers"
      - id: check-case-conflict
        name: check-case-conflict
        description: "Check for case conflicts"
      - id: mixed-line-ending
        name: mixed-line-ending
        description: "Ensure consistent line endings"
      - id: check-docstring-first
        name: check-docstring-first
        description: "Ensure docstrings come first"

  # Documentation
  - repo: https://github.com/econchick/interrogate
    rev: 1.7.0
    hooks:
      - id: interrogate
        name: interrogate
        description: "Check docstring coverage"
        args: [--config=pyproject.toml, src/todo]
        pass_filenames: false

  # Test validation
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        description: "Run tests before commit"
        entry: uv run pytest tests/ --maxfail=1 -q
        language: system
        pass_filenames: false
        stages: [commit]

  # Documentation generation check
  - repo: local
    hooks:
      - id: docs-check
        name: docs-check
        description: "Ensure documentation is up to date"
        entry: python scripts/check_docs.py
        language: system
        files: ^(src/|docs/)
        pass_filenames: false

# CI configuration
ci:
  autoupdate_schedule: weekly
  skip: [safety, pytest-check]  # Skip slow checks in CI
  autofix_commit_msg: |
    [pre-commit.ci] auto fixes from pre-commit hooks

    for more information, see https://pre-commit.ci
```

## Tool Configuration Details

### Ruff Configuration (Extended)
```toml
# pyproject.toml - Enhanced ruff configuration
[tool.ruff]
target-version = "py313"
line-length = 88
indent-width = 4
respect-gitignore = true
extend-exclude = [
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
]

[tool.ruff.lint]
# Enable comprehensive rule sets
select = [
    # Pyflakes
    "F",
    # pycodestyle errors
    "E",
    # pycodestyle warnings
    "W",
    # isort
    "I",
    # pep8-naming
    "N",
    # pydocstyle
    "D",
    # pyupgrade
    "UP",
    # flake8-annotations
    "ANN",
    # flake8-async
    "ASYNC",
    # flake8-bandit
    "S",
    # flake8-blind-except
    "BLE",
    # flake8-boolean-trap
    "FBT",
    # flake8-bugbear
    "B",
    # flake8-builtins
    "A",
    # flake8-comprehensions
    "C4",
    # flake8-datetimez
    "DTZ",
    # flake8-debugger
    "T10",
    # flake8-django
    "DJ",
    # flake8-errmsg
    "EM",
    # flake8-executable
    "EXE",
    # flake8-implicit-str-concat
    "ISC",
    # flake8-import-conventions
    "ICN",
    # flake8-logging-format
    "G",
    # flake8-no-pep420
    "INP",
    # flake8-pie
    "PIE",
    # flake8-print
    "T20",
    # flake8-pyi
    "PYI",
    # flake8-pytest-style
    "PT",
    # flake8-quotes
    "Q",
    # flake8-return
    "RET",
    # flake8-simplify
    "SIM",
    # flake8-tidy-imports
    "TID",
    # flake8-type-checking
    "TCH",
    # flake8-unused-arguments
    "ARG",
    # flake8-use-pathlib
    "PTH",
    # pandas-vet
    "PD",
    # pygrep-hooks
    "PGH",
    # Pylint
    "PL",
    # tryceratops
    "TRY",
    # flynt
    "FLY",
    # NumPy-specific rules
    "NPY",
    # Perflint
    "PERF",
    # Refurb
    "FURB",
    # flake8-logging
    "LOG",
    # Ruff-specific rules
    "RUF",
]

ignore = [
    # Allow non-abstract empty methods in abstract base classes
    "B027",
    # Allow boolean positional values in function calls
    "FBT003",
    # Ignore complexity
    "C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915",
    # Allow print statements (we use rich.console)
    "T201", "T203",
    # Allow assert statements in tests
    "S101",
    # Allow subprocess calls (needed for CLI)
    "S603", "S607",
    # Allow relative imports in __init__.py
    "TID252",
    # Allow string formatting in logging
    "G002", "G003", "G004",
    # Allow TODO comments
    "TD002", "TD003", "FIX002",
]

unfixable = [
    # Don't auto-remove unused imports
    "F401",
    # Don't auto-remove unused variables
    "F841",
]

[tool.ruff.lint.per-file-ignores]
# Tests can use magic values, assertions, and longer functions
"tests/**/*.py" = [
    "ANN", "ARG", "S101", "PLR2004", "PLR0913", "PLR0915",
    "D", "FBT", "SLF001"
]
# Migration files can have long functions and magic values
"*/migrations/*.py" = ["PLR0915", "PLR2004"]
# CLI files can have longer functions for command definitions
"src/todo/cli/*.py" = ["PLR0915", "PLR0913"]
# __init__.py files can have unused imports (for re-exports)
"__init__.py" = ["F401"]

[tool.ruff.lint.isort]
known-first-party = ["todo"]
required-imports = ["from __future__ import annotations"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
docstring-code-format = true
docstring-code-line-length = "dynamic"
```

### Mypy Configuration (Extended)
```toml
# pyproject.toml - Enhanced mypy configuration
[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
warn_missing_type_stubs = true
strict_equality = true
extra_checks = true

# Error formatting
show_error_codes = true
show_column_numbers = true
show_error_context = true
pretty = true
color_output = true
error_summary = true

# Import discovery
namespace_packages = true
explicit_package_bases = true
ignore_missing_imports = false

# Strictness settings
disallow_any_generics = true
disallow_any_unimported = true
disallow_any_expr = false  # Allow Any in some expressions
disallow_any_decorated = true
disallow_any_explicit = true
disallow_subclassing_any = true
disallow_untyped_calls = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
disallow_untyped_decorators = true
check_untyped_defs = true
implicit_optional = false
strict_optional = true

# Platform configuration
platform = "darwin"

# Per-module configuration
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
disallow_untyped_calls = false
disallow_incomplete_defs = false
check_untyped_defs = false
warn_return_any = false

[[tool.mypy.overrides]]
module = [
    "duckdb.*",
    "typer.*",
    "rich.*",
    "pydantic_ai.*",
]
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "todo.cli.*"
# CLI modules may have some untyped interactions
disallow_any_expr = false
warn_return_any = false
```

### Documentation Quality
```toml
# pyproject.toml - Documentation configuration
[tool.interrogate]
ignore-init-method = true
ignore-init-module = true
ignore-magic = true
ignore-semiprivate = false
ignore-private = false
ignore-property-decorators = false
ignore-module = true
ignore-nested-functions = false
ignore-nested-classes = true
ignore-setters = false
fail-under = 90
exclude = ["setup.py", "docs", "tests"]
ignore-regex = ["^get$", "^post$", "^put$", "^patch$", "^delete$"]
verbose = 0
quiet = false
whitelist-regex = []
color = true
omit-covered-files = false

# Generate badges
generate-badge = "."
badge-format = "svg"
```

## Security Configuration

### Bandit Configuration
```toml
# pyproject.toml - Security scanning configuration
[tool.bandit]
exclude_dirs = ["tests", "docs", ".venv", "build"]
skips = [
    "B101",  # Skip assert_used test
    "B601",  # Skip paramiko calls (we don't use paramiko)
]

# Security hardening targets
targets = ["src/todo"]

[tool.bandit.assert_used]
skips = ["*/tests/*", "*/*_test.py", "*/test_*.py"]
```

### Safety Configuration
```bash
# .safety-policy.json - Dependency vulnerability policy
{
  "security": {
    "ignore-cvss-severity-below": 7.0,
    "ignore-cvss-unknown-severity": false,
    "continue-on-vulnerability-error": false
  },
  "alert": {
    "ignore-vulnerabilities": [],
    "ignore-unpinned-requirements": false
  },
  "report": {
    "only-report": false,
    "output": {
      "format": "json",
      "file": "safety-report.json"
    }
  }
}
```

## Development Scripts

### Quality Check Script
```bash
#!/bin/bash
# scripts/quality.sh - Comprehensive quality check

set -e

echo "🔍 Running comprehensive quality checks..."

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Track overall success
OVERALL_SUCCESS=true

# 1. Code formatting check
print_status "Checking code formatting with ruff..."
if uv run ruff format --check src/ tests/; then
    print_success "Code formatting is correct"
else
    print_error "Code formatting issues found. Run 'uv run ruff format src/ tests/' to fix"
    OVERALL_SUCCESS=false
fi

# 2. Linting
print_status "Running linting with ruff..."
if uv run ruff check src/ tests/; then
    print_success "No linting issues found"
else
    print_error "Linting issues found. Run 'uv run ruff check --fix src/ tests/' to fix"
    OVERALL_SUCCESS=false
fi

# 3. Type checking
print_status "Running type checking with mypy..."
if uv run mypy src/; then
    print_success "Type checking passed"
else
    print_error "Type checking failed"
    OVERALL_SUCCESS=false
fi

# 4. Security scanning
print_status "Running security scan with bandit..."
if uv run bandit -r src/ -f json -o bandit-report.json; then
    print_success "Security scan passed"
else
    print_warning "Security issues found - check bandit-report.json"
    # Don't fail on security warnings, just warn
fi

# 5. Dependency security
print_status "Checking dependency security with safety..."
if uv run safety check --json --output safety-report.json; then
    print_success "Dependency security check passed"
else
    print_error "Vulnerable dependencies found - check safety-report.json"
    OVERALL_SUCCESS=false
fi

# 6. Test suite
print_status "Running test suite..."
if uv run pytest tests/ --cov=src/todo --cov-report=term-missing --cov-fail-under=95; then
    print_success "All tests passed with sufficient coverage"
else
    print_error "Tests failed or coverage insufficient"
    OVERALL_SUCCESS=false
fi

# 7. Documentation coverage
print_status "Checking documentation coverage..."
if uv run interrogate src/todo --fail-under=90; then
    print_success "Documentation coverage is sufficient"
else
    print_error "Documentation coverage is insufficient"
    OVERALL_SUCCESS=false
fi

# 8. Import sorting check
print_status "Checking import sorting..."
if uv run ruff check --select I src/ tests/; then
    print_success "Import sorting is correct"
else
    print_error "Import sorting issues found"
    OVERALL_SUCCESS=false
fi

# Final status
echo ""
if [ "$OVERALL_SUCCESS" = true ]; then
    print_success "🎉 All quality checks passed!"
    exit 0
else
    print_error "❌ Some quality checks failed. Please fix the issues above."
    exit 1
fi
```

### Fix Script
```bash
#!/bin/bash
# scripts/fix.sh - Auto-fix common issues

set -e

echo "🔧 Auto-fixing common code quality issues..."

# Auto-format code
echo "▶ Formatting code with ruff..."
uv run ruff format src/ tests/

# Auto-fix linting issues
echo "▶ Fixing linting issues with ruff..."
uv run ruff check --fix src/ tests/

# Sort imports
echo "▶ Sorting imports..."
uv run ruff check --select I --fix src/ tests/

# Remove unused imports (careful with this)
echo "▶ Removing unused imports..."
uv run ruff check --select F401 --fix src/

echo "✓ Auto-fixes completed. Please review changes and run quality checks."
```

### Performance Monitoring Script
```python
# scripts/performance_monitor.py - Monitor performance regressions
import time
import subprocess
import statistics
from typing import List, Dict, Any

def run_command_timing(command: List[str], iterations: int = 5) -> Dict[str, Any]:
    """Run a command multiple times and measure performance."""
    times = []

    for _ in range(iterations):
        start = time.time()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        end = time.time()
        times.append(end - start)

    return {
        'command': ' '.join(command),
        'times': times,
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times)
    }

def main():
    """Monitor key performance metrics."""
    print("🏃 Performance monitoring...")

    # Commands to monitor
    commands = [
        ['uv', 'run', 'todo', 'add', 'Performance test task', '--no-ai'],
        ['uv', 'run', 'todo', 'list', '--limit', '20'],
        ['uv', 'run', 'todo', 'stats'],
        ['uv', 'run', 'pytest', 'tests/unit/', '-q'],
        ['uv', 'run', 'ruff', 'check', 'src/'],
        ['uv', 'run', 'mypy', 'src/todo/models.py']
    ]

    results = []
    for command in commands:
        try:
            result = run_command_timing(command)
            results.append(result)
            print(f"✓ {result['command']}: {result['mean']:.3f}s (±{result['stdev']:.3f})")
        except subprocess.CalledProcessError as e:
            print(f"✗ {' '.join(command)}: Failed with code {e.returncode}")

    # Check for performance regressions
    performance_targets = {
        'todo add': 0.5,    # 500ms for todo creation
        'todo list': 0.2,   # 200ms for listing todos
        'todo stats': 0.3,  # 300ms for stats
        'pytest tests/unit/': 10.0,  # 10s for unit tests
        'ruff check': 2.0,  # 2s for linting
        'mypy': 5.0         # 5s for type checking
    }

    print("\n🎯 Performance targets:")
    for result in results:
        command_key = next(
            (key for key in performance_targets.keys() if key in result['command']),
            None
        )
        if command_key:
            target = performance_targets[command_key]
            status = "✓" if result['mean'] <= target else "⚠"
            print(f"{status} {command_key}: {result['mean']:.3f}s (target: {target}s)")

if __name__ == "__main__":
    main()
```

## CI/CD Configuration

### GitHub Actions Workflow
```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  UV_CACHE_DIR: /tmp/.uv-cache

jobs:
  quality:
    name: Code Quality
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.13"]

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up uv
      uses: astral-sh/setup-uv@v3
      with:
        enable-cache: true
        cache-dependency-glob: "uv.lock"

    - name: Set up Python
      run: uv python install ${{ matrix.python-version }}

    - name: Install dependencies
      run: uv sync --all-extras --dev

    - name: Cache pre-commit
      uses: actions/cache@v4
      with:
        path: ~/.cache/pre-commit
        key: pre-commit-${{ runner.os }}-${{ hashFiles('.pre-commit-config.yaml') }}

    - name: Run pre-commit
      run: uv run pre-commit run --all-files

    - name: Run tests with coverage
      run: |
        uv run pytest tests/ \
          --cov=src/todo \
          --cov-report=xml \
          --cov-report=term-missing \
          --cov-fail-under=95 \
          --junit-xml=pytest.xml

    - name: Upload coverage reports
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella

    - name: Performance monitoring
      run: uv run python scripts/performance_monitor.py

    - name: Security scan
      run: |
        uv run bandit -r src/ -f json -o bandit-report.json
        uv run safety check --json --output safety-report.json

    - name: Upload security reports
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: security-reports
        path: |
          bandit-report.json
          safety-report.json

  build:
    name: Build and Install
    runs-on: ubuntu-latest
    needs: quality

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up uv
      uses: astral-sh/setup-uv@v3

    - name: Build package
      run: uv build

    - name: Test installation
      run: |
        uv tool install --from dist/*.whl todo
        todo --version

    - name: Upload build artifacts
      uses: actions/upload-artifact@v4
      with:
        name: build-artifacts
        path: dist/

  test-matrix:
    name: Test Matrix
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.13"]

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up uv
      uses: astral-sh/setup-uv@v3

    - name: Set up Python
      run: uv python install ${{ matrix.python-version }}

    - name: Install dependencies
      run: uv sync --dev

    - name: Run core tests
      run: uv run pytest tests/unit/ tests/integration/ -v

  dependency-review:
    name: Dependency Review
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Dependency Review
      uses: actions/dependency-review-action@v4
      with:
        fail-on-severity: moderate
```

## Documentation Quality Assurance

### Documentation Update Script
```python
# scripts/check_docs.py - Ensure documentation is current
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Set

def check_documentation_currency() -> bool:
    """Check if documentation is up to date with code changes."""
    issues = []

    # Check if CLAUDE.md mentions the important warning
    claude_md = Path("CLAUDE.md")
    if claude_md.exists():
        content = claude_md.read_text()
        if "Review this document before implementation" not in content:
            issues.append("CLAUDE.md missing implementation review warning")

    # Check if all implementation docs have the warning
    docs_dir = Path("docs")
    for doc_file in docs_dir.glob("*.md"):
        content = doc_file.read_text()
        if "Review this document before implementation" not in content:
            issues.append(f"{doc_file} missing implementation review warning")

    # Check for TODO markers in docs
    for doc_file in docs_dir.glob("*.md"):
        content = doc_file.read_text()
        if "TODO:" in content or "FIXME:" in content:
            issues.append(f"{doc_file} contains unresolved TODO/FIXME items")

    # Check that code examples in docs are syntactically valid
    for doc_file in docs_dir.glob("*.md"):
        content = doc_file.read_text()
        python_blocks = re.findall(r'```python\n(.*?)\n```', content, re.DOTALL)
        for i, block in enumerate(python_blocks):
            try:
                compile(block, f"{doc_file}:block{i}", "exec")
            except SyntaxError as e:
                issues.append(f"{doc_file} has invalid Python syntax in code block {i}: {e}")

    if issues:
        print("❌ Documentation issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✓ Documentation quality checks passed")
        return True

if __name__ == "__main__":
    success = check_documentation_currency()
    sys.exit(0 if success else 1)
```

## Quality Metrics Dashboard

### Metrics Collection Script
```python
# scripts/collect_metrics.py - Collect quality metrics
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

def collect_quality_metrics() -> Dict[str, Any]:
    """Collect comprehensive quality metrics."""
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip(),
    }

    # Code coverage
    try:
        coverage_result = subprocess.run(
            ['uv', 'run', 'coverage', 'report', '--format=json'],
            capture_output=True, text=True, check=True
        )
        coverage_data = json.loads(coverage_result.stdout)
        metrics['coverage'] = {
            'percent_covered': coverage_data['totals']['percent_covered'],
            'lines_covered': coverage_data['totals']['covered_lines'],
            'lines_total': coverage_data['totals']['num_statements']
        }
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        metrics['coverage'] = {'error': 'Failed to collect coverage data'}

    # Type checking
    try:
        mypy_result = subprocess.run(
            ['uv', 'run', 'mypy', 'src/', '--json-report', 'mypy-report.json'],
            capture_output=True, text=True
        )
        with open('mypy-report.json') as f:
            mypy_data = json.load(f)

        metrics['type_checking'] = {
            'error_count': len(mypy_data.get('errors', [])),
            'files_checked': len(mypy_data.get('files', [])),
            'success': mypy_result.returncode == 0
        }
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        metrics['type_checking'] = {'error': 'Failed to collect mypy data'}

    # Linting
    try:
        ruff_result = subprocess.run(
            ['uv', 'run', 'ruff', 'check', 'src/', '--format=json'],
            capture_output=True, text=True
        )
        if ruff_result.stdout:
            ruff_data = json.loads(ruff_result.stdout)
            metrics['linting'] = {
                'violations': len(ruff_data),
                'clean': len(ruff_data) == 0
            }
        else:
            metrics['linting'] = {'violations': 0, 'clean': True}
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        metrics['linting'] = {'error': 'Failed to collect ruff data'}

    # Code complexity (lines of code)
    src_files = list(Path('src').rglob('*.py'))
    total_lines = 0
    for file_path in src_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            total_lines += len(f.readlines())

    metrics['complexity'] = {
        'total_files': len(src_files),
        'total_lines': total_lines,
        'avg_lines_per_file': total_lines / len(src_files) if src_files else 0
    }

    # Test metrics
    try:
        test_result = subprocess.run(
            ['uv', 'run', 'pytest', 'tests/', '--collect-only', '-q'],
            capture_output=True, text=True, check=True
        )
        # Parse test count from output
        lines = test_result.stdout.split('\n')
        test_count = 0
        for line in lines:
            if ' collected' in line:
                test_count = int(line.split()[0])
                break

        metrics['tests'] = {
            'total_tests': test_count,
            'test_to_code_ratio': test_count / total_lines if total_lines > 0 else 0
        }
    except (subprocess.CalledProcessError, ValueError):
        metrics['tests'] = {'error': 'Failed to collect test data'}

    # Security metrics
    try:
        bandit_result = subprocess.run(
            ['uv', 'run', 'bandit', '-r', 'src/', '-f', 'json'],
            capture_output=True, text=True
        )
        if bandit_result.stdout:
            bandit_data = json.loads(bandit_result.stdout)
            metrics['security'] = {
                'issues_found': len(bandit_data.get('results', [])),
                'high_severity': len([r for r in bandit_data.get('results', [])
                                    if r.get('issue_severity') == 'HIGH']),
                'medium_severity': len([r for r in bandit_data.get('results', [])
                                      if r.get('issue_severity') == 'MEDIUM'])
            }
        else:
            metrics['security'] = {'issues_found': 0, 'high_severity': 0, 'medium_severity': 0}
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        metrics['security'] = {'error': 'Failed to collect security data'}

    return metrics

def save_metrics(metrics: Dict[str, Any]) -> None:
    """Save metrics to file."""
    metrics_dir = Path('metrics')
    metrics_dir.mkdir(exist_ok=True)

    # Save latest metrics
    with open(metrics_dir / 'latest.json', 'w') as f:
        json.dump(metrics, f, indent=2)

    # Save timestamped metrics
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    with open(metrics_dir / f'metrics_{timestamp}.json', 'w') as f:
        json.dump(metrics, f, indent=2)

def main():
    """Main function to collect and save metrics."""
    print("📊 Collecting quality metrics...")
    metrics = collect_quality_metrics()
    save_metrics(metrics)

    print("✓ Metrics collected:")
    print(f"  Coverage: {metrics.get('coverage', {}).get('percent_covered', 'N/A')}%")
    print(f"  Type checking: {'✓' if metrics.get('type_checking', {}).get('success') else '✗'}")
    print(f"  Linting: {'✓' if metrics.get('linting', {}).get('clean') else '✗'}")
    print(f"  Tests: {metrics.get('tests', {}).get('total_tests', 'N/A')}")
    print(f"  Security issues: {metrics.get('security', {}).get('issues_found', 'N/A')}")

if __name__ == "__main__":
    main()
```

## Implementation Steps

### Step 1: Pre-commit Setup
1. Install pre-commit: `uv add --dev pre-commit`
2. Create `.pre-commit-config.yaml` with comprehensive hooks
3. Install hooks: `uv run pre-commit install`
4. Test on all files: `uv run pre-commit run --all-files`

### Step 2: Tool Configuration
1. Enhance ruff configuration in pyproject.toml
2. Set up strict mypy configuration
3. Configure bandit for security scanning
4. Set up safety for dependency checking

### Step 3: Quality Scripts
1. Create `scripts/quality.sh` for comprehensive checks
2. Create `scripts/fix.sh` for auto-fixes
3. Create performance monitoring script
4. Set up documentation validation

### Step 4: CI/CD Integration
1. Create GitHub Actions workflow
2. Set up codecov integration
3. Configure dependency review
4. Add performance regression detection

### Step 5: Metrics and Monitoring
1. Create metrics collection system
2. Set up quality dashboard
3. Configure alerts for quality regressions
4. Document quality standards and processes

## Success Criteria
- [ ] Pre-commit hooks prevent all quality issues
- [ ] 100% mypy compliance with strict mode
- [ ] 95%+ test coverage maintained
- [ ] Zero high-severity security vulnerabilities
- [ ] CI/CD pipeline runs in under 10 minutes
- [ ] All documentation current and validated
- [ ] Performance regressions caught automatically
- [ ] Quality metrics tracked over time
- [ ] Developer experience remains smooth and fast
