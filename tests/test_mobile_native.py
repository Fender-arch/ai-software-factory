"""DEC-010: mobile_native is a first-class factory product type."""

from __future__ import annotations

from types import SimpleNamespace

from core.estimate import base_hours_for
from core.planner import plan_product_tasks
from discovery.interview import _detect_product_type
from discovery.tz_outline import SHAPE_TO_PRODUCT_TYPE, topic_by_id, topics_for


def test_detect_native_app_aliases():
    assert _detect_product_type("Нужно мобильное приложение для записи") == "mobile_native"
    assert _detect_product_type("We need an iOS app") == "mobile_native"
    assert _detect_product_type("android app for drivers") == "mobile_native"
    assert _detect_product_type("Landing page, mobile-friendly") == "website"


def test_shape_mobile_locks_product_type():
    assert SHAPE_TO_PRODUCT_TYPE["shape_mobile"] == "mobile_native"
    assert SHAPE_TO_PRODUCT_TYPE["ctx:shape_android"] == "mobile_native"
    assert SHAPE_TO_PRODUCT_TYPE["ctx:shape_ios"] == "mobile_native"


def test_native_topics_only_for_mobile_type():
    platforms = topic_by_id("native_platforms")
    assert platforms is not None
    assert "mobile_native" in (platforms.applies_to or frozenset())

    native_ids = {t.id for t in topics_for("mobile_native")}
    site_ids = {t.id for t in topics_for("website")}
    assert "native_platforms" in native_ids
    assert "store_distribution" in native_ids
    assert "native_platforms" not in site_ids
    assert "public_identity" in native_ids


def test_planner_emits_native_slices():
    reqs = [SimpleNamespace(id="r1", status="new", payload={"priority": "must"})]
    plan = plan_product_tasks("mobile_native", reqs)
    titles = " ".join(spec.title.lower() for spec in plan)
    assert "native" in titles or "mobile" in titles
    assert any("mobile_native" in " ".join(spec.acceptance_criteria) for spec in plan)
    assert base_hours_for("mobile_native") == 32
