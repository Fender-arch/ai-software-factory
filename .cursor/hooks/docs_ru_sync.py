#!/usr/bin/env python3
"""Track English docs edits and trigger Russian mirror sync.

Events:
  afterFileEdit — mark / clear pending EN→RU sync; inject reminder context
  stop          — if pending remains, auto-follow up once to sync translations
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
STATE_PATH = HOOKS_DIR / "state" / "docs-ru-pending.json"
REPO_ROOT = HOOKS_DIR.parent.parent


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _load_pending() -> list[str]:
    if not STATE_PATH.is_file():
        return []
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    files = data.get("files", [])
    return sorted({str(f) for f in files if isinstance(f, str)})


def _save_pending(files: list[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not files:
        if STATE_PATH.is_file():
            STATE_PATH.unlink()
        return
    STATE_PATH.write_text(
        json.dumps({"files": sorted(set(files))}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _rel_posix(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return None


def _classify_docs_path(rel: str) -> str | None:
    """Return 'en', 'ru', or None."""
    if not rel.endswith(".md"):
        return None
    if rel == "docs/README.md" or (
        rel.startswith("docs/") and not rel.startswith("docs/ru/") and rel.count("/") == 1
    ):
        return "en"
    if rel == "docs/ru/README.md" or (
        rel.startswith("docs/ru/") and rel.count("/") == 2
    ):
        return "ru"
    return None


def _en_to_ru_rel(en_rel: str) -> str:
    if en_rel == "docs/README.md":
        return "docs/ru/README.md"
    name = Path(en_rel).name
    return f"docs/ru/{name}"


def _ru_to_en_rel(ru_rel: str) -> str:
    if ru_rel == "docs/ru/README.md":
        return "docs/README.md"
    name = Path(ru_rel).name
    return f"docs/{name}"


def handle_after_file_edit(payload: dict) -> dict:
    file_path = payload.get("file_path") or ""
    if not file_path:
        return {}

    rel = _rel_posix(Path(file_path))
    if not rel:
        return {}

    kind = _classify_docs_path(rel)
    if kind is None:
        return {}

    pending = _load_pending()

    if kind == "en":
        if rel not in pending:
            pending.append(rel)
            _save_pending(pending)
        ru_rel = _en_to_ru_rel(rel)
        return {
            "additional_context": (
                "ASF docs sync required: English canonical doc was edited. "
                f"Update the Russian mirror `{ru_rel}` from `{rel}` "
                "(full faithful translation; keep code identifiers/paths; "
                "banner `> Перевод. Канон: ...`). "
                "Do not change English meaning when translating. "
                "English remains source of truth for agents and implementation."
            )
        }

    # Russian mirror edited → clear matching EN pending entry
    en_rel = _ru_to_en_rel(rel)
    if en_rel in pending:
        pending = [p for p in pending if p != en_rel]
        _save_pending(pending)
    return {}


def handle_stop(payload: dict) -> dict:
    status = payload.get("status") or "completed"
    loop_count = int(payload.get("loop_count") or 0)
    if status != "completed" or loop_count > 0:
        return {}

    pending = _load_pending()
    if not pending:
        return {}

    lines = []
    for en_rel in pending:
        ru_rel = _en_to_ru_rel(en_rel)
        lines.append(f"- `{en_rel}` → `{ru_rel}`")

    message = (
        "Automatic docs sync: English Foundation docs changed without an updated "
        "Russian mirror. Translate/update these files now (faithful RU copy; keep "
        "paths/identifiers; include the standard canon banner). Do not alter the "
        "English sources. When done, stop.\n\n" + "\n".join(lines)
    )
    return {"followup_message": message}


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        _emit({})
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _emit({})
        return 0

    event = (
        payload.get("hook_event_name")
        or payload.get("event")
        or ""
    ).strip()

    # Infer from shape when event name missing
    if not event:
        if "file_path" in payload and "edits" in payload:
            event = "afterFileEdit"
        elif "loop_count" in payload or "status" in payload:
            event = "stop"

    if event == "afterFileEdit":
        _emit(handle_after_file_edit(payload))
    elif event == "stop":
        _emit(handle_stop(payload))
    else:
        _emit({})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
