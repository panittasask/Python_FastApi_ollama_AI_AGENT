import pytest

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(autouse=True)
def _set_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    yield
