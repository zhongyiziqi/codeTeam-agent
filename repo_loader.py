from dataclasses import dataclass
from pathlib import Path

from git import Repo

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".md": "markdown",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".idea",
    ".venv",
    ".vscode",
    "build",
    "dist",
    "node_modules",
    "vendor",
    "__pycache__",
}


@dataclass(frozen=True)
class SourceFile:
    path: str
    language: str
    content: str


def prepare_repository(source_url: str | None, local_path: str, branch: str | None) -> Path:
    target = Path(local_path).resolve()
    if source_url:
        if target.exists() and (target / ".git").exists():
            repo = Repo(target)
            repo.remotes.origin.pull()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            Repo.clone_from(source_url, target, branch=branch)
    if not target.exists() or not target.is_dir():
        raise ValueError(f"Repository path does not exist: {target}")
    return target


def repository_revision(path: Path) -> tuple[str | None, str | None]:
    try:
        repo = Repo(path)
        branch = None if repo.head.is_detached else repo.active_branch.name
        return branch, repo.head.commit.hexsha
    except Exception:
        return None, None


def iter_source_files(root: Path, max_file_bytes: int = 1_000_000):
    for path in root.rglob("*"):
        if not path.is_file() or any(part in IGNORED_DIRECTORIES for part in path.parts):
            continue
        language = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
        if language is None or path.stat().st_size > max_file_bytes:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        yield SourceFile(path=path.relative_to(root).as_posix(), language=language, content=content)
