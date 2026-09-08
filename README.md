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

### 3. Configure AI Features (Optional)

The todo app works without AI features, but for the full experience, set up API keys:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys and preferences
# Required for AI features:
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional configuration:
TODO_DEFAULT_AI_PROVIDER=openai              # or "anthropic"
TODO_AI_CONFIDENCE_THRESHOLD=0.7             # Auto-apply threshold (0.0-1.0)
TODO_ENABLE_AI=true                          # Enable/disable AI features
TODO_OPENAI_MODEL=gpt-4o-mini                # OpenAI model to use
TODO_ANTHROPIC_MODEL=claude-3-haiku-20240307 # Anthropic model to use
```

**Getting API Keys:**

- **OpenAI**: Visit https://platform.openai.com/api-keys
- **Anthropic**: Visit https://console.anthropic.com/

**Without API Keys**: The app works perfectly for basic todo management. AI features will be gracefully disabled with helpful messages.

## Using the Todo App

### Basic Commands

```bash
# Show help and available commands
todo --help

# Show version
todo version

# Add a new task with AI enrichment
todo add "Buy groceries"
todo add "Fix authentication bug" --desc "Users can't log in"

# Add a task with specific AI provider
todo add "Optimize database queries" --provider anthropic

# Add a task without AI analysis
todo add "Simple task" --no-ai

# List your todos
todo list              # Show active tasks
todo list --all        # Show all tasks including completed
todo list --limit 20   # Show up to 20 tasks

# Complete a task
todo done 1            # Mark task 1 as complete
todo complete 2        # Alternative command

# Show detailed task information
todo show 1            # View task details and AI analysis

# Manually analyze a task with AI
todo enrich 1          # Use default provider
todo enrich 1 --provider openai  # Use specific provider

# Show database information
todo db                # Database status and migration info
```

### AI-Powered Features

The todo app automatically analyzes your tasks using OpenAI or Anthropic AI to provide:

- **Smart Categorization**: Automatically suggests categories for your tasks
- **Priority Assessment**: Determines task urgency based on content
- **Size Estimation**: Estimates task complexity (small/medium/large)
- **Duration Prediction**: Suggests how long tasks might take
- **Recurrence Detection**: Identifies potentially recurring tasks
- **Confidence Scoring**: Shows how confident the AI is in its suggestions

Example AI enrichment output:
```bash
$ todo add "Fix authentication bug in user service" --desc "Users can't log in"

✓ Added task: Fix authentication bug in user service
Task ID: 1

🤖 AI analyzing task...

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                           🤖 AI Suggestions                           ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Aspect    │ Suggestion    │ Confidence │
├───────────┼───────────────┼────────────┤
│ Category  │ Bug Fix       │ 92.0%      │
│ Priority  │ High          │ 89.0%      │
│ Size      │ Medium        │ 85.0%      │
│ Duration  │ 120min        │ 85.0%      │
└───────────┴───────────────┴────────────┘

Reasoning: This appears to be a critical bug affecting user access, requiring
investigation of authentication systems and potential database or session issues.

✓ High confidence suggestions applied automatically
```

### List View with AI Status

The list command shows your todos with AI enrichment status:

```bash
$ todo list

                            📋 Your Todos
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━┓
┃ ID ┃ Task                                            ┃ Status     ┃ Priority ┃ AI  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━┩
│ 1  │ Fix authentication bug in user service          │ ○ Pending  │ High     │ ✓   │
│ 2  │ Buy groceries for the weekend                   │ ○ Pending  │ Medium   │ ✓   │
│ 3  │ Write unit tests for payment processor          │ ○ Pending  │ Medium   │ ○   │
└────┴─────────────────────────────────────────────────┴────────────┴──────────┴─────┘
```

### Database Management

The app automatically manages its database schema:

```bash
$ todo db

                        💾 Database Status
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field         ┃ Value                                            ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Database Path │ /Users/you/.local/share/todo/todos.db            │
│ Schema Version│ 1                                                │
│ Initialized   │ ✓ Yes                                            │
│ Tables        │ 8                                                │
└───────────────┴──────────────────────────────────────────────────┘

Applied Migrations:
  • v1: Create initial schema with todos, categories, user stats, and AI tables
```

## Telegram Bot (add/list from your phone)

Long-polling bot, no public endpoint needed. It shells out to the local `todo`
CLI, so it sees the same DB as the terminal.

1. Create a bot with [@BotFather](https://t.me/BotFather), get the token.
2. Get your numeric Telegram user id from [@userinfobot](https://t.me/userinfobot).
3. Add to `.env` (or `~/.config/todo/config.toml`'s equivalent env vars):
   ```
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_ALLOWED_USER_ID=...
   ```
4. Run in the foreground to test: `todo telegram serve`
5. Send the bot any text to add it as a todo; `/list` shows active todos.

Only `TELEGRAM_ALLOWED_USER_ID` may talk to the bot — everyone else is ignored.

### Run as a background service

Two ways to keep it running, pick whichever fits the machine:

- **k3s** (e.g. the mac mini, which already runs k3s) — see
  `k3s/telegram-bot/README.md`. Runs as a Deployment, sharing the same
  DuckDB as the terminal `todo` on that machine via a hostPath mount.
- **launchd** (any other Mac) — see below.

#### macOS launchd

Copy `launchd/com.silverbeer.todo-telegram-bot.plist` to
`~/Library/LaunchAgents/`, edit the `ProgramArguments` path to your `todo`
binary (`which todo`) and the `EnvironmentVariables` token/id, then:

```bash
launchctl load ~/Library/LaunchAgents/com.silverbeer.todo-telegram-bot.plist
```

Logs go to `~/Library/Logs/todo-telegram-bot.log`.

## Current Implementation Status

### ✅ Fully Implemented Features

- **Core Todo Management**: Add, list, complete, and view tasks
- **AI Enrichment**: Complete OpenAI and Anthropic integration
- **Rich Terminal UI**: Beautiful tables, colors, and formatting
- **Database Layer**: Full DuckDB integration with migrations
- **Configuration System**: Environment variables with `.env` support
- **Testing Infrastructure**: 71.67% coverage with E2E testing
- **Code Quality**: Pre-commit hooks, linting, type checking

### 🚧 Planned Features (Future Releases)

- **Gamification System**: Points, levels, streaks, and achievements
- **Natural Language Dates**: "due tomorrow", "next Friday" parsing
- **Export/Import**: JSON, CSV export capabilities
- **Calendar Integration**: Sync with Google Calendar, Outlook
- **Team Features**: Shared todo lists and collaboration
- **Web Dashboard**: Browser-based visualization and management
- **Mobile App**: Companion mobile application

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

### Core Application
- **Python 3.13** - Latest Python with performance improvements
- **uv** - Fast Python package manager (replacement for pip + virtualenv)
- **Typer** - Modern CLI framework with excellent developer experience
- **Rich** - Beautiful terminal formatting, tables, and colors
- **Pydantic** - Data validation and serialization using Python type hints
- **DuckDB** - Fast embedded analytics database (like SQLite but optimized)

### AI Integration
- **PydanticAI** - Type-safe AI framework with structured outputs
- **OpenAI API** - GPT models for task analysis and enrichment
- **Anthropic API** - Claude models as alternative/fallback provider
- **python-dotenv** - Environment variable management for API keys

### Development Tools
- **Ruff** - Extremely fast Python linter and formatter (replaces Black, isort, flake8)
- **MyPy** - Static type checker for Python with strict type safety
- **Pytest** - Testing framework with fixtures and parametrization
- **pytest-cov** - Code coverage measurement and reporting
- **Pre-commit** - Git hooks for automated code quality checks

### Testing & Quality
- **71.67% Test Coverage** - Comprehensive unit, integration, and E2E tests
- **Isolated Test Databases** - Each test uses its own temporary database
- **Mocked AI Responses** - Consistent testing without API dependencies
- **Pre-commit Hooks** - Automatic linting, formatting, and validation

## Project Structure

```
todo/
├── src/todo/              # Main application code
│   ├── ai/                # AI enrichment system
│   │   ├── enrichment_service.py  # Main AI service orchestrator
│   │   ├── providers.py           # OpenAI/Anthropic provider abstractions
│   │   ├── enrichment.py          # AI prompts and structured responses
│   │   ├── learning.py            # Feedback collection and learning
│   │   └── background.py          # Async background processing
│   ├── cli/               # Command-line interface
│   │   └── main.py        # Full CLI with Rich terminal formatting
│   ├── core/              # Core business logic
│   │   └── config.py      # Configuration management with .env support
│   ├── db/                # Database operations
│   │   ├── repository.py  # All repository implementations
│   │   ├── connection.py  # Database connection management
│   │   └── migrations.py  # Schema management and migrations
│   └── models.py          # Pydantic data models
├── tests/                 # Test files (71.67% coverage)
│   ├── unit/              # Unit tests for individual components
│   ├── integration/       # Integration tests for component interactions
│   ├── e2e/               # End-to-end CLI testing with isolated databases
│   ├── test_ai.py         # AI service and provider tests
│   ├── test_cli.py        # CLI command tests
│   ├── test_repository.py # Database repository tests
│   └── test_db_components.py # Database connection and migration tests
├── docs/                  # Implementation documentation and planning
├── pyproject.toml         # Project configuration (replaces setup.py, requirements.txt)
├── .pre-commit-config.yaml # Pre-commit hook configuration
├── .env.example           # Example environment configuration
└── README.md              # This file
```

## License

MIT License - see LICENSE file for details.
