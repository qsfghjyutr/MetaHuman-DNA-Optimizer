"""PySide6 GUI for MetaHuman DNA Optimizer.
MetaHuman DNA 优化器的 PySide6 图形界面。

Usage:
    & "path/to/Maya2025/bin/mayapy.exe" scripts/gui.py
"""

import copy
import os
import sys

# Add project src to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_root, "src"))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QFileDialog, QComboBox, QHeaderView, QMessageBox,
    QAbstractItemView, QSlider, QDoubleSpinBox, QGroupBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

# Row colors by level
COLOR_L0 = QColor(255, 220, 220)
COLOR_L1 = QColor(255, 245, 200)
COLOR_KEEP = QColor(220, 255, 220)
COLOR_FILTER = QColor(200, 220, 255)

# Table column definitions: (header, field_name)
COLUMNS = [
    ("", "check"),
    ("Rank", "rank"),
    ("Name", "name"),
    ("Score", "importance"),
    ("Level", "suggested_level"),
    ("Geometry", "geometry_score"),
    ("Joint", "joint_score"),
    ("Fanout", "fanout_score"),
    ("PSD Ratio", "psd_ratio_score"),
    ("LOD", "lod_score"),
    ("Runtime", "runtime_score"),
    ("Direct BS", "direct_bs_count"),
    ("PSD BS", "psd_bs_count"),
    ("Joints", "joint_attr_count"),
    ("AMs", "am_count"),
]

DEFAULT_LIB = "C:/Program Files/Epic Games/MetaHumanForMaya"


class AnalyzeWorker(QThread):
    """Background thread for DNA analysis."""
    result_ready = Signal(list, object, object)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, dna_path, lib_path, keep_list=None):
        super().__init__()
        self.dna_path = dna_path
        self.lib_path = lib_path
        self.keep_list = keep_list

    def run(self):
        try:
            from dna_optimizer.lib_setup import setup_lib_paths
            setup_lib_paths(self.lib_path)

            from dna_optimizer.dna_io import load_dna
            from dna_optimizer.dependency_graph import build_dependency_graph
            from dna_optimizer.scoring import compute_scores

            self.log.emit("Loading DNA...")
            data = load_dna(self.dna_path.replace("\\", "/"), load_geometry=True)
            self.log.emit(f"Loaded: {data.raw_control_count} raw controls, "
                          f"{data.bs_channel_count} BS channels")

            self.log.emit("Building dependency graph...")
            graph = build_dependency_graph(data)

            self.log.emit("Computing scores...")
            scores = compute_scores(data, graph, keep_list=self.keep_list)

            self.log.emit("Analysis complete.")
            self.result_ready.emit(scores, graph, data)
        except Exception as e:
            self.error.emit(str(e))


class PruneWorker(QThread):
    """Background thread for pruning execution."""
    result_ready = Signal(object)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, dna_path, output_path, lib_path, scores, graph, data, l2_threshold):
        super().__init__()
        self.dna_path = dna_path
        self.output_path = output_path
        self.lib_path = lib_path
        self.scores = scores
        self.graph = graph
        self.data = data
        self.l2_threshold = l2_threshold

    def run(self):
        try:
            from dna_optimizer.lib_setup import setup_lib_paths
            setup_lib_paths(self.lib_path)

            from dna_optimizer.pruner import execute_pruning

            self.log.emit("Executing pruning...")
            result = execute_pruning(
                dna_path=self.dna_path.replace("\\", "/"),
                output_path=self.output_path.replace("\\", "/"),
                scores=self.scores,
                graph=self.graph,
                data=self.data,
                levels=["L0", "L1", "L2"],
                l2_threshold=self.l2_threshold,
            )
            self.log.emit("Pruning complete.")
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class NumericTableItem(QTableWidgetItem):
    """Table item that sorts numerically."""
    def __lt__(self, other):
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return self.text() < other.text()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MetaHuman DNA Optimizer")
        self.setMinimumSize(1200, 700)

        self.scores = []
        self.graph = None
        self.data = None
        self.worker = None
        self._total_joint_nonzero = 0

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Top: file inputs ---
        layout.addLayout(self._build_file_section())

        # --- Filter bar ---
        layout.addLayout(self._build_filter_section())

        # --- Threshold controls ---
        layout.addLayout(self._build_threshold_section())

        # --- Keep list ---
        layout.addLayout(self._build_keep_list_section())

        # --- Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 30)
        layout.addWidget(self.table, stretch=1)

        # --- Pruning stats ---
        layout.addWidget(self._build_stats_section())

        # --- Status bar ---
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        # --- Bottom: output + prune ---
        layout.addLayout(self._build_prune_section())

    def _build_file_section(self):
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("DNA File:"))
        self.dna_input = QLineEdit()
        self.dna_input.setPlaceholderText("Select .dna file...")
        row1.addWidget(self.dna_input, stretch=1)
        btn_dna = QPushButton("Browse")
        btn_dna.clicked.connect(self._browse_dna)
        row1.addWidget(btn_dna)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Lib Path:"))
        self.lib_input = QLineEdit(DEFAULT_LIB)
        row2.addWidget(self.lib_input, stretch=1)
        btn_lib = QPushButton("Browse")
        btn_lib.clicked.connect(self._browse_lib)
        row2.addWidget(btn_lib)

        self.btn_analyze = QPushButton("Analyze")
        self.btn_analyze.setFixedWidth(120)
        self.btn_analyze.clicked.connect(self._on_analyze)
        row2.addWidget(self.btn_analyze)
        layout.addLayout(row2)

        return layout

    def _build_filter_section(self):
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Filter:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Search by name...")
        self.filter_input.textChanged.connect(self._apply_filters)
        layout.addWidget(self.filter_input, stretch=1)

        layout.addWidget(QLabel("Show:"))
        self.level_filter = QComboBox()
        self.level_filter.addItems(["All", "L0", "L1", "keep"])
        self.level_filter.currentTextChanged.connect(self._apply_filters)
        layout.addWidget(self.level_filter)

        btn_select = QPushButton("Select All L0+L1")
        btn_select.clicked.connect(self._select_l0_l1)
        layout.addWidget(btn_select)

        btn_deselect = QPushButton("Deselect All")
        btn_deselect.clicked.connect(self._deselect_all)
        layout.addWidget(btn_deselect)

        return layout

    def _build_threshold_section(self):
        layout = QHBoxLayout()

        layout.addWidget(QLabel("L0 Threshold (<):"))
        self.l0_spin = QDoubleSpinBox()
        self.l0_spin.setRange(0.0, 100.0)
        self.l0_spin.setSingleStep(1.0)
        self.l0_spin.setValue(20.0)
        self.l0_spin.setFixedWidth(70)
        layout.addWidget(self.l0_spin)

        self.l0_slider = QSlider(Qt.Horizontal)
        self.l0_slider.setRange(0, 1000)  # 0.0 ~ 100.0, step 0.1
        self.l0_slider.setValue(200)
        self.l0_slider.setFixedWidth(200)
        layout.addWidget(self.l0_slider)

        layout.addSpacing(20)

        layout.addWidget(QLabel("L1 Threshold (<):"))
        self.l1_spin = QDoubleSpinBox()
        self.l1_spin.setRange(0.0, 100.0)
        self.l1_spin.setSingleStep(1.0)
        self.l1_spin.setValue(50.0)
        self.l1_spin.setFixedWidth(70)
        layout.addWidget(self.l1_spin)

        self.l1_slider = QSlider(Qt.Horizontal)
        self.l1_slider.setRange(0, 1000)
        self.l1_slider.setValue(500)
        self.l1_slider.setFixedWidth(200)
        layout.addWidget(self.l1_slider)

        # Sync slider <-> spinbox
        self.l0_slider.valueChanged.connect(
            lambda v: self.l0_spin.setValue(v / 10.0))
        self.l0_spin.valueChanged.connect(
            lambda v: self.l0_slider.setValue(int(v * 10)))
        self.l1_slider.valueChanged.connect(
            lambda v: self.l1_spin.setValue(v / 10.0))
        self.l1_spin.valueChanged.connect(
            lambda v: self.l1_slider.setValue(int(v * 10)))

        btn_apply = QPushButton("Apply Thresholds")
        btn_apply.setFixedWidth(130)
        btn_apply.clicked.connect(self._apply_thresholds)
        layout.addWidget(btn_apply)

        layout.addStretch()

        return layout

    def _build_keep_list_section(self):
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Keep List:"))
        self.keep_input = QLineEdit()
        self.keep_input.setPlaceholderText("Enter curve name pattern and click Add...")
        layout.addWidget(self.keep_input, stretch=1)

        btn_add = QPushButton("Add")
        btn_add.setFixedWidth(60)
        btn_add.clicked.connect(self._add_keep_pattern)
        layout.addWidget(btn_add)

        self.keep_label = QLabel("")
        self.keep_label.setStyleSheet("color: #336; font-style: italic;")
        layout.addWidget(self.keep_label, stretch=1)

        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(60)
        btn_clear.clicked.connect(self._clear_keep_list)
        layout.addWidget(btn_clear)

        # Internal keep list storage with defaults
        self._keep_list = ["eyeBlinkL", "eyeBlinkR", "browRaise", "eyeLook"]
        self._update_keep_label()

        return layout

    def _add_keep_pattern(self):
        pattern = self.keep_input.text().strip()
        if not pattern:
            return
        if pattern not in self._keep_list:
            self._keep_list.append(pattern)
        self.keep_input.clear()
        self._update_keep_label()
        # Re-apply thresholds to reflect new keep list
        self._apply_thresholds()

    def _clear_keep_list(self):
        self._keep_list.clear()
        self._update_keep_label()
        self._apply_thresholds()

    def _update_keep_label(self):
        if self._keep_list:
            self.keep_label.setText("Active: " + ", ".join(self._keep_list))
        else:
            self.keep_label.setText("")

    def _is_filtered(self, name):
        """Check if a curve name matches any pattern in the keep list."""
        return any(pattern in name for pattern in self._keep_list)

    def _apply_thresholds(self):
        """Reclassify all rows based on current threshold spinbox values."""
        if not self.scores:
            return

        l0_thresh = self.l0_spin.value()
        l1_thresh = self.l1_spin.value()

        if l0_thresh >= l1_thresh:
            QMessageBox.warning(
                self, "Invalid Thresholds",
                "L0 threshold must be less than L1 threshold.")
            return

        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            # Read importance score from column 3
            score_item = self.table.item(row, 3)
            if not score_item:
                continue
            try:
                importance = float(score_item.text())
            except ValueError:
                continue

            # Check keep list filter
            name_item = self.table.item(row, 2)
            name = name_item.text() if name_item else ""
            is_filtered = self._is_filtered(name)

            if is_filtered:
                new_level = "keep"
            elif importance < l0_thresh:
                new_level = "L0"
            elif importance < l1_thresh:
                new_level = "L1"
            else:
                new_level = "keep"

            # Update combobox
            combo = self.table.cellWidget(row, 4)
            if combo:
                combo.blockSignals(True)
                combo.setCurrentText(new_level)
                combo.blockSignals(False)

            # Update hidden item
            level_item = self.table.item(row, 4)
            if level_item:
                level_item.setText(new_level)

            # Update checkbox
            cb_item = self.table.item(row, 0)
            if cb_item:
                cb_item.setCheckState(
                    Qt.Checked if new_level in ("L0", "L1") else Qt.Unchecked)

            # Update row color: filtered rows get special color
            if is_filtered:
                self._set_row_color(row, "filtered")
            else:
                self._set_row_color(row, new_level)

        self.table.blockSignals(False)
        self._update_status()

    def _build_stats_section(self):
        group = QGroupBox("Estimated Pruning Impact")
        layout = QHBoxLayout(group)

        self.bs_stat_label = QLabel("BS Channels: --")
        self.am_stat_label = QLabel("Animated Maps: --")
        self.joint_stat_label = QLabel("Joint Matrix: --")

        layout.addWidget(self.bs_stat_label)
        layout.addSpacing(30)
        layout.addWidget(self.am_stat_label)
        layout.addSpacing(30)
        layout.addWidget(self.joint_stat_label)
        layout.addStretch()

        return group

    def _build_modified_scores_from_gui(self):
        """Build modified scores list reflecting current GUI checkbox/level state."""
        checked_levels = {}
        for row in range(self.table.rowCount()):
            cb_item = self.table.item(row, 0)
            if cb_item and cb_item.checkState() == Qt.Checked:
                rc_index = cb_item.data(Qt.UserRole)
                checked_levels[rc_index] = self._get_row_level(row)

        modified_scores = copy.deepcopy(self.scores)
        for s in modified_scores:
            # Keep list filter takes priority over checkbox state
            if self._is_filtered(s.name):
                s.suggested_level = "keep"
            elif s.index in checked_levels:
                s.suggested_level = checked_levels[s.index]
            else:
                s.suggested_level = "keep"
        return modified_scores

    def _compute_pruning_estimates(self):
        """Recompute and display estimated pruning percentages from current GUI state."""
        if not self.scores or not self.graph or not self.data:
            return

        from dna_optimizer.pruner import _collect_l0_safe_indices, _collect_l1_bs_indices

        modified_scores = self._build_modified_scores_from_gui()

        l0_bs, l0_am, zero_joint_inputs = _collect_l0_safe_indices(
            modified_scores, self.graph
        )
        l1_bs = _collect_l1_bs_indices(modified_scores, self.graph, l0_bs)

        total_bs = self.data.bs_channel_count
        total_am = self.data.animated_map_count
        total_joint = self._total_joint_nonzero

        removed_bs = len(l0_bs) + len(l1_bs)
        removed_am = len(l0_am)
        zeroed_joint = sum(
            self.graph.input_to_joint_attrs.get(i, 0) for i in zero_joint_inputs
        )

        bs_pct = (removed_bs / total_bs * 100) if total_bs > 0 else 0
        am_pct = (removed_am / total_am * 100) if total_am > 0 else 0
        joint_pct = (zeroed_joint / total_joint * 100) if total_joint > 0 else 0

        self.bs_stat_label.setText(
            f"BS Channels: {removed_bs}/{total_bs} ({bs_pct:.1f}%)")
        self.am_stat_label.setText(
            f"Animated Maps: {removed_am}/{total_am} ({am_pct:.1f}%)")
        self.joint_stat_label.setText(
            f"Joint Matrix: {zeroed_joint}/{total_joint} ({joint_pct:.1f}%)")

    def _build_prune_section(self):
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Output:"))
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Output .dna file path...")
        layout.addWidget(self.output_input, stretch=1)
        btn_out = QPushButton("Browse")
        btn_out.clicked.connect(self._browse_output)
        layout.addWidget(btn_out)

        layout.addWidget(QLabel("L2 Threshold:"))
        self.l2_input = QLineEdit("0.001")
        self.l2_input.setFixedWidth(60)
        layout.addWidget(self.l2_input)

        self.btn_prune = QPushButton("Execute Pruning")
        self.btn_prune.setFixedWidth(140)
        self.btn_prune.setEnabled(False)
        self.btn_prune.clicked.connect(self._on_prune)
        layout.addWidget(self.btn_prune)

        return layout

    # --- Browse dialogs ---

    def _browse_dna(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select DNA File", "", "DNA Files (*.dna)")
        if path:
            self.dna_input.setText(path)
            base, ext = os.path.splitext(path)
            self.output_input.setText(f"{base}_pruned{ext}")

    def _browse_lib(self):
        path = QFileDialog.getExistingDirectory(self, "Select MetaHuman for Maya Directory")
        if path:
            self.lib_input.setText(path)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Pruned DNA", "", "DNA Files (*.dna)")
        if path:
            self.output_input.setText(path)

    # --- Analyze ---

    def _on_analyze(self):
        dna_path = self.dna_input.text().strip()
        lib_path = self.lib_input.text().strip()

        if not dna_path:
            QMessageBox.warning(self, "Error", "Please select a DNA file.")
            return
        if not os.path.isfile(dna_path):
            QMessageBox.warning(self, "Error", f"DNA file not found:\n{dna_path}")
            return

        self.btn_analyze.setEnabled(False)
        self.btn_analyze.setText("Analyzing...")
        self.status_label.setText("Analyzing...")

        keep_list = self._keep_list if self._keep_list else None
        self.worker = AnalyzeWorker(dna_path, lib_path, keep_list=keep_list)
        self.worker.result_ready.connect(self._on_analyze_done)
        self.worker.error.connect(self._on_worker_error)
        self.worker.log.connect(self._on_log)
        self.worker.start()

    def _on_analyze_done(self, scores, graph, data):
        self.scores = scores
        self.graph = graph
        self.data = data
        self._total_joint_nonzero = sum(graph.input_to_joint_attrs.values())
        self._populate_table()
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Analyze")
        self.btn_prune.setEnabled(True)
        self._update_status()

    def _on_worker_error(self, msg):
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("Analyze")
        self.btn_prune.setEnabled(bool(self.scores))
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Error", msg)

    def _on_log(self, msg):
        self.status_label.setText(msg)

    # --- Table ---

    def _populate_table(self):
        self.table.setSortingEnabled(False)
        try:
            self.table.itemChanged.disconnect(self._on_item_changed)
        except RuntimeError:
            pass
        self.table.setRowCount(len(self.scores))

        for row, s in enumerate(self.scores):
            rank = row + 1

            # Checkbox
            cb = QTableWidgetItem()
            cb.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checked = s.suggested_level in ("L0", "L1")
            cb.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            cb.setData(Qt.UserRole, s.index)
            self.table.setItem(row, 0, cb)

            # Data columns (skip Level column index 4, handled by combobox)
            values = [
                (1, str(rank), True),
                (2, s.name, False),
                (3, f"{s.importance:.1f}", True),
                # column 4 = Level, handled below as combobox
                (5, f"{s.geometry_score:.1f}", True),
                (6, f"{s.joint_score:.1f}", True),
                (7, f"{s.fanout_score:.1f}", True),
                (8, f"{s.psd_ratio_score:.1f}", True),
                (9, f"{s.lod_score:.1f}", True),
                (10, f"{s.runtime_score:.1f}", True),
                (11, str(s.direct_bs_count), True),
                (12, str(s.psd_bs_count), True),
                (13, str(s.joint_attr_count), True),
                (14, str(s.am_count), True),
            ]

            for col, text, numeric in values:
                item = NumericTableItem(text) if numeric else QTableWidgetItem(text)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.table.setItem(row, col, item)

            # Level column: placeholder item for color + combobox widget
            level_item = QTableWidgetItem(s.suggested_level)
            level_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.table.setItem(row, 4, level_item)

            combo = QComboBox()
            combo.addItems(["L0", "L1", "keep"])
            combo.setCurrentText(s.suggested_level)
            combo.setProperty("row", row)
            combo.currentTextChanged.connect(self._on_level_changed)
            self.table.setCellWidget(row, 4, combo)

            # Row color: filtered rows get special color
            if s.filtered:
                self._set_row_color(row, "filtered")
            else:
                self._set_row_color(row, s.suggested_level)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 30)
        self.table.itemChanged.connect(self._on_item_changed)

    def _set_row_color(self, row, level):
        """Set background color for all cells in a row based on level."""
        color = {"L0": COLOR_L0, "L1": COLOR_L1, "keep": COLOR_KEEP,
                 "filtered": COLOR_FILTER}.get(level, QColor(255, 255, 255))
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(color)

    def _on_level_changed(self, new_level):
        """Handle manual level change from combobox."""
        combo = self.sender()
        row = combo.property("row")
        # Update hidden item text so filters and prune logic work
        level_item = self.table.item(row, 4)
        if level_item:
            level_item.setText(new_level)
        # Update row color
        self._set_row_color(row, new_level)
        # Auto-update checkbox: check if L0/L1, uncheck if keep
        cb_item = self.table.item(row, 0)
        if cb_item:
            self.table.blockSignals(True)
            cb_item.setCheckState(Qt.Checked if new_level in ("L0", "L1") else Qt.Unchecked)
            self.table.blockSignals(False)
        self._update_status()

    def _on_item_changed(self, item):
        if item.column() == 0:
            self._update_status()

    # --- Filters ---

    def _get_row_level(self, row):
        """Get current level for a row from combobox or fallback to item text."""
        combo = self.table.cellWidget(row, 4)
        if combo:
            return combo.currentText()
        level_item = self.table.item(row, 4)
        return level_item.text() if level_item else ""

    def _apply_filters(self):
        text_filter = self.filter_input.text().lower()
        level_filter = self.level_filter.currentText()

        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 2)
            if not name_item:
                continue

            current_level = self._get_row_level(row)
            name_match = text_filter in name_item.text().lower()
            level_match = level_filter == "All" or current_level == level_filter
            self.table.setRowHidden(row, not (name_match and level_match))

    def _select_l0_l1(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            cb_item = self.table.item(row, 0)
            if cb_item:
                current_level = self._get_row_level(row)
                checked = current_level in ("L0", "L1")
                cb_item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.table.blockSignals(False)
        self._update_status()

    def _deselect_all(self):
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            cb_item = self.table.item(row, 0)
            if cb_item:
                cb_item.setCheckState(Qt.Unchecked)
        self.table.blockSignals(False)
        self._update_status()

    # --- Status ---

    def _update_status(self):
        total = self.table.rowCount()
        selected = 0
        l0_sel = 0
        l1_sel = 0
        filtered = 0

        for row in range(total):
            name_item = self.table.item(row, 2)
            name = name_item.text() if name_item else ""
            if self._is_filtered(name):
                filtered += 1

            cb_item = self.table.item(row, 0)
            if cb_item and cb_item.checkState() == Qt.Checked:
                selected += 1
                current_level = self._get_row_level(row)
                if current_level == "L0":
                    l0_sel += 1
                elif current_level == "L1":
                    l1_sel += 1

        status = (f"Selected: {selected}/{total}  |  "
                  f"L0: {l0_sel}  L1: {l1_sel}  keep: {total - selected}")
        if filtered > 0:
            status += f"  |  Filtered (forced keep): {filtered}"
        self.status_label.setText(status)
        self._compute_pruning_estimates()

    # --- Prune ---

    def _on_prune(self):
        output_path = self.output_input.text().strip()
        if not output_path:
            QMessageBox.warning(self, "Error", "Please specify an output file path.")
            return

        dna_path = self.dna_input.text().strip()
        lib_path = self.lib_input.text().strip()

        try:
            l2_threshold = float(self.l2_input.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid L2 threshold value.")
            return

        modified_scores = self._build_modified_scores_from_gui()

        if not any(s.suggested_level in ("L0", "L1") for s in modified_scores):
            QMessageBox.warning(self, "Error", "No controls selected for pruning.")
            return

        self.btn_prune.setEnabled(False)
        self.btn_prune.setText("Pruning...")

        self.worker = PruneWorker(
            dna_path, output_path, lib_path,
            modified_scores, self.graph, self.data, l2_threshold,
        )
        self.worker.result_ready.connect(self._on_prune_done)
        self.worker.error.connect(self._on_worker_error)
        self.worker.log.connect(self._on_log)
        self.worker.start()

    def _on_prune_done(self, result):
        self.btn_prune.setEnabled(True)
        self.btn_prune.setText("Execute Pruning")

        total_bs = len(result.l0_bs_removed) + len(result.l1_bs_removed)
        msg = (
            f"Pruning complete!\n\n"
            f"L0 BS removed: {len(result.l0_bs_removed)}\n"
            f"L0 AM removed: {len(result.l0_am_removed)}\n"
            f"L0 Joint entries zeroed: {result.l0_joint_entries_zeroed}\n"
            f"L1 BS removed: {len(result.l1_bs_removed)}\n"
            f"Total BS removed: {total_bs}\n\n"
            f"Output: {result.output_path}"
        )
        self.status_label.setText(f"Done - {total_bs} BS removed -> {result.output_path}")
        QMessageBox.information(self, "Pruning Complete", msg)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
