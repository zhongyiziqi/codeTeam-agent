from codeteam.indexing.code_splitter import split_source_file
from codeteam.indexing.repo_loader import SourceFile


def test_python_splitter_preserves_symbol_and_lines():
    source = SourceFile(
        path="service.py",
        language="python",
        content="def validate(value: str) -> bool:\n    return bool(value)\n",
    )

    chunks = split_source_file(source)

    assert len(chunks) == 1
    assert chunks[0].symbol_name == "validate"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 2
    assert chunks[0].file_path == "service.py"
