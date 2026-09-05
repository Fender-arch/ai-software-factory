"""Launch a Cursor Cloud Agent when env is set; otherwise a manual stub."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from core.config import get_settings
from core.models import BuildJob, BuildJobStatus

logger = logging.getLogger(__name__)

_TIMEOUT_S = 15.0


@dataclass
class CursorLaunchResult:
    executor: str
    status: str
    external_id: str | None = None
    deep_link: str | None = None
    message: str = ""
    raw: dict[str, Any] | None = None


class CursorExecutor(Protocol):
    def launch(self, job: BuildJob, brief: dict[str, Any]) -> CursorLaunchResult: ...

    def poll(self, job: BuildJob) -> CursorLaunchResult | None: ...


class StubCursorExecutor:
    """Architecture-ready handoff: export + deep-link, no live agent."""

    def launch(self, job: BuildJob, brief: dict[str, Any]) -> CursorLaunchResult:
        project_id = brief.get("project_id") or str(job.project_id)
        link = (
            brief.get("deep_link")
            or f"/projects/{project_id}/export/tasks?format=markdown"
        )
        return CursorLaunchResult(
            executor="stub",
            status=BuildJobStatus.READY_FOR_CLIENT.value,
            external_id=f"stub-{job.id}",
            deep_link=link,
            message=(
                "Cursor API не настроен — brief и export готовы для ручного запуска. "
                "Задайте CURSOR_API_KEY, чтобы стартовать Cloud Agent."
            ),
        )

    def poll(self, job: BuildJob) -> CursorLaunchResult | None:
        return CursorLaunchResult(
            executor="stub",
            status=job.status,
            external_id=job.external_id,
            deep_link=(job.payload or {}).get("deep_link"),
            message="stub",
        )


class HttpCursorExecutor:
    def launch(self, job: BuildJob, brief: dict[str, Any]) -> CursorLaunchResult:
        settings = get_settings()
        key = (settings.cursor_api_key or "").strip()
        base = (settings.cursor_cloud_api_url or "https://api.cursor.com").rstrip("/")
        repo = (settings.cursor_agent_repo or "").strip()
        prompt = brief.get("prompt") or brief.get("task_export_markdown") or ""
        body: dict[str, Any] = {
            "prompt": {"text": str(prompt)[:20000]},
            "name": f"ASF MVP {brief.get('project_name') or job.project_id}",
        }
        if repo:
            body["source"] = {"repository": repo, "ref": "main"}
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                response = client.post(
                    f"{base}/v0/agents",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                data = response.json() if response.content else {}
        except Exception as exc:  # noqa: BLE001 — fall back to stub
            logger.warning("Cursor Cloud Agent launch failed; using stub: %s", exc)
            stub = StubCursorExecutor().launch(job, brief)
            stub.message = f"Cursor API недоступен ({exc.__class__.__name__}). {stub.message}"
            return stub

        agent_id = str(data.get("id") or data.get("bcId") or data.get("agentId") or "")
        url = data.get("url") or data.get("target") or ""
        if not url and agent_id:
            url = f"https://cursor.com/agents/{agent_id}"
        if not url:
            q = quote((brief.get("project_name") or "ASF MVP")[:80])
            url = f"https://cursor.com/agents?q={q}"
        return CursorLaunchResult(
            executor="cursor",
            status=BuildJobStatus.RUNNING.value,
            external_id=agent_id or None,
            deep_link=url,
            message="Cloud Agent запущен.",
            raw=data if isinstance(data, dict) else None,
        )

    def poll(self, job: BuildJob) -> CursorLaunchResult | None:
        settings = get_settings()
        key = (settings.cursor_api_key or "").strip()
        base = (settings.cursor_cloud_api_url or "https://api.cursor.com").rstrip("/")
        if not key or not job.external_id:
            return None
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                response = client.get(
                    f"{base}/v0/agents/{job.external_id}",
                    headers={"Authorization": f"Bearer {key}"},
                )
                response.raise_for_status()
                data = response.json() if response.content else {}
        except Exception:  # noqa: BLE001
            logger.warning("Cursor Cloud Agent poll failed for %s", job.id)
            return None
        status_raw = str(data.get("status") or data.get("lifecycle") or "").lower()
        if status_raw in {"finished", "completed", "done", "ready"}:
            next_status = BuildJobStatus.READY_FOR_CLIENT.value
        elif status_raw in {"failed", "error", "killed"}:
            next_status = BuildJobStatus.FAILED.value
        else:
            next_status = BuildJobStatus.RUNNING.value
        return CursorLaunchResult(
            executor="cursor",
            status=next_status,
            external_id=job.external_id,
            deep_link=(job.payload or {}).get("deep_link"),
            message=status_raw or "running",
            raw=data if isinstance(data, dict) else None,
        )


def get_cursor_executor() -> CursorExecutor:
    settings = get_settings()
    if (settings.cursor_api_key or "").strip():
        return HttpCursorExecutor()
    return StubCursorExecutor()
