"""TZ graph projection for the owner console (view over KG + outline)."""

from __future__ import annotations

import uuid
from typing import Any

from core.models import Entity, Project
from core.estimate import estimate_console_panel, estimate_project
from discovery.fsm import DiscoveryStage
from discovery.tz_outline import plan_from_state, resolve_active_topics, topic_by_id
from knowledge.repository import KnowledgeRepository
from knowledge.types import normalize_requirement_status

STAGE_LABELS_RU: dict[str, str] = {
    DiscoveryStage.PROJECT_CREATED.value: "Старт",
    DiscoveryStage.UNDERSTANDING_IDEA.value: "Цель и идея",
    DiscoveryStage.BUSINESS_CONTEXT.value: "Бизнес-контекст",
    DiscoveryStage.USERS.value: "Пользователи",
    DiscoveryStage.FUNCTIONAL.value: "Функции",
    DiscoveryStage.DATA.value: "Данные",
    DiscoveryStage.NON_FUNCTIONAL.value: "Ограничения",
    DiscoveryStage.INTEGRATIONS.value: "Интеграции",
    DiscoveryStage.ACCEPTANCE.value: "Приёмка",
    DiscoveryStage.RISKS.value: "Риски",
    DiscoveryStage.REVIEW.value: "Ревью",
    DiscoveryStage.READY_FOR_OWNER.value: "Готово владельцу",
}

UNSCOPED_STAGE_ID = "UNSCOPED"
UNSCOPED_TOPIC_ID = "other"


def _project_state(kg: KnowledgeRepository, project: Project) -> dict:
    entities = kg.list_entities(project.id, type_="Project")
    if not entities:
        return {}
    return dict(entities[0].payload or {})


def _requirement_label(entity: Entity) -> str:
    payload = entity.payload or {}
    desc = str(payload.get("description") or entity.name or "").strip()
    if len(desc) > 72:
        return desc[:69] + "…"
    return desc or entity.name


def _conflict_ids(kg: KnowledgeRepository, project_id: uuid.UUID) -> set[uuid.UUID]:
    ids: set[uuid.UUID] = set()
    for rel in kg.list_relations(project_id, type_="conflicts_with"):
        ids.add(rel.from_entity_id)
        ids.add(rel.to_entity_id)
    return ids


def build_tz_graph(kg: KnowledgeRepository, project: Project) -> dict[str, Any]:
    """Full graph JSON: virtual stage/topic nodes + Requirement leaves."""
    state = _project_state(kg, project)
    task_shape = state.get("task_shape")
    plan = plan_from_state(state)
    outline = resolve_active_topics(project.product_type, task_shape=task_shape, plan=plan)
    requirements = [
        e
        for e in kg.list_entities(project.id, type_="Requirement")
        if e.status != "archived"
    ]
    conflict_ids = _conflict_ids(kg, project.id)

    project_node_id = f"project:{project.id}"
    nodes: list[dict[str, Any]] = [
        {
            "id": project_node_id,
            "kind": "project",
            "label": project.name,
            "parent": None,
            "level": 0,
            "child_count": 0,
        }
    ]
    edges: list[dict[str, Any]] = []

    stages_seen: dict[str, str] = {}
    topic_ids_in_outline: set[str] = set()

    for topic in outline:
        stage_key = topic.stage.value
        stage_node_id = f"stage:{stage_key}"
        if stage_key not in stages_seen:
            stages_seen[stage_key] = stage_node_id
            nodes.append(
                {
                    "id": stage_node_id,
                    "kind": "stage",
                    "label": STAGE_LABELS_RU.get(stage_key, stage_key),
                    "parent": project_node_id,
                    "level": 1,
                    "stage": stage_key,
                    "child_count": 0,
                }
            )
            edges.append(
                {
                    "id": f"struct:{project_node_id}:{stage_node_id}",
                    "from": project_node_id,
                    "to": stage_node_id,
                    "kind": "structure",
                }
            )
        topic_node_id = f"topic:{topic.id}"
        topic_ids_in_outline.add(topic.id)
        nodes.append(
            {
                "id": topic_node_id,
                "kind": "topic",
                "label": topic.title_ru,
                "parent": stage_node_id,
                "level": 2,
                "topic_id": topic.id,
                "stage": stage_key,
                "child_count": 0,
            }
        )
        edges.append(
            {
                "id": f"struct:{stage_node_id}:{topic_node_id}",
                "from": stage_node_id,
                "to": topic_node_id,
                "kind": "structure",
            }
        )

    def ensure_unscoped() -> tuple[str, str]:
        stage_node_id = f"stage:{UNSCOPED_STAGE_ID}"
        topic_node_id = f"topic:{UNSCOPED_TOPIC_ID}"
        if UNSCOPED_STAGE_ID not in stages_seen:
            stages_seen[UNSCOPED_STAGE_ID] = stage_node_id
            nodes.append(
                {
                    "id": stage_node_id,
                    "kind": "stage",
                    "label": "Прочие",
                    "parent": project_node_id,
                    "level": 1,
                    "stage": UNSCOPED_STAGE_ID,
                    "child_count": 0,
                }
            )
            edges.append(
                {
                    "id": f"struct:{project_node_id}:{stage_node_id}",
                    "from": project_node_id,
                    "to": stage_node_id,
                    "kind": "structure",
                }
            )
            nodes.append(
                {
                    "id": topic_node_id,
                    "kind": "topic",
                    "label": "Без раздела",
                    "parent": stage_node_id,
                    "level": 2,
                    "topic_id": UNSCOPED_TOPIC_ID,
                    "stage": UNSCOPED_STAGE_ID,
                    "child_count": 0,
                }
            )
            edges.append(
                {
                    "id": f"struct:{stage_node_id}:{topic_node_id}",
                    "from": stage_node_id,
                    "to": topic_node_id,
                    "kind": "structure",
                }
            )
        return stage_node_id, topic_node_id

    by_id = {n["id"]: n for n in nodes}

    for req in requirements:
        payload = req.payload or {}
        topic_id = str(payload.get("topic_id") or "")
        if topic_id and topic_id in topic_ids_in_outline:
            parent_id = f"topic:{topic_id}"
        elif topic_id and topic_by_id(topic_id, plan.extra_topics):
            # Topic exists in catalog but not current outline — still attach if we add it.
            parent_id = f"topic:{topic_id}"
            if parent_id not in by_id:
                _, parent_id = ensure_unscoped()
                parent_id = f"topic:{UNSCOPED_TOPIC_ID}"
        else:
            _, parent_id = ensure_unscoped()
            parent_id = f"topic:{UNSCOPED_TOPIC_ID}"

        display = normalize_requirement_status(req.status)
        has_conflict = display == "conflict" or req.id in conflict_ids
        node = {
            "id": str(req.id),
            "kind": "requirement",
            "label": _requirement_label(req),
            "parent": parent_id,
            "level": 3,
            "status": display,
            "is_new": display == "new",
            "has_conflict": has_conflict,
            "topic_id": topic_id or None,
            "stage": payload.get("stage"),
        }
        nodes.append(node)
        by_id[node["id"]] = node
        edges.append(
            {
                "id": f"struct:{parent_id}:{req.id}",
                "from": parent_id,
                "to": str(req.id),
                "kind": "structure",
            }
        )

    child_counts: dict[str, int] = {}
    for node in nodes:
        parent = node.get("parent")
        if parent:
            child_counts[parent] = child_counts.get(parent, 0) + 1
    for node in nodes:
        if node["kind"] in {"project", "stage", "topic"}:
            node["child_count"] = child_counts.get(node["id"], 0)

    for rel_type in ("depends_on", "conflicts_with"):
        for rel in kg.list_relations(project.id, type_=rel_type):
            edges.append(
                {
                    "id": str(rel.id),
                    "from": str(rel.from_entity_id),
                    "to": str(rel.to_entity_id),
                    "kind": rel_type,
                }
            )

    return {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "status": project.status.value,
            "product_type": project.product_type,
            "estimate": estimate_console_panel(estimate_project(kg, project)),
        },
        "nodes": nodes,
        "edges": edges,
    }
