import os

os.environ["EMBODIED_DISABLE_EMBEDDINGS"] = "1"

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_snapshot():
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    snapshots = client.get("/api/v1/graph/snapshots")
    assert snapshots.status_code == 200
    assert snapshots.json()[0]["code"] == "v4-dictionary-backfill-001"


def test_job_search_and_detail():
    response = client.get("/api/v1/jobs", params={"q": "ROS", "pageSize": 10})
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    job = items[0]
    detail = client.get(f"/api/v1/jobs/{job['id']}")
    assert detail.status_code == 200
    assert detail.json()["skillCount"] > 0


def test_job_neighborhood_and_evidence():
    jobs = client.get("/api/v1/jobs", params={"q": "ROS", "pageSize": 10}).json()["items"]
    job = jobs[0]
    graph = client.get(
        "/api/v1/graph/neighborhood",
        params={"node": job["key"], "depth": 1, "maxNodes": 30, "maxEdges": 50},
    )
    assert graph.status_code == 200
    payload = graph.json()
    assert payload["nodes"][0]["key"] == job["key"]
    skill_edges = [edge for edge in payload["edges"] if edge["type"] == "REQUIRES_SKILL"]
    assert skill_edges
    mapping_id = skill_edges[0]["properties"]["mapping_id"]
    evidence = client.get("/api/v1/evidence", params={"mappingId": mapping_id})
    assert evidence.status_code == 200
    assert evidence.json()["page"]["total"] >= 1
    assert evidence.json()["items"][0]["verified"] is False


def test_overview_is_budget_aware():
    response = client.get(
        "/api/v1/graph/overview",
        params={"aggregation": "none", "maxNodes": 20, "maxEdges": 20},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["partial"] is True
    assert len(payload["nodes"]) <= 20
    assert len(payload["edges"]) <= 20


def test_missing_resources_use_consistent_error_shape():
    response = client.get("/api/v1/jobs/999999")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "HTTP_404"
    assert body["requestId"]


def test_v4_capability_and_career_graph_contracts():
    capability = client.get("/api/v1/capability-graph/tree", params={"depth": 3})
    assert capability.status_code == 200
    payload = capability.json()
    assert payload["schemaVersion"] == "2"
    assert payload["graphType"] == "capability"
    assert len(payload["nodes"]) == 201
    assert payload["meta"]["coverage"] < 1

    career = client.get("/api/v1/career-graph/overview", params={"topK": 4, "threshold": 0.25})
    assert career.status_code == 200
    payload = career.json()
    assert payload["graphType"] == "career"
    assert len(payload["nodes"]) == 106
    assert payload["combos"]


def test_v4_focus_and_similarity_are_explainable():
    graph = client.get("/api/v1/career-graph/overview", params={"threshold": 0.25}).json()
    edge = graph["edges"][0]
    a = int(edge["source"].split(":")[1])
    b = int(edge["target"].split(":")[1])
    detail = client.get(f"/api/v1/job-similarities/{a}/{b}")
    assert detail.status_code == 200
    assert "components" in detail.json()
    assert "sharedCapabilities" in detail.json()
