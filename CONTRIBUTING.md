# Contributing to CGC

Thanks for your interest in contributing to Context Graph Connector!

## Getting Started

1. Fork the repo and clone it locally
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   ```
3. Install in development mode:
   ```bash
   pip install -e ".[all,dev]"
   ```
4. Run the tests:
   ```bash
   pytest
   ```

## Development

### Code Style

We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
ruff check .
ruff format .
```

### Running Tests

```bash
pytest                    # run all tests
pytest tests/test_smoke.py  # run specific test file
pytest -x                 # stop on first failure
```

### Project Structure

- `cgc/` — main package
- `cgc/adapters/` — data source and sink adapters
- `cgc/discovery/` — schema discovery and graph extraction
- `cgc/core/` — shared types and data structures
- `tests/` — test suite
- `docs/` — documentation

## Submitting Changes

1. Create a feature branch from `master`
2. Make your changes with clear, focused commits
3. Ensure tests pass and linting is clean
4. Open a pull request with a description of what and why

## Reporting Issues

Open an issue at [github.com/anthonylee991/cgc/issues](https://github.com/anthonylee991/cgc/issues) with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version and OS

## Areas for Contribution

- New data source adapters
- New graph sink adapters
- Additional industry packs for extraction
- Documentation improvements
- Bug fixes and test coverage
- Performance optimizations

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
