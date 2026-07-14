from pathlib import Path


README = Path(__file__).resolve().parents[1] / "README.md"


def test_watch_generator_runtime_dependencies_import():
    import build123d  # noqa: F401
    import matplotlib  # noqa: F401
    import numpy  # noqa: F401
    import PIL  # noqa: F401
    import scipy  # noqa: F401


def test_readme_installs_dependencies_from_required_working_directories():
    readme = README.read_text(encoding="utf-8")
    install_commands = """```powershell
Push-Location skills/cad
python -m pip install -r requirements.txt
Pop-Location
python -m pip install -r models/watch_kinematic/requirements.txt
```"""

    assert "From the repository root" in readme
    assert install_commands in readme
