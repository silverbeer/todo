# Terminal Todo App with AI Enrichment

## Project Overview
A modern Python terminal-based todo application designed for developers who live in the command line. This app combines simplicity with AI-powered task enrichment and gamification to make task management both efficient and engaging.

## Core Features
- **Simple CLI Interface**: Dead simple task creation and completion
- **AI Enrichment**: Automatic categorization, size estimation, and recurrence detection
- **Gamification**: Points, streaks, achievements, and daily/weekly/monthly goals
- **Multi-LLM Support**: OpenAI and Claude API integration
- **Learning System**: AI improves from user feedback and overrides
- **Beautiful Terminal UI**: Rich formatting with tables, colors, and progress indicators

## Technology Stack

### Core Technologies
- **Python 3.13** - Latest Python version
- **uv** - Modern Python package and project management (NO pip or requirements.txt)
- **pyproject.toml** - Modern Python project configuration

### Dependencies
- **Typer** - Modern CLI framework with excellent developer experience
- **Rich** - Beautiful terminal formatting, tables, progress bars, colors
- **Pydantic** - Data validation and serialization using Python type hints
- **PydanticAI** - Modern AI framework with type safety and structured outputs
- **DuckDB** - Lightweight, embedded SQL database perfect for CLI apps

### Development Tools
- **pytest** - Testing framework with fixtures and parametrized tests
- **pytest-cov** - Code coverage measurement
- **pre-commit** - Git hooks for code quality
- **ruff** - Fast Python linter and formatter
- **mypy** - Static type checking
- **black** - Code formatting (integrated with ruff)

### AI Integration
- **OpenAI API** - GPT models for task enrichment
- **Anthropic Claude API** - Claude models as alternative/fallback
- **Provider switching** - Configurable LLM provider selection

## Project Structure
```
todo/
├── pyproject.toml              # Project config, dependencies, tool settings
├── uv.lock                     # Dependency lock file (auto-generated)
├── .pre-commit-config.yaml     # Pre-commit hooks configuration
├── CLAUDE.md                   # This file - project documentation
├── docs/                       # Implementation planning documentation
│   ├── 01-project-setup.md
│   ├── 02-data-models.md
│   ├── 03-database-layer.md
│   ├── 04-ai-enrichment.md
│   ├── 05-cli-interface.md
│   ├── 06-gamification.md
│   ├── 07-testing-strategy.md
│   └── 08-quality-assurance.md
├── src/
│   └── todo/
│       ├── __init__.py
│       ├── models.py           # Pydantic data models
│       ├── database.py         # DuckDB operations and schema
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── enrichment.py   # PydanticAI task enrichment
│       │   ├── providers.py    # OpenAI/Claude provider abstraction
│       │   └── learning.py     # AI learning from user feedback
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py         # Main Typer app and commands
│       │   ├── display.py      # Rich formatting and display logic
│       │   └── utils.py        # CLI utility functions
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py       # Settings, API keys, user preferences
│       │   ├── scoring.py      # Gamification points and achievements
│       │   └── recurrence.py   # Recurring task management
│       └── db/
│           ├── __init__.py
│           ├── schema.sql      # Database schema definitions
│           └── migrations.py   # Schema migration utilities
└── tests/
    ├── __init__.py
    ├── conftest.py             # Pytest configuration and fixtures
    ├── unit/                   # Unit tests for individual components
    ├── integration/            # Integration tests for component interactions
    └── e2e/                    # End-to-end CLI testing

```

## Development Principles
- **Test-Driven Development**: Write tests first, ensure 100% code coverage
- **Type Safety**: Full mypy compliance with strict type checking
- **Code Quality**: Pre-commit hooks prevent bad code from being committed
- **Modern Python**: Use latest Python 3.13 features and best practices
- **No Legacy Tools**: uv instead of pip, pyproject.toml instead of setup.py
- **Documentation**: Every feature documented with examples and rationale

## Quality Standards
- **Zero Failing Tests**: All tests must pass before any commit
- **High Code Coverage**: Target 95%+ test coverage
- **Type Safety**: 100% mypy compliance
- **Code Style**: Consistent formatting with ruff/black
- **Pre-commit Hooks**: Automatic linting, formatting, and testing
- **Documentation**: Clear docstrings and type hints for all public APIs

## User Experience Goals
- **Simplicity**: Core workflow should be `todo add "task"` → `todo done <id>`
- **Speed**: Commands should execute in milliseconds
- **Beauty**: Rich terminal output that's a pleasure to use
- **Intelligence**: AI that gets smarter over time without being intrusive
- **Motivation**: Gamification that encourages consistent task completion

## Configuration Management
- **Environment Variables**: API keys and sensitive configuration
- **Config File**: User preferences stored in `~/.config/todo/config.toml`
- **Database Location**: `~/.local/share/todo/todos.db` (follows XDG standards)
- **Cross-platform**: Works on macOS, Linux, and Windows

## Future Enhancements (Post-MVP)
- Web dashboard for visualization
- Team/shared todo lists
- Integration with calendar applications
- Mobile companion app
- Advanced AI features (deadline prediction, task prioritization)
- Export/import functionality
- Plugin system for custom enrichments

---
*This documentation is maintained as the project evolves. Last updated: 2025-08-29*
