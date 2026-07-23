from pathlib import Path

import pytest

from app.database import Database
from app.llm_capability_service import (
    CapabilityLLMService,
    DeepSeekClient,
    LLMCapabilityError,
    LLMExtractionRetry,
)


def service() -> CapabilityLLMService:
    return CapabilityLLMService(
        Database(Path("unused.db")),
        DeepSeekClient("", "https://api.deepseek.com", "deepseek-v4-flash", 30),
    )


def taxonomy():
    directions = [
        {
            "id": 3,
            "code": "CD3",
            "name": "工程开发能力",
            "categories": [
                {
                    "id": 31,
                    "code": "C3.1",
                    "name": "软件工程",
                    "directionCode": "CD3",
                }
            ],
        }
    ]
    categories = {"C3.1": directions[0]["categories"][0]}
    return directions, categories


def valid_payload():
    return {
        "schema_version": "1.0",
        "capabilities": [
            {
                "surface_name": "ROS2",
                "proposed_canonical_name": "机器人操作系统开发",
                "description": "使用ROS2开发机器人软件节点与通信功能。",
                "level1": {"code": "CD3", "name": "工程开发能力"},
                "level2": {
                    "selection": "existing",
                    "code": "C3.1",
                    "name": "软件工程",
                    "proposed_description": None,
                },
                "requirement_level": "required",
                "evidence": [
                    {
                        "text": "熟练使用ROS2开发机器人节点",
                        "section": "requirements",
                    }
                ],
                "llm_assessment": {
                    "extraction_confidence": 0.96,
                    "classification_confidence": 0.91,
                },
            }
        ],
    }


def test_validates_grounded_structured_extraction():
    directions, categories = taxonomy()
    items = service()._validate_extraction(
        valid_payload(),
        "岗位要求：熟练使用ROS2开发机器人节点",
        directions,
        categories,
    )
    assert items[0]["direction_code"] == "CD3"
    assert items[0]["category_id"] == 31
    assert items[0]["evidence_text"] == "熟练使用ROS2开发机器人节点"
    assert items[0]["evidence_items"][0]["source_field"] == "combined_text"
    assert items[0]["evidence_items"][0]["start_offset"] == 5


def test_preserves_multiple_grounded_evidence_details():
    directions, categories = taxonomy()
    payload = valid_payload()
    payload["capabilities"][0]["evidence"].append(
        {"text": "负责ROS2通信模块维护", "section": "responsibilities"}
    )
    items = service()._validate_extraction(
        payload,
        {
            "job_title": "机器人软件工程师",
            "jd_description": "岗位要求：熟练使用ROS2开发机器人节点。负责ROS2通信模块维护。",
            "other_info": "",
        },
        directions,
        categories,
    )
    evidence = items[0]["evidence_items"]
    assert len(evidence) == 2
    assert evidence[0]["source_field"] == "jd_description"
    assert evidence[1]["source_field"] == "jd_description"
    assert evidence[1]["start_offset"] == 21
    assert evidence[1]["end_offset"] == 21 + len("负责ROS2通信模块维护")


def test_rejects_evidence_not_present_in_jd():
    directions, categories = taxonomy()
    payload = valid_payload()
    payload["capabilities"][0]["evidence"][0]["text"] = "精通不存在的技能"
    with pytest.raises(LLMCapabilityError, match="证据无法"):
        service()._validate_extraction(
            payload,
            "岗位要求：熟练使用ROS2开发机器人节点",
            directions,
            categories,
        )


def test_rejects_cross_direction_existing_category():
    directions, categories = taxonomy()
    payload = valid_payload()
    payload["capabilities"][0]["level1"]["code"] = "CD2"
    directions.append({"id": 2, "code": "CD2", "name": "研究与算法能力", "categories": []})
    with pytest.raises(LLMCapabilityError, match="跨一级方向"):
        service()._validate_extraction(
            payload,
            "岗位要求：熟练使用ROS2开发机器人节点",
            directions,
            categories,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("extraction_confidence", 0.89),
        ("classification_confidence", 0.899),
    ],
)
def test_requests_retry_when_either_confidence_is_below_90_percent(field, value):
    directions, categories = taxonomy()
    payload = valid_payload()
    payload["capabilities"][0]["llm_assessment"][field] = value
    with pytest.raises(LLMExtractionRetry, match="低于90%"):
        service()._validate_extraction(
            payload,
            "岗位要求：熟练使用ROS2开发机器人节点",
            directions,
            categories,
        )


def test_requests_retry_when_canonical_name_has_no_chinese():
    directions, categories = taxonomy()
    payload = valid_payload()
    payload["capabilities"][0]["proposed_canonical_name"] = "ROS2 Development"
    with pytest.raises(LLMExtractionRetry, match="中文"):
        service()._validate_extraction(
            payload,
            "岗位要求：熟练使用ROS2开发机器人节点",
            directions,
            categories,
        )


def test_automation_threshold_boundaries():
    capability_service = service()
    assert capability_service._is_auto_merge(
        {"matched_capability_id": 7, "relation": "same", "confidence": 0.95}
    )
    assert not capability_service._is_auto_merge(
        {"matched_capability_id": 7, "relation": "same", "confidence": 0.949}
    )
    base_item = {"extraction_confidence": 0.95, "category_id": 31}
    assert not capability_service._can_auto_create(base_item, None)
    assert capability_service._can_auto_create(
        {**base_item, "extraction_confidence": 0.951},
        {"matched_capability_id": None, "relation": "different", "confidence": 0.98},
    )
    assert capability_service._can_auto_create(
        {**base_item, "extraction_confidence": 0.99},
        {"matched_capability_id": 7, "relation": "same", "confidence": 0.94},
    )
