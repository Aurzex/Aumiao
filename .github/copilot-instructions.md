# AI Coding Agent Instructions for Aumiao

## Project Overview
Aumiao is a comprehensive API collection and toolset for the CodeMao (编程猫) community, providing automation tools for community management, content moderation, development utilities, and AI integration. The project supports multiple work formats (KITTEN N, KITTEN, NEMO, CoCo) and includes both CLI and GUI interfaces.

## Architecture & Code Organization

### Core Structure
- **`aumiao/`**: Main package with lazy-loaded modules via `__getattr__`
  - **`api/`**: REST API clients for CodeMao services (auth, community, forum, library, etc.)
  - **`core/`**: Core business logic, data structures, and block programming support
  - **`utils/`**: Utilities for data management, plugins, decorators, and tools
- **`main.py`**: CLI entry point with numbered menu system
- **`mainWindows.py`**: GUI entry point (PyQt5-based)
- **`gui/`**: GUI components and image processing
- **`plugins/`**: Extensible plugin system with dynamic code modification

### Key Design Patterns
- **Lazy Module Loading**: All submodules use `__getattr__` for on-demand imports, ensuring Nuitka compilation compatibility
- **Singleton Pattern**: Core services like `Index()` use `@decorator.singleton`
- **Dynamic Code Modification**: Plugins can inject code via line numbers, pattern matching, or function rewriting
- **Configuration Management**: Separate `data.json` (auth/data) and `setting.json` (runtime settings)

## Development Workflow

### Build & Run
```bash
# Install with uv (recommended)
pip install uv
uv sync

# Run CLI
python -m aumiao  # or: aumiao

# Build executable with Nuitka
uv run python -m nuitka --onefile --enable-plugin=pyside6 main.py
```

### Testing & Quality
- **Linting**: `ruff check --fix --preview` (extensive rule set, line length 180)
- **Formatting**: `ruff format` (tabs, not spaces)
- **Type Checking**: `mypy` with strict settings
- **CI/CD**: Automated builds to executables for Windows/Linux/macOS

## Coding Conventions

### Naming Conventions (Critical)
Follow the detailed naming conventions in `document/Naming-Convention.md`:

**Function Prefixes**:
- `fetch_` - Network I/O operations (async-capable)
- `grab_` - Local data retrieval (no network)
- `create_` - New resource creation
- `update_` - Resource modification
- `delete_` - Resource removal
- `save_` - Data persistence (local or remote)
- `execute_` - Complex operations/workflows
- `validate_` - Input validation (returns errors or bool)
- `is_`/`has_`/`can_` - Boolean checks (question-like names)
- `convert_` - Data format transformation
- `format_` - Display formatting
- `parse_` - Raw data parsing

**Examples**:
```python
# Correct
def fetch_user_profile(user_id: int) -> dict:
def grab_local_config() -> dict:
def validate_email_format(email: str) -> list[str]:
def is_user_logged_in() -> bool:
def convert_json_to_xml(data: dict) -> str:
```

### ID System for Community Operations
When working with replies/comments, use the four-ID system:
- `business_id`: Top-level identifier (post/work ID)
- `target_id`: Direct reply target ID
- `parent_id`: Hierarchical position (0 for top-level)
- `reply_id`: Notification unique identifier

### Block Programming Support
The codebase extensively supports CodeMao's visual programming blocks:
- **Block Types**: Motion, Control, Events, Operators, etc.
- **Shadow Types**: Regular, Empty, Value, Replaceable
- **Opcodes**: Extensive enums for all block operations
- **Decompilation**: Support for KITTEN N, KITTEN, NEMO, CoCo formats

### Error Handling & Logging
- Use structured logging with configurable levels
- Handle network timeouts (30s default) and reconnections
- Validate all API responses before processing

## Key Files & Components

### Entry Points
- `main.py`: CLI menu system with 20+ operations
- `mainWindows.py`: PyQt5 GUI launcher
- `aumiao/__init__.py`: Dynamic module loader

### Core Services
- `core/base.py`: Fundamental types, enums, and configurations
- `core/services.py`: Business logic (reporting, uploading, etc.)
- `core/compile.py`: Work decompilation engine
- `core/process.py`: File processing pipeline

### API Clients
- `api/auth.py`: Authentication management
- `api/community.py`: Community operations
- `api/forum.py`: Forum interactions
- `api/work.py`: Work/project management

### Utilities
- `utils/data.py`: Configuration and cache management
- `utils/plugin.py`: Plugin system framework
- `utils/tool.py`: Common utilities

## Plugin Development
Plugins extend functionality through:
1. **Command Registration**: Add new CLI commands
2. **Code Injection**: Modify existing modules dynamically
3. **Event Handling**: Hook into load/unload events
4. **Configuration**: Schema-based settings

See `document/Plugin-Development.md` for implementation details.

## Dependencies & Environment
- **Python**: 3.12-3.14
- **Key Libraries**: httpx, cryptography, websocket-client
- **Build**: hatchling + Nuitka for executables
- **Package Manager**: uv (recommended) or pip
- **Platform**: Cross-platform (Windows/Linux/macOS)

## Common Patterns
- **Async Operations**: Use httpx for HTTP requests
- **Data Persistence**: JSON-based with backup/restore
- **Batch Processing**: Group operations for efficiency
- **Progress Tracking**: Console-based progress bars
- **Internationalization**: Support for Chinese interface

## Testing Approach
- **Unit Tests**: pytest with focus on API clients and utilities
- **Integration Tests**: End-to-end workflows
- **Manual Testing**: GUI and CLI interface validation

## Deployment
- **PyPI**: `pip install aumiao`
- **GitHub Releases**: Pre-compiled executables
- **CI/CD**: Automated multi-platform builds

Remember: This codebase serves the CodeMao educational platform community. All changes should prioritize user safety, content moderation best practices, and educational value.</content>
<parameter name="filePath">f:\Aumiao\.github\copilot-instructions.md