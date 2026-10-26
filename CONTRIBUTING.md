# Contributing to Invader Tracker

First off, thank you for considering contributing to Invader Tracker! It's people like you that make this integration such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps which reproduce the problem** in as much detail as possible
- **Provide specific examples to demonstrate the steps**
- **Describe the behavior you observed after following the steps** and point out what exactly is the problem with that behavior
- **Explain which behavior you expected to see instead and why**
- **Include screenshots and animated GIFs if possible**
- **Include your Home Assistant version and integration version**

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

- **Use a clear and descriptive title**
- **Provide a step-by-step description of the suggested enhancement** in as much detail as possible
- **Provide specific examples to demonstrate the steps**
- **Describe the current behavior** and **the expected behavior**
- **Explain why this enhancement would be useful**

### Pull Requests

- Fill in the required template
- Follow the Python styleguides
- Include appropriate test cases
- End all files with a newline
- Avoid platform-dependent code

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Home Assistant development environment
- Git

### Local Development

1. **Fork the repository** on GitHub

2. **Clone your fork locally:**
   ```bash
   git clone https://github.com/YOUR-USERNAME/HA-Invader-Tracker.git
   cd HA-Invader-Tracker
   ```

3. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install development dependencies:**
   ```bash
   pip install homeassistant beautifulsoup4 aiohttp voluptuous
   pip install pytest pytest-asyncio pytest-cov
   pip install ruff==0.17.2 mypy==2.4.0
   ```

   > Ruff and MyPy are pinned to the versions CI uses (see `.github/workflows/ci.yml`).
   > Their rule sets change between releases, so an unpinned install can report
   > findings CI does not — or miss findings CI reports.

5. **Create a branch for your changes:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=custom_components.invader_tracker

# Run specific test file
pytest tests/test_models.py

# Run with verbose output
pytest -v
```

### Code Style

We use **Ruff** for linting and code formatting. Before committing:

Lint rules, formatting and the target Python version live in `pyproject.toml`.

```bash
# Check code style
ruff check custom_components/invader_tracker tests/

# Fix issues automatically
ruff check --fix custom_components/invader_tracker tests/

# Format (CI runs `ruff format --check`, so run this before committing)
ruff format custom_components/invader_tracker tests/
```

### Type Checking

We use **MyPy** for static type checking:

```bash
# Check types
mypy custom_components/invader_tracker/
```

### Project Structure

```
custom_components/invader_tracker/
├── __init__.py              # Integration setup
├── api/
│   ├── flash_invader.py    # Flash Invader API client
│   └── invader_spotter.py  # Invader-spotter.art scraper
├── binary_sensor.py         # Binary sensor entities
├── config_flow.py           # Configuration UI
├── const.py                 # Constants
├── coordinator.py           # Data update coordinators
├── exceptions.py            # Custom exceptions
├── models.py                # Data models
├── processor.py             # Data processing
├── sensor.py                # Sensor entities
└── store.py                 # State storage

tests/
├── conftest.py              # Pytest fixtures and mock data
├── test_models.py           # Model tests
└── test_device_removal.py   # Device removal tests
```

## Styleguides

### Python Styleguide

All Python code follows [PEP 8](https://www.python.org/dev/peps/pep-0008/) with Home Assistant conventions:

- Use type hints for all function parameters and returns
- Write docstrings for all classes and public methods
- Keep lines under 100 characters (Ruff configured)
- Use descriptive variable names
- Avoid `except:` or `except Exception:` without specific handling

**Example:**

```python
"""Module docstring."""
from __future__ import annotations

from typing import TYPE_CHECKING

import logging

if TYPE_CHECKING:
    from some_module import SomeType

_LOGGER = logging.getLogger(__name__)


class MyClass:
    """Class docstring with purpose."""

    def __init__(self, param1: str, param2: int) -> None:
        """Initialize the class.
        
        Args:
            param1: Description of param1
            param2: Description of param2
        """
        self._param1 = param1
        self._param2 = param2

    def my_method(self, value: str) -> bool:
        """Do something with the value.
        
        Args:
            value: The value to process
            
        Returns:
            True if successful, False otherwise
        """
        # Implementation
        return True
```

### Git Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

**Example:**

```
Fix invader status detection in news parser

- Handle both French and English status keywords
- Add unit tests for edge cases
- Fixes #123
```

### Documentation

- Keep documentation up-to-date with code changes
- Use clear and concise language
- Include code examples where helpful
- Update the CHANGELOG.md file

## Testing

All new features and bug fixes should include tests.

### Writing Tests

```python
import pytest
from custom_components.invader_tracker.models import Invader, InvaderStatus


class TestInvader:
    """Tests for Invader model."""

    def test_is_flashable_ok(self) -> None:
        """Test is_flashable for OK status."""
        invader = Invader(
            id="PA_001",
            city_code="PA",
            city_name="Paris",
            points=10,
            status=InvaderStatus.OK,
        )
        assert invader.is_flashable is True

    @pytest.mark.asyncio
    async def test_async_operation(self) -> None:
        """Test async operations."""
        # Your async test here
        pass
```

## Pull Request Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes and commit:**
   ```bash
   git add .
   git commit -m "Add my feature"
   ```

3. **Ensure tests pass:**
   ```bash
   pytest
   ruff check custom_components/invader_tracker tests/
   ruff format --check custom_components/invader_tracker tests/
   mypy custom_components/invader_tracker/
   ```

4. **Push to your fork:**
   ```bash
   git push origin feature/my-feature
   ```

5. **Open a Pull Request on GitHub:**
   - Provide a clear title and description
   - Reference any related issues with `Fixes #123`
   - Include screenshots if UI-related
   - Wait for review

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] CHANGELOG.md updated
- [ ] Commit messages are clear

## Additional Notes

### Issue and Pull Request Labels

Labels help organize and identify issues and pull requests:

- **bug** - Something isn't working
- **enhancement** - New feature or request
- **documentation** - Improvements or additions to documentation
- **good-first-issue** - Good for newcomers
- **help-wanted** - Extra attention is needed
- **question** - Further information is requested
- **wontfix** - This will not be worked on

## Questions?

Feel free to open an issue with the label `question` if you have any questions about the development process or codebase.

---

**Thank you for contributing! 🚀**
