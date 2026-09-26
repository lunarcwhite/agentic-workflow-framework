# Contributing to UAAF

Thank you for your interest in contributing to the **Universal AI Agent Framework (UAAF)**! We welcome contributions from the community to help advance autonomous agent protocols, reliability standards, and secure multi-agent federation.

---

## Code of Conduct

All contributors and maintainers are expected to adhere to our [Code of Conduct](./CODE_OF_CONDUCT.md). Please read it before participating.

---

## Getting Started

### Prerequisites

- Python 3.10, 3.11, or 3.12
- Git
- `pip` or modern Python package manager (`uv`, `poetry`)

### Setting Up Development Environment

1. **Fork and Clone the Repository:**
   ```bash
   git clone https://github.com/<your-username>/universal-agent-framework.git
   cd universal-agent-framework
   ```

2. **Create and Activate a Virtual Environment:**
   ```bash
   # On macOS/Linux:
   python -m venv .venv
   source .venv/bin/activate

   # On Windows (PowerShell):
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies in Editable Mode:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify Installation:**
   ```bash
   uaf --help
   ```

---

## Development Workflow

### 1. Branching Strategy

Always create a new branch from `main`:
- `feat/feature-name`: New capabilities, tools, or extensions.
- `fix/issue-description`: Bug fixes and conformance issue patches.
- `docs/topic`: Documentation, specifications, or reporting updates.
- `refactor/area`: Code cleanup or structural optimization without behavioral changes.

### 2. Golden Principles for Code Changes

Contributors should keep the UAAF Core Axioms in mind:
- **Understand before changing:** Trace existing specs and tools first.
- **Inspect before inventing:** Check if standard templates or commands already cover the behavior.
- **Fail-Closed Security:** All security and policy verification boundaries must fail closed.
- **Minimal & Complete:** Keep changes focused without silently expanding scope.

### 3. Running Conformance Tests

Before submitting a Pull Request, verify that all test suites pass with zero warnings:

```bash
# Run latest field archetype test suite
python tests/test_v301_field.py

# Run general longitudinal & tool suites
python tests/test_uaf_tools.py
python tests/test_field_validation.py
```

### 4. Code Formatting & Linting

We use [Ruff](https://github.com/astral-sh/ruff) for fast, consistent linting:

```bash
# Check for lint issues
ruff check .

# Automatically fix fixable issues
ruff check --fix .
```

---

## Pull Request Guidelines

1. **Keep Commits Clear & Conventional:**
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: implement key-ops provider for azure key vault`
   - `fix: resolve manifest schema validation warning in v3.0.1`
   - `docs: add sequence diagram for federation handshakes`

2. **Fill out the PR Template:**
   When opening a Pull Request, complete all sections in the automated checklist.

3. **CI Passing:**
   Ensure all GitHub Actions checks pass green before requesting review.
