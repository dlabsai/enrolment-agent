from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from app.api.deps import get_current_user, require_user_roles
from app.api.schemas import (
    EvalReportDetailOut,
    EvalReportSummaryOut,
    EvalRunLogFileOut,
    EvalRunRequest,
    EvalTestCasesOut,
)
from app.models import UserRole

router = APIRouter(
    prefix="/evals",
    tags=["evals"],
    dependencies=[Depends(require_user_roles(get_current_user, UserRole.ADMIN, UserRole.DEV))],
)

REPORTS_DIR = Path(__file__).resolve().parents[3] / "reports"
LOGS_DIR = REPORTS_DIR / "logs"
REPORT_LOG_MAP_DIR = LOGS_DIR / "reports"
BACKEND_ROOT = REPORTS_DIR.parent

_EVAL_SUITES: dict[str, Path] = {
    "chatbot": BACKEND_ROOT / "tests" / "chat" / "test_eval_chatbot.py",
    "guardrails": BACKEND_ROOT / "tests" / "chat" / "test_eval_guardrails.py",
    "search": BACKEND_ROOT / "tests" / "chat" / "test_eval_search.py",
}

_NAME_RE = re.compile(r"^# Evaluation Report: (.+)")
_GENERATED_RE = re.compile(r"^\*\*Generated:\*\* (.+)")
_REPEATS_RE = re.compile(r"^\*\*Repeats:\*\* (\d+) \| \*\*Concurrency:\*\* (\d+)")
_FILENAME_RE = re.compile(r"^eval_(.+)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.md$")
_TEST_CASE_ID_RE = re.compile(r"test_case_id\s*=\s*(['\"])(.*?)\1")


class EvalReportLogMap(BaseModel):
    log_id: str


def _parse_filename_metadata(filename: str) -> tuple[str | None, datetime | None]:
    match = _FILENAME_RE.match(filename)
    if match is None:
        return None, None
    name = match.group(1)
    timestamp = match.group(2)
    try:
        generated_at = datetime.strptime(timestamp, "%Y-%m-%d_%H-%M-%S").replace(tzinfo=UTC)
    except ValueError:
        generated_at = None
    return name, generated_at


def _read_report_metadata(report_path: Path) -> tuple[str, datetime, int | None, int | None]:
    name: str | None = None
    generated_at: datetime | None = None
    repeats: int | None = None
    concurrency: int | None = None

    try:
        with report_path.open("r", encoding="utf-8") as handle:
            for _ in range(25):
                line = handle.readline()
                if line == "":
                    break
                cleaned = line.strip()
                if cleaned == "":
                    continue
                if name is None:
                    match = _NAME_RE.match(cleaned)
                    if match is not None:
                        name = match.group(1).strip()
                        continue
                if generated_at is None:
                    match = _GENERATED_RE.match(cleaned)
                    if match is not None:
                        generated_value = match.group(1).strip()
                        try:
                            generated_at = datetime.fromisoformat(generated_value)
                            if generated_at.tzinfo is None:
                                generated_at = generated_at.replace(tzinfo=UTC)
                        except ValueError:
                            generated_at = None
                        continue
                if repeats is None:
                    match = _REPEATS_RE.match(cleaned)
                    if match is not None:
                        repeats = int(match.group(1))
                        concurrency = int(match.group(2))
                        continue
                if name is not None and generated_at is not None and repeats is not None:
                    break
    except OSError:
        pass

    filename_name, filename_generated_at = _parse_filename_metadata(report_path.name)
    if name is None:
        name = filename_name or report_path.stem
    if generated_at is None:
        generated_at = filename_generated_at
    if generated_at is None:
        generated_at = datetime.fromtimestamp(report_path.stat().st_mtime, tz=UTC)

    return name, generated_at, repeats, concurrency


def _resolve_report_path(report_id: str) -> Path:
    if "/" in report_id or "\\" in report_id:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report_id.endswith(".md"):
        raise HTTPException(status_code=404, detail="Report not found")
    report_path = REPORTS_DIR / report_id
    if not report_path.exists() or not report_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return report_path


def _resolve_log_path(log_id: str) -> Path:
    if "/" in log_id or "\\" in log_id:
        raise HTTPException(status_code=404, detail="Log not found")
    if not log_id.endswith(".log"):
        raise HTTPException(status_code=404, detail="Log not found")
    log_path = LOGS_DIR / log_id
    if not log_path.exists() or not log_path.is_file():
        raise HTTPException(status_code=404, detail="Log not found")
    return log_path


def _resolve_report_log_map(report_id: str) -> Path:
    if "/" in report_id or "\\" in report_id:
        raise HTTPException(status_code=404, detail="Log not found")
    if not report_id.endswith(".md"):
        raise HTTPException(status_code=404, detail="Log not found")
    return REPORT_LOG_MAP_DIR / f"{report_id}.json"


def _format_sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _resolve_eval_suite(suite: str) -> Path:
    test_path = _EVAL_SUITES.get(suite)
    if test_path is None:
        raise HTTPException(status_code=400, detail="Unsupported eval suite")
    if not test_path.exists():
        raise HTTPException(status_code=404, detail="Eval suite not found")
    return test_path


def _extract_test_case_ids(test_path: Path) -> list[str]:
    try:
        content = test_path.read_text(encoding="utf-8")
    except OSError:
        return []

    cases: list[str] = []
    seen: set[str] = set()
    for match in _TEST_CASE_ID_RE.finditer(content):
        case_id = match.group(2)
        if case_id in seen:
            continue
        seen.add(case_id)
        cases.append(case_id)

    return cases


def _build_eval_command(run_request: EvalRunRequest, test_path: Path) -> list[str]:
    command = ["uv", "run", "pytest", str(test_path), "-v", "-s"]

    command.extend(["--repeat", str(run_request.repeat)])
    command.extend(["--max-concurrency", str(run_request.max_concurrency)])
    command.extend(["--pass-threshold", str(run_request.pass_threshold)])
    if run_request.test_cases is not None and run_request.test_cases.strip() != "":
        command.extend(["--test-cases", run_request.test_cases])
    if run_request.chatbot_model:
        command.extend(["--chatbot-model", run_request.chatbot_model])
    if run_request.guardrail_model:
        command.extend(["--guardrail-model", run_request.guardrail_model])
    if run_request.search_model:
        command.extend(["--search-model", run_request.search_model])
    if run_request.extractor_model:
        command.extend(["--extractor-model", run_request.extractor_model])
    if run_request.evaluation_model:
        command.extend(["--evaluation-model", run_request.evaluation_model])

    return command


def _build_eval_env(run_request: EvalRunRequest) -> dict[str, str]:
    env = os.environ.copy()
    overrides = {
        "CHATBOT_MODEL": run_request.chatbot_model,
        "GUARDRAIL_MODEL": run_request.guardrail_model,
        "EXTRACTOR_MODEL": run_request.extractor_model,
        "EVALUATION_MODEL": run_request.evaluation_model,
        "SEARCH_AGENT_MODEL": run_request.search_model,
    }
    for key, value in overrides.items():
        if value is None:
            continue
        trimmed = value.strip()
        if trimmed != "":
            env[key] = trimmed
    return env


@router.get("/test-cases", response_model=EvalTestCasesOut)
async def list_eval_test_cases(suite: Annotated[str, Query()]) -> EvalTestCasesOut:
    test_path = _resolve_eval_suite(suite)
    cases = _extract_test_case_ids(test_path)
    return EvalTestCasesOut(suite=suite, cases=cases)


@router.get("/reports", response_model=list[EvalReportSummaryOut])
async def list_eval_reports(
    limit: Annotated[int, Query(ge=1, le=200)] = 50, search: Annotated[str | None, Query()] = None
) -> list[EvalReportSummaryOut]:
    if not REPORTS_DIR.exists():
        return []

    search_value = search.lower() if search is not None else None
    reports: list[EvalReportSummaryOut] = []

    for report_path in REPORTS_DIR.iterdir():
        if not report_path.is_file():
            continue
        if report_path.suffix != ".md" or not report_path.name.startswith("eval_"):
            continue

        name, generated_at, repeats, concurrency = _read_report_metadata(report_path)
        if search_value is not None and (
            search_value not in name.lower() and search_value not in report_path.name.lower()
        ):
            continue

        reports.append(
            EvalReportSummaryOut(
                id=report_path.name,
                name=name,
                generated_at=generated_at,
                repeats=repeats,
                concurrency=concurrency,
                filename=report_path.name,
                size_bytes=report_path.stat().st_size,
            )
        )

    reports.sort(key=lambda report: report.generated_at, reverse=True)
    return reports[:limit]


@router.get("/reports/{report_id}", response_model=EvalReportDetailOut)
async def get_eval_report(report_id: str) -> EvalReportDetailOut:
    if not REPORTS_DIR.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    report_path = _resolve_report_path(report_id)
    name, generated_at, repeats, concurrency = _read_report_metadata(report_path)

    return EvalReportDetailOut(
        id=report_path.name,
        name=name,
        generated_at=generated_at,
        repeats=repeats,
        concurrency=concurrency,
        filename=report_path.name,
        size_bytes=report_path.stat().st_size,
        content=report_path.read_text(encoding="utf-8"),
    )


@router.get("/runs/logs/{log_id}", response_model=EvalRunLogFileOut)
async def get_eval_run_log(log_id: str) -> EvalRunLogFileOut:
    if not LOGS_DIR.exists():
        raise HTTPException(status_code=404, detail="Log not found")

    log_path = _resolve_log_path(log_id)

    return EvalRunLogFileOut(
        id=log_path.name,
        filename=log_path.name,
        size_bytes=log_path.stat().st_size,
        content=log_path.read_text(encoding="utf-8"),
    )


@router.get("/reports/{report_id}/log", response_model=EvalRunLogFileOut)
async def get_eval_report_log(report_id: str) -> EvalRunLogFileOut:
    if not REPORTS_DIR.exists():
        raise HTTPException(status_code=404, detail="Log not found")

    _resolve_report_path(report_id)
    map_path = _resolve_report_log_map(report_id)
    if not map_path.exists() or not map_path.is_file():
        raise HTTPException(status_code=404, detail="Log not found")

    try:
        payload = EvalReportLogMap.model_validate_json(map_path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise HTTPException(status_code=404, detail="Log not found") from error

    log_id = payload.log_id

    log_path = _resolve_log_path(log_id)

    return EvalRunLogFileOut(
        id=log_path.name,
        filename=log_path.name,
        size_bytes=log_path.stat().st_size,
        content=log_path.read_text(encoding="utf-8"),
    )


@router.post("/runs/stream")
async def run_eval_stream(run_request: EvalRunRequest, request: Request) -> StreamingResponse:
    if run_request.repeat < 1:
        raise HTTPException(status_code=400, detail="Repeat must be at least 1")
    if run_request.max_concurrency < 1:
        raise HTTPException(status_code=400, detail="Max concurrency must be at least 1")
    if not 0 < run_request.pass_threshold <= 1:
        raise HTTPException(status_code=400, detail="Pass threshold must be between 0 and 1")

    test_path = _resolve_eval_suite(run_request.suite)
    command = _build_eval_command(run_request, test_path)
    env = _build_eval_env(run_request)
    existing_reports = {path.name for path in REPORTS_DIR.glob("eval_*.md")}
    log_id = (
        f"eval_run_{run_request.suite}_"
        f"{datetime.now(UTC).strftime('%Y-%m-%d_%H-%M-%S')}_{uuid4().hex}.log"
    )
    log_path = LOGS_DIR / log_id

    async def event_stream() -> AsyncGenerator[str]:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_handle = log_path.open("a", encoding="utf-8")
        log_lock = asyncio.Lock()

        async def append_log(label: str, message: str) -> None:
            async with log_lock:
                log_handle.write(f"[{label}] {message}\n")
                log_handle.flush()

        try:
            queue: asyncio.Queue[tuple[str, dict[str, object]]] = asyncio.Queue()
            command_line = " ".join(command)
            yield _format_sse(
                "status",
                {
                    "status": "start",
                    "suite": run_request.suite,
                    "command": command_line,
                    "log_id": log_id,
                },
            )

            await append_log("command", f"$ {command_line}")
            await queue.put(("log", {"stream": "command", "message": f"$ {command_line}"}))

            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=str(BACKEND_ROOT),
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError:
                yield _format_sse(
                    "error",
                    {"message": "Failed to start evals. Ensure uv is available on the backend."},
                )
                return

            if process.stdout is None or process.stderr is None:
                yield _format_sse("error", {"message": "Eval process streams are unavailable."})
                return

            async def read_stream(stream: asyncio.StreamReader, label: str) -> None:
                while True:
                    line = await stream.readline()
                    if line == b"":
                        break
                    message = line.decode("utf-8", errors="replace").rstrip()
                    await append_log(label, message)
                    await queue.put(("log", {"stream": label, "message": message}))
                await queue.put(("stream_end", {"stream": label}))

            tasks = [
                asyncio.create_task(read_stream(process.stdout, "stdout")),
                asyncio.create_task(read_stream(process.stderr, "stderr")),
            ]

            completed_streams = 0
            disconnected = False

            while completed_streams < len(tasks):
                if await request.is_disconnected():
                    disconnected = True
                    process.terminate()
                    break
                try:
                    event, payload = await asyncio.wait_for(queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                if event == "stream_end":
                    completed_streams += 1
                    continue
                yield _format_sse(event, payload)

            if disconnected:
                for task in tasks:
                    task.cancel()
                await process.wait()
                yield _format_sse("status", {"status": "cancelled"})
                return

            for task in tasks:
                task.cancel()

            exit_code = await process.wait()

            current_reports = set(REPORTS_DIR.glob("eval_*.md"))
            new_reports = [path for path in current_reports if path.name not in existing_reports]
            if new_reports:
                newest = max(new_reports, key=lambda path: path.stat().st_mtime)
                name, generated_at, repeats, concurrency = _read_report_metadata(newest)
                REPORT_LOG_MAP_DIR.mkdir(parents=True, exist_ok=True)
                map_path = _resolve_report_log_map(newest.name)
                with contextlib.suppress(OSError):
                    map_path.write_text(
                        json.dumps({"log_id": log_id}, ensure_ascii=False), encoding="utf-8"
                    )
                yield _format_sse(
                    "report",
                    {
                        "report_id": newest.name,
                        "name": name,
                        "generated_at": generated_at.isoformat(),
                        "repeats": repeats,
                        "concurrency": concurrency,
                    },
                )

            if exit_code == 0:
                yield _format_sse("status", {"status": "complete", "exit_code": exit_code})
            else:
                yield _format_sse("status", {"status": "error", "exit_code": exit_code})
        finally:
            log_handle.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
