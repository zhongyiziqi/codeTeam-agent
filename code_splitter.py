import ast
from dataclasses import dataclass

from codeteam.indexing.repo_loader import SourceFile


@dataclass(frozen=True)
class ChunkData:
    file_path: str
    language: str
    symbol_name: str | None
    chunk_type: str
    start_line: int
    end_line: int
    content: str


def split_source_file(source: SourceFile, max_lines: int = 120) -> list[ChunkData]:
    if source.language == "python":
        chunks = _split_python(source)
        if chunks:
            return chunks
    return _split_by_lines(source, max_lines)


def _split_python(source: SourceFile) -> list[ChunkData]:
    try:
        tree = ast.parse(source.content)
    except SyntaxError:
        return []

    lines = source.content.splitlines()
    chunks: list[ChunkData] = []
    for node in tree.body:
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        chunk_type = "class" if isinstance(node, ast.ClassDef) else "function"
        chunks.append(
            ChunkData(
                file_path=source.path,
                language=source.language,
                symbol_name=node.name,
                chunk_type=chunk_type,
                start_line=start_line,
                end_line=end_line,
                content="\n".join(lines[start_line - 1 : end_line]),
            )
        )
    return chunks


def _split_by_lines(source: SourceFile, max_lines: int) -> list[ChunkData]:
    lines = source.content.splitlines()
    if not lines:
        return []
    chunks = []
    for start_index in range(0, len(lines), max_lines):
        end_index = min(start_index + max_lines, len(lines))
        chunks.append(
            ChunkData(
                file_path=source.path,
                language=source.language,
                symbol_name=None,
                chunk_type="file",
                start_line=start_index + 1,
                end_line=end_index,
                content="\n".join(lines[start_index:end_index]),
            )
        )
    return chunks
