"""Importance scoring dimensions and composite score calculation.
重要性评分维度与综合评分计算。"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .dna_io import DNAData
from .dependency_graph import DependencyGraph, get_raw_control_downstream


DEFAULT_WEIGHTS = {
    "geometry": 0.35,
    "joint": 0.25,
    "fanout": 0.15,
    "psd_ratio": 0.10,
    "lod": 0.05,
    "runtime": 0.10,
}


@dataclass
class RawControlScore:
    """Importance analysis result for a single raw control.
    单个原始控制器的重要性分析结果。"""

    index: int
    name: str

    # Downstream counts
    # 下游计数
    direct_bs_count: int = 0
    psd_count: int = 0
    psd_bs_count: int = 0
    am_count: int = 0
    joint_attr_count: int = 0

    # Actual downstream indices (for accurate aggregate stats)
    # 实际下游索引（用于精确的聚合统计）
    direct_bs_indices: List[int] = field(default_factory=list)
    psd_bs_indices: List[int] = field(default_factory=list)

    # Raw dimension scores (before normalization)
    # 原始维度分数（归一化之前）
    geometry_raw: float = 0.0
    joint_raw: float = 0.0
    fanout_raw: float = 0.0
    psd_ratio_raw: float = 0.0
    lod_raw: float = 0.0
    runtime_raw: float = 0.0

    # Normalized scores (0-100)
    # 归一化分数（0-100）
    geometry_score: float = 0.0
    joint_score: float = 0.0
    fanout_score: float = 0.0
    psd_ratio_score: float = 0.0
    lod_score: float = 0.0
    runtime_score: float = 0.0

    # Composite
    # 综合评分
    importance: float = 0.0
    suggested_level: str = "keep"  # "L0", "L1", "keep"
    filtered: bool = False  # True if protected by keep list / 被 keep list 保护


def compute_scores(
    data: DNAData,
    graph: DependencyGraph,
    weights: Dict[str, float] = None,
    l0_threshold: float = 20.0,
    l1_threshold: float = 50.0,
    keep_list: Optional[List[str]] = None,
) -> List[RawControlScore]:
    """Compute importance scores for all raw controls.
    计算所有原始控制器的重要性评分。

    Args:
        data: Extracted DNA data.
              提取的 DNA 数据。
        graph: Dependency graph.
               依赖图。
        weights: Optional custom weights for scoring dimensions.
                 可选的自定义评分维度权重。
        l0_threshold: Score below this -> suggest L0 (full removal).
                      低于此分数 -> 建议 L0（完全移除）。
        l1_threshold: Score below this -> suggest L1 (simplify PSD corrections).
                      低于此分数 -> 建议 L1（简化 PSD 修正）。
        keep_list: Curve name patterns to always keep (substring match).
                   始终保留的曲线名称模式（子串匹配）。
    """
    w = weights or DEFAULT_WEIGHTS
    scores = []

    for rc_idx in range(data.raw_control_count):
        downstream = get_raw_control_downstream(graph, rc_idx)
        s = RawControlScore(index=rc_idx, name=data.raw_control_names[rc_idx])

        s.direct_bs_count = len(downstream["direct_bs"])
        s.psd_count = len(downstream["psd_indices"])
        s.psd_bs_count = len(downstream["psd_bs"])
        s.am_count = len(downstream["am_indices"])
        s.joint_attr_count = downstream["joint_attr_count"]
        s.direct_bs_indices = downstream["direct_bs"]
        s.psd_bs_indices = downstream["psd_bs"]

        # Geometry: sum delta magnitudes across all downstream BS channels
        # 几何：对所有下游 BS 通道的位移幅度求和
        all_bs = downstream["direct_bs"] + downstream["psd_bs"]
        total_verts = 0
        total_magnitude = 0.0
        for bs_idx in all_bs:
            verts, mag = data.bs_geometry.get(bs_idx, (0, 0.0))
            total_verts += verts
            total_magnitude += mag
        s.geometry_raw = math.log1p(total_magnitude) * math.log1p(total_verts)

        # Joint: non-zero entries in joint matrix for this control + its PSDs
        # 关节：该控制器及其 PSD 在关节矩阵中的非零条目数
        s.joint_raw = float(s.joint_attr_count)

        # Fanout: total downstream count
        # 扇出：下游总数
        s.fanout_raw = float(s.psd_count + s.direct_bs_count + s.psd_bs_count + s.am_count)

        # PSD ratio: proportion of BS driven through PSDs (high ratio = good L1 candidate)
        # PSD 比率：通过 PSD 驱动的 BS 占比（高比率 = 适合 L1 优化）
        total_bs = s.direct_bs_count + s.psd_bs_count
        s.psd_ratio_raw = (s.psd_bs_count / total_bs * 100.0) if total_bs > 0 else 0.0

        # LOD: count how many LODs contain any of this control's downstream BS/AM
        # LOD：统计包含该控制器下游 BS/AM 的 LOD 层级数量
        lods_present = set()
        for lod_idx, bs_list in enumerate(data.bs_indices_per_lod):
            bs_set = set(bs_list)
            if any(bs in bs_set for bs in all_bs):
                lods_present.add(lod_idx)
        for lod_idx, am_list in enumerate(data.am_indices_per_lod):
            am_set = set(am_list)
            if any(am in am_set for am in downstream["am_indices"]):
                lods_present.add(lod_idx)
        s.lod_raw = float(len(lods_present))

        # Runtime cost estimate
        # 运行时开销估算
        s.runtime_raw = float(s.joint_attr_count) + float(s.psd_count) * 3.0 + float(total_verts) * 0.01

        scores.append(s)

    # Normalize each dimension to 0-100
    # 将每个维度归一化到 0-100
    _normalize(scores, "geometry")
    _normalize(scores, "joint")
    _normalize(scores, "fanout")
    _normalize(scores, "psd_ratio")
    _normalize(scores, "lod")
    _normalize(scores, "runtime")

    # Composite weighted score
    # 综合加权评分
    for s in scores:
        s.importance = (
            w.get("geometry", 0) * s.geometry_score
            + w.get("joint", 0) * s.joint_score
            + w.get("fanout", 0) * s.fanout_score
            + w.get("psd_ratio", 0) * s.psd_ratio_score
            + w.get("lod", 0) * s.lod_score
            + w.get("runtime", 0) * s.runtime_score
        )

        # Check keep list (substring match) before threshold classification
        # 在阈值分级前检查 keep list（子串匹配）
        if keep_list and any(pattern in s.name for pattern in keep_list):
            s.suggested_level = "keep"
            s.filtered = True
        elif s.importance < l0_threshold:
            s.suggested_level = "L0"
        elif s.importance < l1_threshold:
            s.suggested_level = "L1"
        else:
            s.suggested_level = "keep"

    # Sort by importance ascending (least important first)
    # 按重要性升序排序（最不重要的排在前面）
    scores.sort(key=lambda x: x.importance)

    return scores


def _normalize(scores: List[RawControlScore], dimension: str) -> None:
    """Min-max normalize a raw dimension to 0-100 across all scores.
    对原始维度在所有评分中进行最小-最大归一化到 0-100。"""
    raw_attr = f"{dimension}_raw"
    score_attr = f"{dimension}_score"

    values = [getattr(s, raw_attr) for s in scores]
    min_val = min(values) if values else 0.0
    max_val = max(values) if values else 0.0
    range_val = max_val - min_val

    for s in scores:
        raw = getattr(s, raw_attr)
        if range_val > 0:
            setattr(s, score_attr, (raw - min_val) / range_val * 100.0)
        else:
            setattr(s, score_attr, 0.0)
