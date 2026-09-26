## Summary of Changes

A concise description of what this PR accomplishes and why it is needed.

Fixes #(issue) *(if applicable)*

---

## Type of Change

- [ ] `fix`: Bug fix that patches an issue
- [ ] `feat`: New feature or capability
- [ ] `docs`: Documentation, spec, or validation report update
- [ ] `refactor`: Code refactoring without behavioral alterations
- [ ] `test`: Adding missing tests or improving existing test suites
- [ ] `chore`: Tooling, workflow, or packaging maintenance

---

## Verification & Conformance

Please verify that the following checks have passed:

- [ ] All field validation tests pass (`python tests/test_v301_field.py`)
- [ ] Tool suites pass (`python tests/test_uaf_tools.py`)
- [ ] Linting checks pass (`ruff check .`)
- [ ] No regression introduced to existing profiles (`minimal`, `standard`, `full`)
- [ ] If changing schemas, templates (`templates/`) and scaffold (`scaffold/.ai/`) remain synchronized

---

## Checklist

- [ ] My code follows the repository's code style and golden axioms.
- [ ] I have updated the documentation / specifications accordingly.
- [ ] I have verified that changes fail closed under error conditions.
