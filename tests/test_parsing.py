from app.utils.parsing import extract_json, parse_file_blocks


def test_extract_json_from_fence():
    text = 'noise ```json\n{"a": 1, "b": [1,2,3]}\n``` tail'
    assert extract_json(text) == {"a": 1, "b": [1, 2, 3]}


def test_extract_json_repairs_trailing_commas():
    text = '{"a": 1, "b": [1,2,3,],}'
    assert extract_json(text) == {"a": 1, "b": [1, 2, 3]}


def test_parse_file_blocks_with_header():
    text = (
        "Here are the files.\n\n"
        "File: app/main.py\n```python\nprint('hi')\n```\n\n"
        "File: README.md\n```markdown\n# hi\n```\n"
    )
    files = parse_file_blocks(text)
    paths = [f["path"] for f in files]
    assert "app/main.py" in paths
    assert "README.md" in paths
    assert any("print('hi')" in f["content"] for f in files)


def test_parse_file_blocks_with_path_in_fence():
    text = "```app/util.py\nx=1\n```"
    files = parse_file_blocks(text)
    assert files == [{"path": "app/util.py", "content": "x=1\n"}]
