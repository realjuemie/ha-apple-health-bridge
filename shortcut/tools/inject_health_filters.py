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
    # Steps and distance are intentionally left ungrouped. We inspect each
    # raw sample's Source and choose one source before writing the total.
    "steps": {"type": "步数", "today": True},
    "walking_running_distance": {
        "type": "步行+跑步距离",
        "today": True,
    },
    "active_energy": {
        "type": "活动能量",
        "today": True,
        "group": "Day",
    },
    "exercise_minutes": {
        "type": "锻炼分钟数",
        "today": True,
        "group": "Day",
    },
    "stand_hours": {
        "type": "站立小时数",
        "today": True,
        "group": "Day",
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

# These metrics are cumulative and are commonly written by both an iPhone and
# an Apple Watch.  Shortcuts exposes the raw samples from every source, while
# the Health app de-duplicates them.  The Source value is the user's actual
# iPhone name (and can be customized), not the literal string ``iPhone``.  The
# injector therefore compares Source against the runtime device name for the
# remaining cumulative metrics. Steps and distance are de-duplicated in the
# shortcut by inspecting every raw sample, so they do not need a Source query.
SOURCE_FALLBACK_OUTPUTS = {
    "EnergySamples",
    "ExerciseSamples",
    "StandSamples",
}

def _form_item(key: str, value: dict[str, Any], item_type: int = 0) -> dict[str, Any]:
    return {
        "WFItemType": item_type,
        "WFKey": {"Value": {"string": key}, "WFSerializationType": "WFTextTokenString"},
        "WFValue": {"Value": value, "WFSerializationType": "WFTextTokenAttachment"},
    }


def _token(value: dict[str, Any]) -> dict[str, Any]:
    return {"Value": value, "WFSerializationType": "WFTextTokenAttachment"}


def _url_token(output_uuid: str, output_name: str) -> dict[str, Any]:
    """Build the text-token format expected by Get Contents of URL."""
    return {
        "Value": {
            "attachmentsByRange": {
                "{0, 1}": {
                    "OutputName": output_name,
                    "OutputUUID": output_uuid,
                    "Type": "ActionOutput",
                }
            },
            "string": "\ufffc",
        },
        "WFSerializationType": "WFTextTokenString",
    }


def _inject_selection_persistence(shortcut: dict[str, Any]) -> None:
    """Persist the first multi-selection through the HA webhook."""
    actions = shortcut.get("WFWorkflowActions", [])
    choose_index = next(
        (i for i, a in enumerate(actions)
         if a.get("WFWorkflowActionIdentifier") == "is.workflow.actions.choosefromlist"),
        None,
    )
    if choose_index is None:
        raise ValueError("Selection chooser action not found")
    if any(a.get("WFWorkflowActionIdentifier") == "is.workflow.actions.downloadurl" and a.get("WFWorkflowActionParameters", {}).get("CustomOutputName") == "ConfigResponse" for a in actions):
        return
    group = str(uuid.uuid4())
    endpoint = next(
        (
            action
            for action in actions
            if action.get("WFWorkflowActionParameters", {}).get("CustomOutputName")
            == "HAEndpoint"
        ),
        None,
    )
    if endpoint is None:
        raise ValueError("Compiled Webhook text action not found")
    endpoint_uuid = endpoint["WFWorkflowActionParameters"]["UUID"]
    url_token = _url_token(endpoint_uuid, "HAEndpoint")
    get_uuid = str(uuid.uuid4())
    get_action = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "WFURL": url_token,
            "WFHTTPMethod": "GET",
            "CustomOutputName": "ConfigResponse",
            "UUID": get_uuid,
        },
    }
    text_uuid = str(uuid.uuid4())
    saved_text = {"WFWorkflowActionIdentifier": "is.workflow.actions.detect.text", "WFWorkflowActionParameters": {"CustomOutputName": "ConfigText", "UUID": text_uuid, "WFInput": _token({"OutputUUID": get_uuid, "Type": "ActionOutput", "OutputName": "Content"})}}
    if_action = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
        "WFWorkflowActionParameters": {
            "GroupingIdentifier": group,
            # 4 is the native Shortcuts "is" string comparison.  100 means
            # "has any value", which incorrectly opened the chooser forever.
            "WFCondition": 4,
            "WFControlFlowMode": 0,
            "WFConditionalActionString": "__AHB_SETUP_REQUIRED__",
            "WFInput": {
                "Type": "Variable",
                "Variable": _token(
                    {
                        "OutputUUID": text_uuid,
                        "Type": "ActionOutput",
                        "OutputName": "ConfigText",
                    }
                ),
            },
        },
    }
    saved_var = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
        "WFWorkflowActionParameters": {
            "WFVariableName": "Selected",
            "WFInput": _token(
                {
                    "OutputUUID": text_uuid,
                    "Type": "ActionOutput",
                    "OutputName": "ConfigText",
                }
            ),
            "GroupingIdentifier": group,
            "UUID": str(uuid.uuid4()),
        },
    }
    save_selection = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
        "WFWorkflowActionParameters": {
            "WFURL": url_token,
            "WFHTTPMethod": "POST",
            "WFHTTPBodyType": "Form",
            "WFFormValues": {
                "Value": {
                    "WFDictionaryFieldValueItems": [
                        _form_item(
                            "selection",
                            {"Type": "Variable", "VariableName": "Selected"},
                        )
                    ]
                },
                "WFSerializationType": "WFDictionaryFieldValue",
            },
            "CustomOutputName": "ConfigSaveResponse",
            "UUID": str(uuid.uuid4()),
            "GroupingIdentifier": group,
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
    actions[choose_index + 2]["WFWorkflowActionParameters"]["UUID"] = selection_set_uuid
    actions[choose_index + 3:choose_index + 3] = [
        save_selection,
        otherwise,
        saved_var,
        end,
    ]
    actions[choose_index:choose_index] = [get_action, saved_text, if_action]
    for action in actions:
        params = action.get("WFWorkflowActionParameters") or {}
        if params.get("CustomOutputName") == "ServerResponse":
            params["WFURL"] = url_token


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


def _today_filter() -> dict[str, Any]:
    """Return the native HealthKit predicate for the current calendar day.

    ``1001`` means "in the last N days", which is a rolling 24-hour window.
    Shortcuts exports ``1002`` for the Health filter labelled "today".  The
    Number/Unit pair is retained because iOS includes it in exported filters.
    """
    return {
        "Bounded": True,
        "Operator": 1002,
        "Property": "Start Date",
        "Removable": False,
        "Values": {"Number": "1", "Unit": 16},
    }


def _source_not_current_device_filter(
    device_uuid: str, device_name: str = "CurrentDeviceName"
) -> dict[str, Any]:
    """Match samples whose source is not the device running the shortcut.

    ``HKSource.name`` follows the user's device name, so a literal ``iPhone``
    does not match phones renamed by their owner.  Shortcuts supports a text
    token in predicate values; using the Get Device Details output keeps this
    filter valid for renamed phones and iPhone-only installations.
    """
    return {
        "Bounded": True,
        "Operator": 5,
        "Property": "Source",
        "Removable": False,
        "Values": {
            "String": {
                "Value": {
                    "attachmentsByRange": {
                        "{0, 1}": {
                            "OutputUUID": device_uuid,
                            "OutputName": device_name,
                            "Type": "ActionOutput",
                        }
                    },
                    "string": "\ufffc",
                },
                "WFSerializationType": "WFTextTokenString",
            },
            "Unit": 4,
        },
    }


def _output_ref(output_uuid: str, output_name: str) -> dict[str, Any]:
    return {
        "OutputUUID": output_uuid,
        "OutputName": output_name,
        "Type": "ActionOutput",
    }


def _condition_output_input(output_uuid: str, output_name: str) -> dict[str, Any]:
    return {
        "Type": "Variable",
        "Variable": _token(_output_ref(output_uuid, output_name)),
    }


def _replace_output_with_variable(
    value: Any, output_uuid: str, output_name: str, variable_name: str
) -> None:
    """Replace a magic action-output reference with a variable reference."""
    if isinstance(value, dict):
        if (
            value.get("OutputUUID") == output_uuid
            and value.get("OutputName") == output_name
            and value.get("Type") == "ActionOutput"
        ):
            value.clear()
            value.update({"Type": "Variable", "VariableName": variable_name})
            return
        for child in value.values():
            _replace_output_with_variable(child, output_uuid, output_name, variable_name)
    elif isinstance(value, list):
        for child in value:
            _replace_output_with_variable(child, output_uuid, output_name, variable_name)


def _contains_output_ref(value: Any, output_uuid: str, output_name: str) -> bool:
    if isinstance(value, dict):
        if (
            value.get("OutputUUID") == output_uuid
            and value.get("OutputName") == output_name
            and value.get("Type") == "ActionOutput"
        ):
            return True
        return any(
            _contains_output_ref(child, output_uuid, output_name)
            for child in value.values()
        )
    if isinstance(value, list):
        return any(_contains_output_ref(child, output_uuid, output_name) for child in value)
    return False


def _source_fallback_actions(
    preferred_uuid: str,
    preferred_name: str,
    all_uuid: str,
    all_name: str,
    variable_name: str,
    grouping_identifier: str,
) -> list[dict[str, Any]]:
    """Build If/Otherwise actions selecting preferred or fallback samples."""
    return [
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": grouping_identifier,
                "WFCondition": 100,
                "WFControlFlowMode": 0,
                "WFInput": _condition_output_input(preferred_uuid, preferred_name),
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": variable_name,
                "WFInput": _token(_output_ref(preferred_uuid, preferred_name)),
                "GroupingIdentifier": grouping_identifier,
                "UUID": str(uuid.uuid4()),
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": grouping_identifier,
                "WFControlFlowMode": 1,
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": variable_name,
                "WFInput": _token(_output_ref(all_uuid, all_name)),
                "GroupingIdentifier": grouping_identifier,
                "UUID": str(uuid.uuid4()),
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": grouping_identifier,
                "WFControlFlowMode": 2,
                "UUID": str(uuid.uuid4()),
            },
        },
    ]


def _inject_source_fallbacks(shortcut: dict[str, Any]) -> int:
    """Prefer non-iPhone samples, with an iPhone-only fallback."""
    actions = shortcut.get("WFWorkflowActions", [])
    device_uuid = str(uuid.uuid4())
    device_action = {
        "WFWorkflowActionIdentifier": "is.workflow.actions.getdevicedetails",
        "WFWorkflowActionParameters": {
            "WFDeviceDetail": "Device Name",
            "CustomOutputName": "CurrentDeviceName",
            "UUID": device_uuid,
        },
    }
    authorization_index = next(
        (
            i
            for i, action in enumerate(actions)
            if action.get("WFWorkflowActionIdentifier")
            == "is.workflow.actions.filter.health.quantity"
            and action.get("WFWorkflowActionParameters", {}).get("CustomOutputName")
            == "HealthAuthorization"
        ),
        None,
    )
    if authorization_index is None:
        raise ValueError("Consolidated Health authorization action not found")
    actions.insert(authorization_index + 1, device_action)
    injected = 0
    for base_name in SOURCE_FALLBACK_OUTPUTS:
        preferred = next(
            (
                action
                for action in actions
                if action.get("WFWorkflowActionIdentifier")
                == "is.workflow.actions.filter.health.quantity"
                and action.get("WFWorkflowActionParameters", {}).get("CustomOutputName")
                == base_name
            ),
            None,
        )
        if preferred is None:
            raise ValueError(f"Missing cumulative Health filter: {base_name}")
        preferred_params = preferred["WFWorkflowActionParameters"]
        preferred_uuid = preferred_params["UUID"]
        preferred_name = f"{base_name}Preferred"
        all_name = f"{base_name}All"
        variable_name = f"{base_name}Selected"

        all_action = deepcopy(preferred)
        all_params = all_action["WFWorkflowActionParameters"]
        all_uuid = str(uuid.uuid4())
        all_params["UUID"] = all_uuid
        all_params["CustomOutputName"] = all_name

        templates = preferred_params["WFContentItemFilter"]["Value"][
            "WFActionParameterFilterTemplates"
        ]
        if not any(row.get("Property") == "Source" for row in templates):
            templates.insert(1, _source_not_current_device_filter(device_uuid))
        preferred_params["CustomOutputName"] = preferred_name

        preferred_index = actions.index(preferred)
        target_index = next(
            (
                i
                for i in range(preferred_index + 1, len(actions))
                if actions[i].get("WFWorkflowActionIdentifier")
                == "is.workflow.actions.conditional"
                and _contains_output_ref(
                    actions[i].get("WFWorkflowActionParameters", {}),
                    preferred_uuid,
                    base_name,
                )
            ),
            None,
        )
        if target_index is None:
            raise ValueError(f"Missing cumulative condition for {base_name}")

        # Downstream actions consume the selected variable instead of the
        # preferred query directly.  The variable is set by the fallback
        # branch immediately before the existing metric condition.
        end_index = next(
            (
                i
                for i in range(target_index + 1, len(actions))
                if actions[i].get("WFWorkflowActionIdentifier")
                == "is.workflow.actions.filter.health.quantity"
            ),
            len(actions),
        )
        for action in actions[target_index:end_index]:
            _replace_output_with_variable(
                action.get("WFWorkflowActionParameters", {}),
                preferred_uuid,
                base_name,
                variable_name,
            )

        fallback_group = str(uuid.uuid4())
        additions = [all_action] + _source_fallback_actions(
            preferred_uuid,
            preferred_name,
            all_uuid,
            all_name,
            variable_name,
            fallback_group,
        )
        actions[target_index:target_index] = additions
        injected += 1
    return injected


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
                _today_filter() if spec.get("today") else _recent_filter(spec["days"]),
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
    # HealthKit's Day grouping returns the daily aggregate directly.  Do not
    # add a second Statistics action: on current iOS it can return an empty
    # value when fed Health quantity conversions.

    found: set[str] = set()
    post_actions = 0
    post_action_index: int | None = None
    form_output_ids: dict[str, str] = {}
    health_detail_actions = 0
    authorization_actions = 0
    dictionary_writes = 0
    measurement_conversions = 0
    for action_index, action in enumerate(shortcut.get("WFWorkflowActions", [])):
        identifier = action.get("WFWorkflowActionIdentifier")
        params = action.get("WFWorkflowActionParameters", {})
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
            # A fixed unit (steps/km) is emitted as an ordinary string by
            # Cherri. Other fields use native magic-variable tokens.
            if isinstance(dictionary_value, str):
                continue
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

    source_fallbacks = _inject_source_fallbacks(shortcut)

    missing = set(METRICS) - found
    if missing:
        raise ValueError(f"Missing HealthKit placeholders: {sorted(missing)}")
    if post_actions != 1:
        raise ValueError(f"Expected one JSON POST action, found {post_actions}")
    if source_fallbacks != len(SOURCE_FALLBACK_OUTPUTS):
        raise ValueError(
            f"Expected {len(SOURCE_FALLBACK_OUTPUTS)} source fallbacks, "
            f"found {source_fallbacks}"
        )
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
    if len(questions) != 1 or questions[0].get("ParameterKey") != "WFTextActionText":
        raise ValueError("Expected one Webhook URL import question")
    # The imported webhook URL belongs to the shared URL action used by both
    # the configuration GET and the data POST.
    endpoint_index = next(
        (
            i
            for i, action in enumerate(shortcut["WFWorkflowActions"])
            if action.get("WFWorkflowActionParameters", {}).get("CustomOutputName")
            == "HAEndpoint"
        ),
        None,
    )
    if endpoint_index is None:
        raise ValueError("Shared HA endpoint action not found")
    questions[0]["ActionIndex"] = endpoint_index
    questions[0]["ParameterKey"] = "WFTextActionText"
    questions[0]["DefaultValue"] = ""

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
