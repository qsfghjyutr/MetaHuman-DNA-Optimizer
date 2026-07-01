"""Build dependency graph from DNA data: raw control -> PSD -> BS/AM/Joint.
从 DNA 数据构建依赖图：原始控制器 -> PSD -> BS/AM/关节。"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set

from .dna_io import DNAData


@dataclass
class DependencyGraph:
    """Maps each raw control to all its downstream dependencies.
    将每个原始控制器映射到其所有下游依赖。"""

    raw_control_count: int = 0
    psd_offset: int = 0  # PSD indices start at raw_control_count in unified space
    # PSD 索引在统一空间中从 raw_control_count 开始

    # raw control index -> list of PSD indices (unified space, >= psd_offset)
    # 原始控制器索引 -> PSD 索引列表（统一空间，>= psd_offset）
    raw_to_psds: Dict[int, List[int]] = field(default_factory=lambda: defaultdict(list))

    # PSD index (unified) -> list of raw control indices that feed it
    # PSD 索引（统一）-> 为其提供输入的原始控制器索引列表
    psd_to_raw_inputs: Dict[int, List[int]] = field(default_factory=lambda: defaultdict(list))

    # unified input index -> list of BS channel indices it drives
    # 统一输入索引 -> 其驱动的 BS 通道索引列表
    input_to_bs: Dict[int, List[int]] = field(default_factory=lambda: defaultdict(list))

    # unified input index -> set of AM output indices it drives
    # 统一输入索引 -> 其驱动的 AM 输出索引集合
    input_to_am: Dict[int, Set[int]] = field(default_factory=lambda: defaultdict(set))

    # unified input index -> number of non-zero joint matrix entries
    # 统一输入索引 -> 非零关节矩阵条目数
    input_to_joint_attrs: Dict[int, int] = field(default_factory=lambda: defaultdict(int))

    # BS channel index -> unified input index that drives it
    # BS 通道索引 -> 驱动它的统一输入索引
    bs_to_input: Dict[int, int] = field(default_factory=dict)


def build_dependency_graph(data: DNAData) -> DependencyGraph:
    """Build the full dependency graph from extracted DNA data.
    从提取的 DNA 数据构建完整的依赖图。"""
    graph = DependencyGraph()
    graph.raw_control_count = data.raw_control_count
    graph.psd_offset = data.raw_control_count

    _build_psd_mappings(data, graph)
    _build_bs_mappings(data, graph)
    _build_am_mappings(data, graph)
    _build_joint_mappings(data, graph)

    return graph


def _build_psd_mappings(data: DNAData, graph: DependencyGraph) -> None:
    """Map raw controls <-> PSD expressions from the PSD sparse matrix.
    从 PSD 稀疏矩阵建立原始控制器与 PSD 表达式的双向映射。"""
    for row, col in zip(data.psd_rows, data.psd_columns):
        # row = PSD output index (unified space, >= raw_control_count)
        # row = PSD 输出索引（统一空间，>= raw_control_count）
        # col = raw control input index
        # col = 原始控制器输入索引
        if col < data.raw_control_count:
            if row not in graph.raw_to_psds[col]:
                graph.raw_to_psds[col].append(row)
            if col not in graph.psd_to_raw_inputs[row]:
                graph.psd_to_raw_inputs[row].append(col)


def _build_bs_mappings(data: DNAData, graph: DependencyGraph) -> None:
    """Map unified input indices -> BS channel outputs.
    建立统一输入索引到 BS 通道输出的映射。"""
    for input_idx, output_idx in zip(data.bs_input_indices, data.bs_output_indices):
        if output_idx not in graph.input_to_bs[input_idx]:
            graph.input_to_bs[input_idx].append(output_idx)
        graph.bs_to_input[output_idx] = input_idx


def _build_am_mappings(data: DNAData, graph: DependencyGraph) -> None:
    """Map unified input indices -> animated map outputs.
    建立统一输入索引到动画贴图输出的映射。"""
    for input_idx, output_idx in zip(data.am_input_indices, data.am_output_indices):
        graph.input_to_am[input_idx].add(output_idx)


def _build_joint_mappings(data: DNAData, graph: DependencyGraph) -> None:
    """Count non-zero joint matrix entries per input index.
    统计每个输入索引的非零关节矩阵条目数。"""
    for group in data.joint_groups:
        input_indices = group["input_indices"]
        output_indices = group["output_indices"]
        values = group["values"]

        if not input_indices or not output_indices:
            continue

        num_cols = len(input_indices)
        num_rows = len(output_indices)

        # Values are stored row-major: values[row * num_cols + col]
        # 值按行优先存储：values[row * num_cols + col]
        for row in range(num_rows):
            for col in range(num_cols):
                val_idx = row * num_cols + col
                if val_idx < len(values) and values[val_idx] != 0.0:
                    graph.input_to_joint_attrs[input_indices[col]] += 1


def get_raw_control_downstream(graph: DependencyGraph, raw_idx: int) -> dict:
    """Get all downstream dependencies for a single raw control.
    获取单个原始控制器的所有下游依赖。

    Returns dict with:
    返回包含以下键的字典：
        direct_bs: BS channels directly driven by this raw control
                   该原始控制器直接驱动的 BS 通道
        psd_indices: PSD expressions this raw control participates in
                     该原始控制器参与的 PSD 表达式
        psd_bs: BS channels driven through PSDs
                通过 PSD 驱动的 BS 通道
        am_indices: animated maps driven (directly or via PSD)
                    驱动的动画贴图（直接或通过 PSD）
        joint_attr_count: total non-zero joint matrix entries
                          非零关节矩阵条目总数
    """
    result = {
        "direct_bs": list(graph.input_to_bs.get(raw_idx, [])),
        "psd_indices": list(graph.raw_to_psds.get(raw_idx, [])),
        "psd_bs": [],
        "am_indices": set(graph.input_to_am.get(raw_idx, set())),
        "joint_attr_count": graph.input_to_joint_attrs.get(raw_idx, 0),
    }

    # Collect BS and AM driven through PSDs
    # 收集通过 PSD 驱动的 BS 和 AM
    for psd_idx in result["psd_indices"]:
        for bs_idx in graph.input_to_bs.get(psd_idx, []):
            if bs_idx not in result["psd_bs"]:
                result["psd_bs"].append(bs_idx)
        result["am_indices"].update(graph.input_to_am.get(psd_idx, set()))
        result["joint_attr_count"] += graph.input_to_joint_attrs.get(psd_idx, 0)

    result["am_indices"] = list(result["am_indices"])
    return result
