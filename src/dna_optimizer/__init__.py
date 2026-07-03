"""MetaHuman DNA Optimizer - Expression curve importance analysis and pruning tool.
MetaHuman DNA 优化器 - 表情曲线重要性分析与裁剪工具。"""

__version__ = "0.2.0"

from .analyzer import analyze, analyze_and_prune
from .pruner import execute_pruning, PruneResult
