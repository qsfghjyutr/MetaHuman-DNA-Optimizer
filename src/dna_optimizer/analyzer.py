"""Core analysis engine: orchestrates DNA loading, graph building, and scoring.
核心分析引擎：协调 DNA 加载、依赖图构建和评分。"""

from typing import Dict, List, Optional

from .dna_io import DNAData, load_dna
from .dependency_graph import DependencyGraph, build_dependency_graph
from .scoring import RawControlScore, compute_scores, DEFAULT_WEIGHTS
from .reporter import export_csv, print_summary


def analyze(
    dna_path: str,
    output_csv: Optional[str] = None,
    weights: Optional[Dict[str, float]] = None,
    l0_threshold: float = 20.0,
    l1_threshold: float = 50.0,
    load_geometry: bool = True,
) -> List[RawControlScore]:
    """Run full importance analysis on a DNA file.
    对 DNA 文件运行完整的重要性分析。

    Args:
        dna_path: Path to the .dna file.
                  DNA 文件路径。
        output_csv: If provided, write results to this CSV path.
                    如果提供，将结果写入此 CSV 路径。
        weights: Custom dimension weights (defaults to DEFAULT_WEIGHTS).
                 自定义维度权重（默认为 DEFAULT_WEIGHTS）。
        l0_threshold: Importance score below this -> suggest L0 removal.
                      低于此重要性分数 -> 建议 L0 移除。
        l1_threshold: Importance score below this -> suggest L1 simplification.
                      低于此重要性分数 -> 建议 L1 简化。
        load_geometry: Load geometry layer for delta magnitude scoring.
                       加载几何层以用于位移幅度评分。

    Returns:
        List of RawControlScore sorted by importance (ascending).
        按重要性升序排列的 RawControlScore 列表。
    """
    print(f"Loading DNA: {dna_path}")
    data = load_dna(dna_path, load_geometry=load_geometry)

    print(f"  Raw controls: {data.raw_control_count}")
    print(f"  PSD expressions: {data.psd_count}")
    print(f"  BS channels: {data.bs_channel_count}")
    print(f"  Animated maps: {data.animated_map_count}")
    print(f"  Joints: {data.joint_count}")
    print(f"  LODs: {data.lod_count}")
    print(f"  Meshes: {data.mesh_count}")
    print()

    print("Building dependency graph...")
    graph = build_dependency_graph(data)

    print("Computing importance scores...")
    scores = compute_scores(
        data, graph,
        weights=weights,
        l0_threshold=l0_threshold,
        l1_threshold=l1_threshold,
    )

    print_summary(scores, total_bs_channels=data.bs_channel_count)

    if output_csv:
        export_csv(scores, output_csv)
        print(f"Results written to: {output_csv}")

    return scores
