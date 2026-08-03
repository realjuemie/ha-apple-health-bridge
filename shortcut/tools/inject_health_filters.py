#!/usr/bin/env python3
"""Inject canonical HealthKit filter parameters into a Cherri plist."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import plistlib
from typing import Any


METRICS: dict[str, dict[str, Any]] = {
    "steps": {"type": "Steps", "days": 1, "group": "Day", "limit": 1},
    "walking_running_distance": {
        "type": "Walking + Running Distance",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
    "active_energy": {
        "type": "Active Energy",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
    "exercise_minutes": {
        "type": "Exercise Time",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
    "stand_hours": {
        "type": "Stand Hours",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
    "heart_rate": {"type": "Heart Rate", "days": 7, "limit": 1},
    "resting_heart_rate": {
        "type": "Resting Heart Rate",
        "days": 7,
        "limit": 1,
    },
    "blood_oxygen": {"type": "Blood Oxygen", "days": 7, "limit": 1},
    "respiratory_rate": {
        "type": "Respiratory Rate",
        "days": 7,
        "limit": 1,
    },
    "sleep_duration": {"type": "Sleep", "days": 2},
    "weight": {"type": "Weight", "days": 30, "limit": 1},
    "body_fat_percentage": {
        "type": "Body Fat Percentage",
        "days": 30,
        "limit": 1,
    },
    "floors_climbed": {
        "type": "Flights Climbed",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
}


def _type_filter(type_name: str) -> dict[str, Any]:
    return {
        "Bounded": True,
        "Operator": 4,
        "Property": "Type",
        "Removable": False,
        "Values": {
            "Enumeration": {
                "Value": type_name,
                "WFSerializationType": "WFStringSubstitutableState",
            }
        },
    }


def _recent_filter(days: int) -> dict[str, Any]:
    return {
        "Bounded": True,
        "Operator": 1001,
        "Property": "Start Date",
        "Removable": False,
        "Values": {"Number": str(days), "Unit": 16},
    }


def _health_params(existing: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    preserved = {
        key: deepcopy(value)
        for key, value in existing.items()
        if key in {"UUID", "CustomOutputName"}
    }
    preserved["WFContentItemFilter"] = {
        "Value": {
            "WFActionParameterFilterPrefix": 1,
            "WFActionParameterFilterTemplates": [
                _type_filter(spec["type"]),
                _recent_filter(spec["days"]),
            ],
            "WFContentPredicateBoundedDate": False,
        },
        "WFSerializationType": "WFContentPredicateTableTemplate",
    }
    preserved["WFContentItemSortProperty"] = "Start Date"
    preserved["WFContentItemSortOrder"] = "Latest First"
    if group := spec.get("group"):
        preserved["WFHKSampleFilteringGroupBy"] = group
        preserved["WFHKSampleFilteringFillMissing"] = False
    if limit := spec.get("limit"):
        preserved["WFContentItemLimitEnabled"] = True
        preserved["WFContentItemLimitNumber"] = limit
    return preserved


def inject(source: Path, destination: Path) -> tuple[int, int]:
    with source.open("rb") as file_handle:
        shortcut = plistlib.load(file_handle)

    found: set[str] = set()
    post_actions = 0
    post_action_index: int | None = None
    health_detail_actions = 0
    for action_index, action in enumerate(shortcut.get("WFWorkflowActions", [])):
        identifier = action.get("WFWorkflowActionIdentifier")
        params = action.get("WFWorkflowActionParameters", {})

        # Cherri 2.3.0 keeps the generic rawaction identifier when rawAction()
        # is assigned to a variable. Restore the intended native action here.
        if identifier == "is.workflow.actions.rawaction":
            if "AHBMetric" in params:
                identifier = "is.workflow.actions.filter.health.quantity"
            elif {"WFInput", "WFContentItemPropertyName"} <= params.keys():
                identifier = "is.workflow.actions.properties.health.quantity"
                health_detail_actions += 1
            elif {"WFURL", "WFJSONValues"} <= params.keys():
                identifier = "is.workflow.actions.downloadurl"
            action["WFWorkflowActionIdentifier"] = identifier

        if (
            identifier == "is.workflow.actions.downloadurl"
            and params.get("CustomOutputName") == "ServerResponse"
        ):
            params["WFJSONValues"] = {
                "Value": {"Type": "Variable", "VariableName": "Payload"},
                "WFSerializationType": "WFTextTokenAttachment",
            }
            params["WFHTTPMethod"] = "POST"
            params["WFHTTPBodyType"] = "JSON"
            post_actions += 1
            post_action_index = action_index

        if identifier != "is.workflow.actions.filter.health.quantity":
            continue
        metric_key = params.get("AHBMetric")
        if metric_key not in METRICS:
            continue
        if metric_key in found:
            raise ValueError(f"Duplicate HealthKit placeholder: {metric_key}")
        action["WFWorkflowActionParameters"] = _health_params(
            params, METRICS[metric_key]
        )
        found.add(metric_key)

    missing = set(METRICS) - found
    if missing:
        raise ValueError(f"Missing HealthKit placeholders: {sorted(missing)}")
    if post_actions != 1:
        raise ValueError(f"Expected one JSON POST action, found {post_actions}")
    if health_detail_actions != 1:
        raise ValueError(
            f"Expected one Health detail action, found {health_detail_actions}"
        )
    raw_actions = sum(
        action.get("WFWorkflowActionIdentifier") == "is.workflow.actions.rawaction"
        for action in shortcut.get("WFWorkflowActions", [])
    )
    if raw_actions:
        raise ValueError(f"Unresolved raw actions remain: {raw_actions}")

    questions = shortcut.get("WFWorkflowImportQuestions", [])
    if len(questions) != 1 or questions[0].get("ParameterKey") != "WFURL":
        raise ValueError("Expected one Webhook URL import question")
    questions[0]["ActionIndex"] = post_action_index

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as file_handle:
        plistlib.dump(shortcut, file_handle, fmt=plistlib.FMT_XML, sort_keys=False)
    return len(found), post_actions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    health_count, post_count = inject(args.source, args.destination)
    print(
        f"Injected {health_count} HealthKit filters and configured "
        f"{post_count} JSON POST action in {args.destination}"
    )


if __name__ == "__main__":
    main()
