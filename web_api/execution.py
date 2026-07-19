from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from web_api.config import PROJECT_ROOT, pipeline_timeout_seconds


ProgressCallback = Callable[[dict], None]


@dataclass(frozen=True)
class ExecutionResult:
    return_code: int
    stdout_tail: str
    stderr_tail: str


class ExecutionFailed(RuntimeError):
    def __init__(self, result: ExecutionResult) -> None:
        super().__init__(f"Pipeline subprocess exited with status {result.return_code}")
        self.result = result


class ExecutionTimedOut(TimeoutError):
    def __init__(self, timeout_seconds: float, result: ExecutionResult) -> None:
        super().__init__(f"Pipeline subprocess exceeded {timeout_seconds:g} seconds")
        self.timeout_seconds = timeout_seconds
        self.result = result


class SubprocessExecutor:
    """Run one pipeline process and stream its machine-readable progress events."""

    def __init__(self, timeout_seconds: float | None = None, poll_interval: float = 0.1) -> None:
        self.timeout_seconds = timeout_seconds or pipeline_timeout_seconds()
        self.poll_interval = poll_interval

    def execute(
        self,
        *,
        run_id: str,
        intake: dict,
        artifact_directory: Path,
        on_progress: ProgressCallback,
    ) -> ExecutionResult:
        artifact_directory.mkdir(parents=True, exist_ok=False)
        intake_path = artifact_directory / "web-intake.json"
        progress_path = artifact_directory / "progress.jsonl"
        stdout_path = artifact_directory / "subprocess.stdout.log"
        stderr_path = artifact_directory / "subprocess.stderr.log"
        intake_path.write_text(json.dumps(intake, indent=2, ensure_ascii=False), encoding="utf-8")

        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "--run-id",
            run_id,
            "--intake",
            str(intake_path),
            "--output-dir",
            str(artifact_directory),
            "--progress-file",
            str(progress_path),
        ]
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        started = time.monotonic()
        progress_offset = 0

        with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_file:
            process = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
            )
            timed_out = False
            while process.poll() is None:
                progress_offset = self._drain_progress(progress_path, progress_offset, on_progress)
                if time.monotonic() - started >= self.timeout_seconds:
                    timed_out = True
                    process.kill()
                    break
                time.sleep(self.poll_interval)
            process.wait()
            self._drain_progress(progress_path, progress_offset, on_progress)

        result = ExecutionResult(
            return_code=process.returncode,
            stdout_tail=_tail(stdout_path),
            stderr_tail=_tail(stderr_path),
        )
        if timed_out:
            raise ExecutionTimedOut(self.timeout_seconds, result)
        if result.return_code != 0:
            raise ExecutionFailed(result)
        return result

    @staticmethod
    def _drain_progress(path: Path, offset: int, callback: ProgressCallback) -> int:
        if not path.is_file():
            return offset
        with path.open(encoding="utf-8") as progress_file:
            progress_file.seek(offset)
            content = progress_file.read()
            new_offset = progress_file.tell()
            for line in content.splitlines():
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    callback(payload)
            return new_offset


def _tail(path: Path, limit: int = 4000) -> str:
    try:
        with path.open("rb") as file:
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(max(0, size - limit))
            return file.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
