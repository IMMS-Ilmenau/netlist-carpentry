# Prerequisites and Notes regarding the Development Guide

## Getting Started

This package uses the Python project manager [uv](https://docs.astral.sh/uv/). To start development, please follow these steps:

1. Please refer to [installation instructions](https://docs.astral.sh/uv/installation/) for uv. Please use version 0.3.0 or higher.

2. Clone this repository:.
    ```bash
    git clone https://github.com/IMMS-Ilmenau/netlist-carpentry.git
    cd netlist-carpentry
    ```
3. Use `uv sync` to generate a virtual environment in `.venv`. This virtual environment can be sourced as usual:

    ```bash
    uv sync
    source .venv/bin/activate
    ```

The virtual environment will contain the package in editable mode, as well as all development dependencies.
VS Code can use it too!

To install packages use `uv pip install <package-name>`.
Please note that you should never install any packages to the `.venv` manually!
If you need additional dependencies or development dependencies, you can also edit them accordingly in `pyproject.toml` and re-run `uv sync`.

## Running Tests

This project uses [tox](https://tox.wiki/en/4.16.0/) for test orchestration.

By running it, you will run [pytest](https://docs.pytest.org/en/stable/), [mypy](https://mypy.readthedocs.io/en/stable/) and [ruff](https://docs.astral.sh/ruff/) all in one command:

```bash
uv run tox
```

(mypy is currently deactivated, because of... reasons)

uv will automatically download Python versions for tox.

Of course, you can run the tools independently too (as usual).
After activating the `.venv`, you can call them as usual, for example:

```bash
source .venv/bin/activate
ruff check src/netlist_carpentry
mypy -p netlist_carpentry
pytest netlist_carpentry
```

## Commiting changes

Before committing any changes, please remember the following steps:

1. Run all tests and static code checks via `tox`:

    ```bash
    uv run tox
    ```

2. (Optional) If you changed any dependencies (or just to be sure!), please run `uv sync` to re-create the lock file for your project. It must be committed to version control. The lock file allows restoring the exact environment you used yourself during development!

3. (Optional) If you edited the documentation, please try building it in `--strict` mode. This will turn warnings to errors.
    The same will happen in Gitlab CI.

    ```bash
    uv run mkdocs build --strict
    ```

## Building the documentation

The documentation for this project is built with [MkDocs](https://www.mkdocs.org), the [Material theme](https://squidfunk.github.io/mkdocs-material/reference/) and [mkdocstrings](https://mkdocstrings.github.io).

After [installing the development requirements](#getting-started), you can build the documentation locally with:

```bash
uv run mkdocs build
```

The results will be in `docs/site`.

You can also serve a preview of the documentation:

```bash
uv run mkdocs serve
```

The website will live update to changes in source code, both inside 'docs/src' and the Python source code `src/netlist_carpentry`.
