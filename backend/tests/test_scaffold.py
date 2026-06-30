from pathlib import Path


def test_backend_scaffold_exists() -> None:
    pyproject_path = Path(__file__).parents[1] / "pyproject.toml"
    if not pyproject_path.is_file():
        raise AssertionError("backend/pyproject.toml should exist")
