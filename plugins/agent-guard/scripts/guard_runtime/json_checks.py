"""共享 JSON check（JSON 检查）能力。"""

from __future__ import annotations

from typing import Any


JSON_PREDICATES = {
    "exists",
    "equals",
    "not_equals",
    "number_lte",
    "number_gte",
    "array_none",
    "array_all",
}

VALUE_PREDICATES = {"equals", "not_equals", "number_lte", "number_gte"}
ARRAY_PREDICATES = {"array_none", "array_all"}

MISSING_JSON_VALUE = object()


def json_field(data: Any, field: str, default: Any = MISSING_JSON_VALUE) -> Any:
    current = data
    for part in field.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def _is_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


def evaluate_json_predicate(actual: Any, predicate: str, expected: Any = None, where: dict[str, Any] | None = None) -> bool:
    if predicate == "exists":
        return actual is not MISSING_JSON_VALUE
    if predicate == "equals":
        return actual == expected
    if predicate == "not_equals":
        return actual != expected
    if predicate == "number_lte":
        return _is_number(actual) and _is_number(expected) and actual <= expected
    if predicate == "number_gte":
        return _is_number(actual) and _is_number(expected) and actual >= expected
    if predicate in ARRAY_PREDICATES:
        if not isinstance(actual, list) or not isinstance(where, dict):
            return False
        child_field = where.get("field")
        child_predicate = where.get("predicate")
        if not isinstance(child_field, str) or not isinstance(child_predicate, str):
            return False
        results = [
            evaluate_json_predicate(
                json_field(item, child_field),
                child_predicate,
                where.get("value"),
                where.get("where"),
            )
            for item in actual
        ]
        return not any(results) if predicate == "array_none" else all(results)
    return False
