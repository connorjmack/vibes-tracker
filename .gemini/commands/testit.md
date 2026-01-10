---
description: Analyze changes, generate/run tests, fix errors, and commit the result.
---

I need you to test and commit the current work-in-progress code. Please follow this strictly:

1.  **Analyze Changes**: Run `git status` and `git diff` to identify which source files have been modified or created.
2.  **Check/Create Tests**:
    *   For each modified source file, check if a corresponding test file exists (look in `tests/` or alongside the file, following project conventions).
    *   **If no test exists:** Create a comprehensive unit test file for the modified code (using `pytest` or `unittest` as appropriate for the project).
    *   **If tests exist:** Ensure they cover the recent changes.
3.  **Run Tests**: Run the relevant tests.
4.  **Iterative Fix (Loop)**:
    *   If tests **fail**: Analyze the error output, fix the source code (or the test if the test is incorrect), and run the tests again. Repeat this step up to 3 times if necessary.
    *   If tests **pass**: Proceed to the next step.
5.  **Commit**:
    *   Stage the changes (`git add`).
    *   Generate a descriptive, conventional commit message based on the changes and the fact that tests are passing.
    *   Commit the changes.

**Constraint**: If you cannot fix the errors after 3 attempts, stop and report the specific failure so I can review it manually.
