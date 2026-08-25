"""Download a Lucide subset for TZ graph section icons (ISC license)."""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "apps" / "console" / "icons"
BASE = "https://cdn.jsdelivr.net/npm/lucide-static@0.511.0/icons/{name}.svg"
LICENSE_URL = "https://cdn.jsdelivr.net/npm/lucide-static@0.511.0/LICENSE"

# TZ topics (all product types) + stages + product hubs + fallbacks
TOPICS = {
    "purpose_problem": "target",
    "product_shape": "app-window",
    "as_is_process": "git-branch",
    "success_mvp": "trophy",
    "out_of_scope": "circle-off",
    "timeline": "calendar",
    "budget": "wallet",
    "contacts": "contact",
    "preferred_contact": "phone",
    "roles": "users-round",
    "access": "key-round",
    "must_features": "list-checks",
    "primary_scenario": "route",
    "pages_sections": "layout-template",
    "delivery_surface": "app-window",
    "interaction_model": "messages-square",
    "public_identity": "contact",
    "offer_catalog": "layout-template",
    "visitor_cta": "send",
    "resources_ops": "server",
    "trigger_io": "zap",
    "admin_operations": "sliders-horizontal",
    "records": "table-2",
    "locale_ux": "languages",
    "brand_assets": "sparkles",
    "design_references": "layout-template",
    "design_direction": "sparkles",
    "ops_constraints": "timer",
    "legal_compliance": "badge-check",
    "promotion": "search-check",
    "integrations": "plug",
    "integration_map": "share-2",
    "human_approval": "user-check",
    "acceptance": "clipboard-check",
    "operator": "headphones",
    "risks": "triangle-alert",
    "other": "circle-help",
}

STAGES = {
    "PROJECT_CREATED": "flag",
    "UNDERSTANDING_IDEA": "lightbulb",
    "BUSINESS_CONTEXT": "briefcase",
    "USERS": "users",
    "FUNCTIONAL": "puzzle",
    "DATA": "database",
    "NON_FUNCTIONAL": "gauge",
    "INTEGRATIONS": "unplug",
    "ACCEPTANCE": "badge-check",
    "RISKS": "siren",
    "REVIEW": "search-check",
    "READY_FOR_OWNER": "circle-check-big",
    "UNSCOPED": "folder-open",
}

PRODUCTS = {
    "website": "globe",
    "telegram_bot": "send",
    "rest_service": "server-cog",
    "ai_automation": "sparkles",
    "default": "hexagon",
}

FALLBACKS = ("circle-dot", "circle-help")


def wrap_svg(raw: str) -> str:
    raw = re.sub(r'\n\s*<rect class="asf-icon-bg"[^/]*/>', "", raw)
    raw = raw.replace('stroke="currentColor"', 'stroke="#f4ead2"')
    raw = raw.replace('stroke-width="2"', 'stroke-width="2.25"')
    raw = re.sub(r'\bwidth="24"', 'width="128"', raw, count=1)
    raw = re.sub(r'\bheight="24"', 'height="128"', raw, count=1)
    return raw


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "asf-console-icons"})
    with urllib.request.urlopen(req, timeout=30) as res:
        if res.status != 200:
            raise RuntimeError(f"{res.status} {url}")
        return res.read()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = sorted(set(TOPICS.values()) | set(STAGES.values()) | set(PRODUCTS.values()) | set(FALLBACKS))
    failed: list[str] = []
    for name in names:
        dest = OUT / f"{name}.svg"
        if dest.exists() and dest.stat().st_size > 100:
            dest.write_text(wrap_svg(dest.read_text(encoding="utf-8")), encoding="utf-8")
            print("wrap", name)
            continue
        try:
            data = fetch(BASE.format(name=name)).decode("utf-8")
            dest.write_text(wrap_svg(data), encoding="utf-8")
            print("ok", name, dest.stat().st_size)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{name}: {exc}")
            print("FAIL", name, exc)
    license_path = OUT / "LICENSE-Lucide.txt"
    if not license_path.exists():
        try:
            license_path.write_bytes(fetch(LICENSE_URL))
        except Exception as exc:  # noqa: BLE001
            print("LICENSE fail", exc)
            license_path.write_text(
                "Lucide icons, ISC License. See https://lucide.dev/license\n",
                encoding="utf-8",
            )
    mapping = {
        "source": "https://lucide.dev/",
        "package": "lucide-static@0.511.0",
        "license": "ISC",
        "topics": TOPICS,
        "stages": STAGES,
        "products": PRODUCTS,
        "fallback": "circle-dot",
    }
    (OUT / "map.json").write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if failed:
        raise SystemExit("failed:\n" + "\n".join(failed))
    print("wrote", len(names), "icons")


if __name__ == "__main__":
    main()
