from pathlib import Path

import pytest

from app.career_clustering_service import (
    CareerClusteringRetry,
    CareerClusteringService,
)
from app.database import Database
from app.llm_capability_service import DeepSeekClient, LLMCapabilityError


def service() -> CareerClusteringService:
    return CareerClusteringService(
        Database(Path("unused.db")),
        DeepSeekClient("", "https://api.deepseek.com", "deepseek-v4-flash", 30),
    )


def taxonomy():
    directions = [
        {
            "id": 2,
            "code": "D2",
            "name": "研究、设计与算法",
            "subDirections": [
                {
                    "id": 5,
                    "code": "2.2",
                    "name": "算法与智能",
                    "directionCode": "D2",
                }
            ],
        }
    ]
    return directions, {"2.2": directions[0]["subDirections"][0]}


def valid_payload():
    return {
        "cluster_name": "多模态智能算法研发",
        "description": "研究和开发多模态理解、推理与模型训练算法。",
        "direction": {"code": "D2", "name": "研究、设计与算法"},
        "sub_direction": {"code": "2.2", "name": "算法与智能"},
        "profile_confidence": 0.96,
        "classification_confidence": 0.94,
        "existing_match": {
            "cluster_id": None,
            "relation": "different",
            "confidence": 0.97,
            "reasoning": "现有职业簇均不具备相同工作目标。",
        },
        "reasoning": "核心能力集中在多模态模型研发与评估。",
    }


def test_validates_structured_career_cluster():
    directions, sub_directions = taxonomy()
    result = service()._validate(valid_payload(), directions, sub_directions, [])
    assert result["name"] == "多模态智能算法研发"
    assert result["subDirectionId"] == 5
    assert result["profileConfidence"] == 0.96


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("profile_confidence", 0.79),
        ("classification_confidence", 0.799),
    ],
)
def test_retries_when_career_confidence_is_below_80_percent(field, value):
    directions, sub_directions = taxonomy()
    payload = valid_payload()
    payload[field] = value
    with pytest.raises(CareerClusteringRetry, match="低于80%"):
        service()._validate(payload, directions, sub_directions, [])


def test_requires_chinese_cluster_name():
    directions, sub_directions = taxonomy()
    payload = valid_payload()
    payload["cluster_name"] = "Multimodal Research Engineer"
    with pytest.raises(CareerClusteringRetry, match="中文"):
        service()._validate(payload, directions, sub_directions, [])


def test_accepts_manual_review_confidence_band():
    directions, sub_directions = taxonomy()
    payload = valid_payload()
    payload["profile_confidence"] = 0.80
    payload["classification_confidence"] = 0.899
    payload["existing_match"]["confidence"] = 0.85
    result = service()._validate(payload, directions, sub_directions, [])
    assert result["profileConfidence"] == 0.80
    assert result["suggestedConfidence"] == 0.85


def test_retries_when_cluster_semantic_confidence_is_below_80_percent():
    directions, sub_directions = taxonomy()
    payload = valid_payload()
    payload["existing_match"]["confidence"] = 0.79
    with pytest.raises(CareerClusteringRetry, match="语义判断"):
        service()._validate(payload, directions, sub_directions, [])


def test_rejects_cross_direction_subcategory():
    directions, sub_directions = taxonomy()
    payload = valid_payload()
    payload["direction"]["code"] = "D3"
    directions.append({"id": 3, "code": "D3", "name": "工程开发与实现", "subDirections": []})
    with pytest.raises(LLMCapabilityError, match="跨越"):
        service()._validate(payload, directions, sub_directions, [])


def test_same_relation_requires_existing_cluster():
    directions, sub_directions = taxonomy()
    payload = valid_payload()
    payload["existing_match"]["relation"] = "same"
    with pytest.raises(LLMCapabilityError, match="ID"):
        service()._validate(payload, directions, sub_directions, [])
