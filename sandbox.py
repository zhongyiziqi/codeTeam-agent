import os
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

from sqlalchemy.orm import Session

from codeteam.config import get_settings
from codeteam.models import ApprovalStatus, PatchExecution


def execute_approved_patch(session: Session, execution_id: str) -> dict:
    execution = session.get(PatchExecution, execution_id)
    if execution is None:
        raise ValueError("Patch execution not found")
    if execution.status != ApprovalStatus.approved:
        raise ValueError("Patch must be approved before execution")

    settings = get_settings()
    source = Path(execution.task.repository.local_path).resolve()
    sandbox = (settings.sandbox_root / execution.id).resolve()
    execution.status = ApprovalStatus.running
    execution.sandbox_path = str(sandbox)
    session.commit()

    try:
        _validate_diff_paths(execution.unified_diff)
        if sandbox.exists():
            shutil.rmtree(sandbox)
        shutil.copytree(source, sandbox, ignore=shutil.ignore_patterns(".git", ".venv"))
        patch_file = sandbox / ".codeteam.patch"
        patch_file.write_text(execution.unified_diff, encoding="utf-8")
        check = _run(["git", "apply", "--check", str(patch_file)], sandbox, 30)
        if check.returncode != 0:
            raise RuntimeError(f"Patch validation failed: {_output(check)}")
        applied = _run(["git", "apply", str(patch_file)], sandbox, 30)
        if applied.returncode != 0:
            raise RuntimeError(f"Patch apply failed: {_output(applied)}")
        execution.apply_output = _output(applied)

        command = execution.test_command or ["pytest", "-q"]
        _validate_command(command, settings.sandbox_allowed_commands)
        tested = _run(command, sandbox, settings.sandbox_timeout_seconds)
        execution.test_output = _output(tested)
        execution.exit_code = tested.returncode
        execution.status = (
            ApprovalStatus.succeeded if tested.returncode == 0 else ApprovalStatus.failed
        )
        session.commit()
        return {"status": execution.status, "exit_code": tested.returncode}
    except Exception as exc:
        session.rollback()
        execution = session.get(PatchExecution, execution_id)
        if execution is not None:
            execution.status = ApprovalStatus.failed
            execution.error_message = str(exc)
            session.commit()
        raise


def _validate_diff_paths(diff: str) -> None:
    if "new file mode 120000" in diff:
        raise ValueError("Symbolic link patches are not allowed")
    prefixes = ("+++ b/", "--- a/", "rename to ", "rename from ", "copy to ", "copy from ")
    paths = []
    for line in diff.splitlines():
        for prefix in prefixes:
            if line.startswith(prefix):
                paths.append(line[len(prefix) :])
                break
    if not paths:
        raise ValueError("Patch does not contain repository-relative file paths")
    for value in paths:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe patch path: {value}")


def _validate_command(command: list[str], allowed_commands: str) -> None:
    if not command:
        raise ValueError("Test command cannot be empty")
    allowed = {item.strip().lower() for item in allowed_commands.split(",") if item.strip()}
    executable = Path(command[0]).name.lower().removesuffix(".exe")
    if executable not in allowed:
        raise ValueError(f"Command is not allowed: {command[0]}")


def _run(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    executable_path = str(Path(sys.executable).parent)
    search_path = f"{executable_path}{os.pathsep}{os.environ.get('PATH', '')}"
    resolved = shutil.which(command[0], path=search_path)
    if resolved is None:
        raise FileNotFoundError(f"Executable not found: {command[0]}")
    resolved_command = [resolved, *command[1:]]
    environment = {
        "PATH": search_path,
        "PYTHONPATH": str(cwd),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
    }
    return subprocess.run(
        resolved_command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())