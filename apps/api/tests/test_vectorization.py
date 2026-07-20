import math

from app.vectorization import (
    capability_similarity,
    cosine_sparse,
    dense_cosine,
    match_suggestion,
    normalize_sparse,
    pack_vector,
    text_hash,
    unpack_vector,
)


def test_sparse_and_dense_vectors_are_deterministic():
    sparse = normalize_sparse({1: 3.0, 2: 4.0})
    assert math.isclose(sum(value * value for value in sparse.values()), 1.0)
    assert cosine_sparse(sparse, sparse) == 1.0
    blob = pack_vector([0.6, 0.8])
    restored = unpack_vector(blob)
    assert dense_cosine(restored, [0.6, 0.8]) > 0.99999
    assert text_hash("岗位名称：测试") == text_hash("岗位名称：测试")


def test_threshold_rules_are_explicit():
    assert match_suggestion(0.85, 0.75, 0.6, 5) == "SAME_CAREER"
    assert match_suggestion(0.7, 0.5, 0.6, 5) == "RELATED_CAREER"
    assert match_suggestion(0.5, 0.2, 0.2, 2) == "INSUFFICIENT_EVIDENCE"
