# Test, Fix, and Commit Workflow

You are running the `/testit` command. Follow these steps to analyze changed files, create/run tests, fix errors, and commit.

## Step 1: Identify Changed Files

First, identify what files have been modified or added:

1. Run `git status` to see all modified/added files
2. Run `git diff --name-only` to get a list of changed file paths
3. Focus on Python files (`.py`) in `src/`, `scripts/`, and `gui/` directories (ignore `.venv/`, `__pycache__/`, etc.)

## Step 2: Check for Existing Tests

For each changed Python file:

1. Check if a corresponding test file exists in a `tests/` directory
2. Test files should follow the pattern `test_<module_name>.py`
3. If `tests/` directory doesn't exist, create it

## Step 3: Create Tests if Missing

For files without tests:

1. Read the source file to understand its functionality
2. Create comprehensive unit tests using `pytest`
3. Test key functions, classes, and edge cases
4. Use appropriate mocking for external dependencies (API calls, file I/O, etc.)
5. Place test files in `tests/` directory with naming convention `test_<module_name>.py`
6. Include docstrings explaining what each test validates

Test file template:
```python
"""Tests for <module_name>."""
import pytest
from unittest.mock import patch, MagicMock

# Import the module being tested
# from src.<module> import <functions/classes>


class Test<ClassName>:
    """Tests for <ClassName>."""

    def test_<method>_success(self):
        """Test <method> with valid input."""
        pass

    def test_<method>_edge_case(self):
        """Test <method> edge cases."""
        pass
```

## Step 4: Run Tests

1. Run pytest with verbose output: `python -m pytest tests/ -v`
2. If pytest is not installed, install it first: `pip install pytest pytest-mock`
3. Capture all test output including failures and errors

## Step 5: Fix Errors

If tests fail:

1. Analyze the error messages carefully
2. Determine if the issue is in the test or the source code
3. Fix the appropriate file(s)
4. Re-run tests until all pass
5. Repeat until all tests pass (max 5 iterations to avoid infinite loops)

## Step 6: Create Commit

Once all tests pass:

1. Run `git status` to see what needs to be committed
2. Run `git diff` to review the changes
3. Check recent commits with `git log --oneline -5` to match the commit style
4. Stage all relevant files: `git add <files>`
5. Write a descriptive commit message that:
   - Starts with a verb (Add, Fix, Update, Refactor, etc.)
   - Summarizes what was changed and why
   - Mentions tests were added/updated if applicable
6. Create the commit with proper format:

```bash
git commit -m "$(cat <<'EOF'
<Short summary line>

<Optional detailed description of changes>

- Tests added/updated for <modules>
- <Other relevant details>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

## Important Notes

- Never commit `.env`, credentials, or sensitive files
- If source files have issues that tests reveal, fix the source code
- Keep tests focused and maintainable
- Use descriptive test names that explain what's being tested
- Mock external services and APIs to ensure tests run offline
- If no changes are detected, inform the user that there's nothing to test/commit
