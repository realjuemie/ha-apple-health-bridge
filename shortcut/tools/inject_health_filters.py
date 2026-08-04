#!/usr/bin/env python3
"""Inject canonical HealthKit filter parameters into a Cherri plist."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import plistlib
import uuid
from typing import Any


METRICS: dict[str, dict[str, Any]] = {
    # Health sample types are localized enum values in Shortcuts.  This bridge
    # targets Simplified Chinese iOS, so use the names searchable in its editor.
    "steps": {"type": "步数", "days": 1, "group": "Day", "limit": 1},
    "walking_running_distance": {
        "type": "步行+跑步距离",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
    "active_energy": {
        "type": "活动能量",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
    "exercise_minutes": {
        "type": "锻炼分钟数",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
    "stand_hours": {
        "type": "站立小时数",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
    "heart_rate": {"type": "心率", "days": 7, "limit": 1},
    "resting_heart_rate": {
        "type": "静息心率",
        "days": 7,
        "limit": 1,
    },
    "blood_oxygen": {"type": "血氧饱和度", "days": 7, "limit": 1},
    "respiratory_rate": {
        "type": "呼吸频率",
        "days": 7,
        "limit": 1,
    },
    "sleep_duration": {"type": "睡眠", "days": 2},
    "weight": {"type": "体重", "days": 30, "limit": 1},
    "body_fat_percentage": {
        "type": "体脂百分比",
        "days": 30,
        "limit": 1,
    },
    "floors_climbed": {
        "type": "爬楼层数",
        "days": 1,
        "group": "Day",
        "limit": 1,
    },
}

# Stored values for the HealthKit type picker. These are intentionally not
# localized display labels: Shortcuts persists this canonical enumeration even
# when its interface language is Chinese.
_HEALTH_TYPE_ENUMERATIONS = {
    "steps": "Steps",
    "walking_running_distance": "Walking + Running Distance",
    "active_energy": "Active Calories",
    "exercise_minutes": "Exercise Time",
    "stand_hours": "Stand Time",
    "heart_rate": "Heart Rate",
    "resting_heart_rate": "Resting Heart Rate",
    "blood_oxygen": "Oxygen Saturation",
    "respiratory_rate": "Respiratory Rate",
    "sleep_duration": "Sleep",
    "weight": "Weight",
    "body_fat_percentage": "Body Fat Percentage",
    "floors_climbed": "Flights Climbed",
}
for _metric_key, _type_name in _HEALTH_TYPE_ENUMERATIONS.items():
    METRICS[_metric_key]["type"] = _type_name

AUTHORIZATION_KEY = "authorize_all"

# Form fields are deliberately flat: this transport is supported by all
# Shortcuts versions that support Get Contents of URL, unlike the unavailable
# dictionary-to-JSON action used by the previous package.
FORM_VALUE_OUTPUTS = {
    "steps": "StepsValue",
    "walking_running_distance": "DistanceValue",
    "active_energy": "EnergyValue",
    "exercise_minutes": "ExerciseValue",
    "stand_hours": "StandValue",
    "heart_rate": "HeartRateValue",
    "resting_heart_rate": "RestingHeartRateValue",
    "blood_oxygen": "BloodOxygenValue",
    "respiratory_rate": "RespiratoryRateValue",
    "sleep_duration": "SleepValue",
    "weight": "WeightValue",
    "body_fat_percentage": "BodyFatValue",
    "floors_climbed": "FloorsValue",
    "latitude": "LatitudeValue",
    "longitude": "LongitudeValue",
    "altitude": "AltitudeValue",
    "ssid": "WifiNameValue",
    "bssid": "BssidValue",
}

SUM_OUTPUTS = {"StepsValue", "DistanceValue", "StandValue"}


def _form_item(key: str, value: dict[str, Any], item_type: int = 0) -> dict[str, Any]:
    return {
        "WFItemType": item_type,
        "WFKey": {"Value": {"string": key}, "WFSerializationType": "WFTextTokenString"},
        "WFValue": {"Value": value, "WFSerializationType": "WFTextTokenAttachment"},
    }


def _token(value: dict[str, Any]) -> dict[str, Any]:
    return {"Value": value, "WFSerializationType": "WFTextTokenAttachment"}


def _inject_selection_persistence(shortcut: dict[str, Any]) -> None:
    """Persist the first multi-selection in the iOS Shortcuts password store."""
    actions = shortcut.get("WFWorkflowActions", [])
    choose_index = next(
        (i for i, a in enumerate(actions)
         if a.get("WFWorkflowActionIdentifier") == "is.workflow.actions.choosefromlist"),
        None,
    )
    if choose_index is None:
        raise ValueError("Selection chooser action not found")
    if any(a.get("WFWorkflowActionIdentifier") == "is.workflow.actions.getpassword" for a in actions):
        return
    group = str(uuid.uuid4())
    get_uuid = str(uuid.uuid4())
    get_action = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.getpassword",
        "WFWorkflowActionParameters": {
            "WFPasswordKey": "AppleHealthBridgeSelection",
            "CustomOutputName": "SavedSelection",
            "UUID": get_uuid,
        },
    }
    if_action = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": group,
            "WFCondition": 100,
            "WFControlFlowMode": 0,
            "WFInput": {"Type": "Variable", "Variable": _token({"OutputUUID": get_uuid, "Type": "ActionOutput", "OutputName": "Password"})},
        },
    }
    saved_text_uuid = str(uuid.uuid4())
    saved_text = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.detect.text",
        "WFWorkflowActionParameters": {
            "CustomOutputName": "SavedSelectionText",
            "UUID": saved_text_uuid,
            "WFInput": _token({"OutputUUID": get_uuid, "Type": "ActionOutput", "OutputName": "Password"}),
        },
    }
    saved_var = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
        "WFWorkflowActionParameters": {
            "WFVariableName": "Selected",
            "WFInput": _token({"OutputUUID": saved_text_uuid, "Type": "ActionOutput", "OutputName": "SavedSelectionText"}),
        },
    }
    otherwise = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {"GroupingIdentifier": group, "WFControlFlowMode": 1},
    }
    end = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {"GroupingIdentifier": group, "WFControlFlowMode": 2, "UUID": str(uuid.uuid4())},
    }
    # Existing chooser/text/set-variable actions become the otherwise branch.
    for action in actions[choose_index:choose_index + 3]:
        action.setdefault("WFWorkflowActionParameters", {})["GroupingIdentifier"] = group
    chooser_params = actions[choose_index].setdefault("WFWorkflowActionParameters", {})
    chooser_params.pop("WFControlFlowMode", None)
    selection_set_uuid = actions[choose_index + 2]["WFWorkflowActionParameters"].get("UUID", str(uuid.uuid4()))
    save_action = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.setpassword",
        "WFWorkflowActionParameters": {
            "WFPasswordKey": "AppleHealthBridgeSelection",
            "WFPasswordValue": _token({"Type": "Variable", "VariableName": "Selected"}),
            "UUID": str(uuid.uuid4()),
        },
    }
    actions[choose_index + 2]["WFWorkflowActionParameters"]["UUID"] = selection_set_uuid
    actions[choose_index + 3:choose_index + 3] = [save_action, end]
    actions[choose_index:choose_index] = [get_action, if_action, saved_text, saved_var, otherwise]


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


def _authorization_params(existing: dict[str, Any]) -> dict[str, Any]:
    """Build one lightweight query that declares every supported Health type.

    Shortcuts uses the static type predicates to determine which Health data the
    shortcut needs. Keeping all types in one action makes iOS present the Health
    authorization request at the beginning instead of while each metric runs.
    """
    preserved = {
        key: deepcopy(value)
        for key, value in existing.items()
        if key in {"UUID", "CustomOutputName"}
    }
    preserved["WFContentItemFilter"] = {
        "Value": {
            "WFActionParameterFilterPrefix": 0,
            "WFActionParameterFilterTemplates": [
                _type_filter(spec["type"]) for spec in METRICS.values()
            ],
            "WFContentPredicateBoundedDate": False,
        },
        "WFSerializationType": "WFContentPredicateTableTemplate",
    }
    preserved["WFContentItemSortProperty"] = "Start Date"
    preserved["WFContentItemSortOrder"] = "Latest First"
    preserved["WFContentItemLimitEnabled"] = True
    preserved["WFContentItemLimitNumber"] = 1
    return preserved


def inject(source: Path, destination: Path) -> tuple[int, int]:
    with source.open("rb") as file_handle:
        shortcut = plistlib.load(file_handle)

    _inject_selection_persistence(shortcut)

    found: set[str] = set()
    post_actions = 0
    post_action_index: int | None = None
    form_output_ids: dict[str, str] = {}
    health_detail_actions = 0
    authorization_actions = 0
    dictionary_writes = 0
    measurement_conversions = 0
    sum_actions = 0
    for action_index, action in enumerate(shortcut.get("WFWorkflowActions", [])):
        identifier = action.get("WFWorkflowActionIdentifier")
        params = action.get("WFWorkflowActionParameters", {})
        if (
            identifier == "is.workflow.actions.detect.number"
            and params.get("CustomOutputName") in SUM_OUTPUTS
        ):
            # HealthKit returns multiple samples for these daily quantities.
            # Get Numbers keeps the list/last sample; Statistics Sum produces
            # the actual day total while preserving the existing input token.
            action["WFWorkflowActionIdentifier"] = "is.workflow.actions.statistics"
            params["WFStatisticsOperation"] = "Sum"
            sum_actions += 1
        output_name = params.get("CustomOutputName")
        if output_name in FORM_VALUE_OUTPUTS.values():
            form_output_ids[output_name] = params["UUID"]

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
            missing_outputs = set(FORM_VALUE_OUTPUTS.values()) - set(form_output_ids)
            if missing_outputs:
                raise ValueError(f"Missing form value outputs: {sorted(missing_outputs)}")
            params.pop("WFHTTPBodyFile", None)
            params.pop("WFJSONValues", None)
            # The server defaults the protocol version to 1.  Do not emit a
            # static form value here: iOS treats it as a magic variable in a
            # form field, showing "unknown variable" and corrupting the POST.
            items: list[dict[str, Any]] = []
            for key, output_name in FORM_VALUE_OUTPUTS.items():
                items.append(_form_item(key, {
                    "Type": "ActionOutput",
                    "OutputUUID": form_output_ids[output_name],
                    "OutputName": output_name,
                }))
            params["WFFormValues"] = {
                "Value": {"WFDictionaryFieldValueItems": items},
                "WFSerializationType": "WFDictionaryFieldValue",
            }
            params["WFHTTPMethod"] = "POST"
            params["WFHTTPBodyType"] = "Form"
            post_actions += 1
            post_action_index = action_index

        if identifier == "is.workflow.actions.setvalueforkey":
            dictionary_writes += 1
            dictionary_value = params.get("WFDictionaryValue", {})
            if dictionary_value.get("WFSerializationType") != "WFTextTokenString":
                raise ValueError("Dictionary value is not a native magic-variable token")
            token = dictionary_value.get("Value", {})
            attachments = token.get("attachmentsByRange", {})
            if token.get("string") != "\ufffc" or set(attachments) != {"{0, 1}"}:
                raise ValueError("Dictionary value contains an invalid magic-variable token")

        if identifier == "is.workflow.actions.measurement.convert":
            measurement_conversions += 1

        if identifier != "is.workflow.actions.filter.health.quantity":
            continue
        metric_key = params.get("AHBMetric")
        if metric_key == AUTHORIZATION_KEY:
            action["WFWorkflowActionParameters"] = _authorization_params(params)
            authorization_actions += 1
            continue
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
    if sum_actions != 3:
        raise ValueError(f"Expected three daily sum actions, found {sum_actions}")
    if authorization_actions != 1:
        raise ValueError(
            f"Expected one consolidated Health authorization action, "
            f"found {authorization_actions}"
        )
    # Every metric reads Value (or Duration for Sleep); all non-Sleep metrics
    # also read Unit so values are never coerced through Convert Measurement.
    expected_health_details = len(METRICS) + len(METRICS) - 1
    if health_detail_actions != expected_health_details:
        raise ValueError(
            f"Expected {expected_health_details} Health detail actions, "
            f"found {health_detail_actions}"
        )
    if dictionary_writes != 47:
        raise ValueError(f"Expected 47 dictionary writes, found {dictionary_writes}")
    if measurement_conversions:
        raise ValueError(
            f"Expected no Convert Measurement actions, found {measurement_conversions}"
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
