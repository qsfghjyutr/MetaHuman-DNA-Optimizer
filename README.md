# MetaHuman DNA Optimizer

A tool for analyzing and optimizing MetaHuman DNA expression curves. It ranks each expression by importance and suggests tiered pruning strategies to reduce file size, GPU morph target cost, and CPU joint evaluation overhead.

MetaHuman DNA 表情曲线分析与优化工具。对每条表情按重要性排序，并建议分层裁剪策略，以减少文件大小、GPU morph target 开销和 CPU 关节计算负担。

## How It Works / 工作原理

MetaHuman DNA files encode a complex evaluation pipeline:

MetaHuman DNA 文件编码了一条复杂的求值管线：

```
GUI Controls (168)
  → Raw Controls (258)  ──→ Joint Matrix (CPU bottleneck, ~85-90% of RigLogic cost)
                             关节矩阵（CPU 瓶颈，占 RigLogic 约 85-90% 开销）
    → PSD (476)         ──→ Joint Matrix (same)
                             关节矩阵（同上）
      → BS Channels (687) ──→ GPU Morph Target deformation
                               GPU Morph Target 变形
      → Animated Maps (82) ──→ Material parameters
                                材质参数
```

This tool analyzes the dependency graph and scores each raw control (expression) across 6 dimensions to determine its importance, then suggests one of three pruning levels:

本工具分析依赖图，对每个原始控制器（表情）进行 6 个维度的评分以确定其重要性，然后建议以下三种裁剪级别之一：

| Level / 级别 | Action / 操作 | CPU Benefit / CPU 收益 | GPU Benefit / GPU 收益 | File Size / 文件大小 |
|-------|--------|------------|------------|-----------|
| **L0** | Remove entire expression (raw control + PSD + BS + AM + joint matrix columns) / 删除整条表情（原始控制器 + PSD + BS + AM + 关节矩阵列） | High / 高 | High / 高 | High / 高 |
| **L1** | Keep base BS, remove PSD correction BS / 保留基础 BS，删除 PSD 修正 BS | None / 无 | Medium / 中 | Medium / 中 |
| **L2** | Prune small deltas from remaining BS / 裁剪剩余 BS 中的微小位移 | None / 无 | Low / 低 | Medium / 中 |

## Scoring Dimensions / 评分维度

| Dimension / 维度 | Weight / 权重 | Description / 描述 |
|-----------|--------|-------------|
| Geometry Impact / 几何影响 | 0.35 | Total vertex displacement magnitude across all downstream BS / 所有下游 BS 的总顶点位移幅度 |
| Joint Drive / 关节驱动 | 0.25 | Non-zero entries in joint matrix for this control / 该控制器在关节矩阵中的非零条目数 |
| Downstream Fanout / 下游扇出 | 0.15 | Number of PSDs + BS channels + Animated Maps driven / 驱动的 PSD + BS 通道 + 动画贴图数量 |
| PSD Correction Ratio / PSD 修正占比 | 0.10 | Proportion of BS driven through PSD corrections / 通过 PSD 修正驱动的 BS 占比 |
| LOD Coverage / LOD 覆盖 | 0.05 | Number of LODs containing downstream BS/AM / 包含下游 BS/AM 的 LOD 层级数 |
| Runtime Cost / 运行时开销 | 0.10 | Estimated per-frame computation cost / 预估的每帧计算开销 |

## Project Structure / 项目结构

```
MetaHuman-DNA-Optimizer/
├── README.md
├── LICENSE
├── requirements.txt
│
├── src/
│   └── dna_optimizer/
│       ├── __init__.py            # Package init / 包初始化
│       ├── dna_io.py              # DNA file reading via BinaryStreamReader API
│       │                          # 通过 BinaryStreamReader API 读取 DNA 文件
│       ├── dependency_graph.py    # Dependency graph: raw control → PSD → BS/AM/Joint
│       │                          # 依赖图：原始控制器 → PSD → BS/AM/关节
│       ├── scoring.py             # 6-dimension importance scoring engine
│       │                          # 6 维重要性评分引擎
│       ├── analyzer.py            # Orchestrator: load → graph → score → report
│       │                          # 编排器：加载 → 建图 → 评分 → 报告
│       └── reporter.py            # CSV export and console summary output
│                                  # CSV 导出和控制台摘要输出
│
├── scripts/
│   └── analyze.py                 # CLI entry point / 命令行入口
│
├── tests/
└── docs/
```

## Prerequisites / 前置要求

- Python 3.7+ (Maya's `mayapy` or standalone Python)
- Python 3.7+（Maya 的 `mayapy` 或独立 Python）
- [MetaHuman DNA Calibration](https://github.com/EpicGames/MetaHuman-DNA-Calibration) pre-built libraries (`dna` and `dnacalib` Python modules)
- [MetaHuman DNA Calibration](https://github.com/EpicGames/MetaHuman-DNA-Calibration) 预编译库（`dna` 和 `dnacalib` Python 模块）

The pre-built libraries are located in the DNA Calibration repository under `lib/Maya{VERSION}/{platform}/`. Supported versions:

预编译库位于 DNA Calibration 仓库的 `lib/Maya{VERSION}/{platform}/` 目录下。支持的版本：

- Maya 2022 (Python 3.7)
- Maya 2023 (Python 3.9)
- Maya 2024 (Python 3.10)

## Usage / 使用方式

### Basic Analysis / 基本分析

```bash
# Using Maya's Python interpreter
# 使用 Maya 的 Python 解释器
mayapy scripts/analyze.py \
  --dna path/to/character.dna \
  --lib path/to/MetaHuman-DNA-Calibration/lib/Maya2023/windows \
  --output report.csv
```

### Options / 参数说明

| Option / 参数 | Description / 描述 |
|--------|-------------|
| `--dna` | Path to input .dna file (required) / 输入 .dna 文件路径（必填） |
| `--lib` | Path to DNA Calibration lib directory. Can also use `DNA_CALIB_LIB` env var / DNA Calibration 库目录路径，也可通过 `DNA_CALIB_LIB` 环境变量设置 |
| `--output`, `-o` | Output CSV file path. If omitted, only prints console summary / 输出 CSV 文件路径，省略则仅打印控制台摘要 |
| `--no-geometry` | Skip geometry layer loading for faster analysis (disables delta magnitude scoring) / 跳过几何层加载以加快分析（禁用位移幅度评分） |
| `--l0-threshold` | Importance score threshold for L0 suggestion (default: 20.0) / L0 建议的重要性分数阈值（默认：20.0） |
| `--l1-threshold` | Importance score threshold for L1 suggestion (default: 50.0) / L1 建议的重要性分数阈值（默认：50.0） |

### Environment Variable / 环境变量

```bash
# Set once, use everywhere
# 设置一次，到处使用
export DNA_CALIB_LIB=path/to/MetaHuman-DNA-Calibration/lib/Maya2023/windows
mayapy scripts/analyze.py --dna character.dna -o report.csv
```

## Example Output / 示例输出

```
======================================================================
MetaHuman DNA Optimizer - Expression Importance Analysis
======================================================================

Total raw controls analyzed: 258

Pruning level distribution:
  L0 (full removal):     172 controls
  L1 (simplify PSD):      79 controls
  keep:                    7 controls

Estimated savings if all suggestions applied:
  BS channels removed (L0):        138 / 687 (20.1%)
  PSD BS channels removed (L1):    445 / 687 (64.8%)
  Total BS reduction:              583 / 687 (84.9%)
  Joint matrix entries removed:   89061 / 2026261 (4.4%)

----------------------------------------------------------------------
Bottom 10 (lowest importance - best L0 candidates):
  Rank   Score Level  Name
  1        0.0 L0     CTRL_expressions.teethUpU
  2        0.0 L0     CTRL_expressions.teethDownU
  ...

Top 10 (highest importance - must keep):
  1       99.9 keep   CTRL_expressions.jawOpen
  2       62.2 keep   CTRL_expressions.mouthStretchR
  ...
======================================================================
```

## CSV Output Format / CSV 输出格式

The output CSV contains one row per raw control, sorted by importance (ascending):

输出 CSV 每行对应一个原始控制器，按重要性升序排列：

| Column / 列 | Description / 描述 |
|--------|-------------|
| `rank` | Rank (1 = least important) / 排名（1 = 最不重要） |
| `raw_control_index` | Index in DNA file / DNA 文件中的索引 |
| `name` | Control name (e.g. `CTRL_expressions.jawOpen`) / 控制器名称 |
| `importance` | Composite importance score (0-100) / 综合重要性评分（0-100） |
| `geometry_score` | Geometry impact dimension (0-100) / 几何影响维度（0-100） |
| `joint_score` | Joint drive dimension (0-100) / 关节驱动维度（0-100） |
| `fanout_score` | Downstream fanout dimension (0-100) / 下游扇出维度（0-100） |
| `psd_ratio_score` | PSD correction ratio dimension (0-100) / PSD 修正占比维度（0-100） |
| `lod_score` | LOD coverage dimension (0-100) / LOD 覆盖维度（0-100） |
| `runtime_score` | Runtime cost dimension (0-100) / 运行时开销维度（0-100） |
| `direct_bs_count` | BS channels directly driven / 直接驱动的 BS 通道数 |
| `psd_bs_count` | BS channels driven via PSD corrections / 通过 PSD 修正驱动的 BS 通道数 |
| `psd_count` | Number of PSD expressions involved / 涉及的 PSD 表达式数量 |
| `joint_attrs` | Joint matrix non-zero entries / 关节矩阵非零条目数 |
| `am_count` | Animated maps driven / 驱动的动画贴图数 |
| `suggested_level` | Suggested pruning level: `L0`, `L1`, or `keep` / 建议裁剪级别 |

## Roadmap / 路线图

- [ ] **L0 pruning execution / L0 裁剪执行**: Implement raw control removal (DNACalib lacks this command, requires direct DNA data manipulation) / 实现原始控制器移除（DNACalib 缺少此命令，需要直接操作 DNA 数据）
- [ ] **L1 pruning execution / L1 裁剪执行**: Generate DNACalib scripts using `RemoveBlendShapeCommand` for PSD correction BS removal / 使用 `RemoveBlendShapeCommand` 生成 DNACalib 脚本以移除 PSD 修正 BS
- [ ] **L2 pruning execution / L2 裁剪执行**: Apply `PruneBlendShapeTargetsCommand` with configurable threshold / 使用可配置阈值应用 `PruneBlendShapeTargetsCommand`
- [ ] **Visual comparison / 可视化对比**: Before/after rig preview in Maya / Maya 中裁剪前后的骨骼预览对比
- [ ] **Batch processing / 批量处理**: Analyze multiple DNA files at once / 一次分析多个 DNA 文件

## License / 许可证

MIT License - see [LICENSE](LICENSE) for details.

MIT 许可证 - 详见 [LICENSE](LICENSE)。
