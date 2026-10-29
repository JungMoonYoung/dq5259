"""유사성(Similarity) — 5259-2 6.5.8.2.

측정 함수: A(전체 샘플 수)와 B(클러스터 수)로 계산.
비고 7 "샘플 수와 클러스터 수가 같으면 0(어떤 샘플도 유사하지 않음)"에 맞춰
X = 1 - B/A 로 구현한다 (값이 클수록 비슷한 샘플이 몰려 있음).

클러스터링: 이미지 dHash(64비트) 해밍 거리 ≤ h 인 샘플을 같은 군집으로 묶는다 (Union-Find).
"""

from collections import defaultdict

import numpy as np

from . import QMResult, not_applicable, register


def _clusters(items, hamming):
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if bin(items[i][1] ^ items[j][1]).count("1") <= hamming:
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i, (key, _) in enumerate(items):
        groups[find(i)].append(key)
    return list(groups.values())


@register("Sim-ML-1", "샘플 유사성", "유사성", "5259-2 6.5.8.2",
          "X = 1 - B/A  (A: 전체 샘플 수, B: 군집 수). 비고 7: 샘플 수 = 군집 수이면 0",
          data_types=("image",))
def sample_similarity(prof, cfg, params):
    items = [(s.key, s.source_meta["dhash"]) for s in prof.samples
             if s.source_meta and "dhash" in s.source_meta]
    if len(items) < 2:
        return not_applicable("Sim-ML-1", "이미지가 2장 미만")
    h = params.get("hamming", 6)
    groups = _clusters(items, h)
    A, B = len(items), len(groups)
    multi = sorted((g for g in groups if len(g) > 1), key=len, reverse=True)
    return QMResult("Sim-ML-1", A, B, 1 - B / A,
                    defects=[{"cluster": i + 1, "size": len(g), "samples": ", ".join(g[:5]) + (" …" if len(g) > 5 else ""),
                              "reason": f"유사 샘플 {len(g)}장이 한 군집"} for i, g in enumerate(multi)],
                    detail={"cluster_sizes": sorted((len(g) for g in groups), reverse=True)},
                    note=f"dHash 해밍 거리 ≤ {h}를 유사로 판단")


def normalize(matrix):
    """5259-2 Sim-ML 비고 1: 각 열의 평균을 빼고, 각 행(샘플)의 크기를 1로 정규화."""
    m = np.asarray(matrix, dtype=float)
    m = m - m.mean(axis=0)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return m / norms


def pca_components(matrix, variance=0.95):
    """고유값 합의 variance 이상을 설명하는 주성분 개수."""
    m = normalize(matrix)
    eig = np.linalg.svd(m, compute_uv=False) ** 2
    if eig.sum() == 0:
        return 0
    return int(np.searchsorted(np.cumsum(eig) / eig.sum(), variance - 1e-12) + 1)


@register("Sim-ML-3", "샘플 독립성", "유사성", "5259-2 6.5.8.2",
          "X = A/B  (A: 고유값 합의 95%를 설명하는 PCA 주성분 수, B: 데이터셋 전체 차원 수)",
          data_types=("image",))
def sample_independence(prof, cfg, params):
    feats = [(s.key, s.source_meta["thumb"]) for s in prof.samples
             if s.source_meta and "thumb" in s.source_meta]
    if len(feats) < 3:
        return not_applicable("Sim-ML-3", "이미지가 3장 미만")
    variance = params.get("variance", 0.95)
    matrix = [f for _, f in feats]
    A, B = pca_components(matrix, variance), len(matrix[0])
    rank_cap = min(len(matrix) - 1, B)
    note = f"특징: 8×8 흑백 축소 이미지({B}차원). 낮을수록 샘플들이 비슷한 방향에 몰려 있음"
    if rank_cap < B:
        note += f" · 샘플 수가 차원보다 적어 A는 최대 {rank_cap}"
    return QMResult("Sim-ML-3", A, B, A / B, detail={"rank_cap": rank_cap, "variance": variance}, note=note)
