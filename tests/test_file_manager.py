import pytest

from app.services.file_manager import FileManager
from app.core.exceptions import FileOperationError


@pytest.mark.asyncio
async def test_write_and_read(tmp_path):
    fm = FileManager(tmp_path / "proj")
    await fm.write_file("a/b/c.txt", "hello")
    assert fm.exists("a/b/c.txt")
    assert (await fm.read_file("a/b/c.txt")) == "hello"
    assert "a/b/c.txt" in fm.list_files()


@pytest.mark.asyncio
async def test_path_escape_blocked(tmp_path):
    fm = FileManager(tmp_path / "proj")
    with pytest.raises(FileOperationError):
        await fm.write_file("../evil.txt", "x")
