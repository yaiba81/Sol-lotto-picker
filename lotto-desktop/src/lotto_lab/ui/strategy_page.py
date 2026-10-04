"""Typed strategy editor; built-ins and used versions are read-only."""
from dataclasses import asdict
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QComboBox, QFormLayout,
    QCheckBox, QDoubleSpinBox, QPushButton, QLabel, QScrollArea, QHBoxLayout)
from lotto_lab.strategy.config import StrategyConfig
from lotto_lab.strategy.repository import StrategyRepository
from lotto_lab.ui.feature_pages import add_page_header


class StrategyLabPage(QWidget):
    changed = Signal()

    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.setObjectName("strategy_lab")
        self.repository = StrategyRepository(database)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        add_page_header(layout, "Strategy Lab", "Clone a version, adjust positive weighting factors, and save your experiment.")
        self.versions = QComboBox()
        self.versions.setAccessibleName("Strategy version")
        layout.addWidget(self.versions)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        panel = QWidget()
        form = QFormLayout(panel)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.controls = {}
        labels = {"use_range": "Enable Range Weighting", "range_strength": "Range Weight Strength",
            "use_high_number_balance": "Enable High Number Balance",
            "structural_max_deviation": "Maximum structural deviation",
            "structural_prior_draws": "Structural smoothing prior (draws)"}
        for name, value in asdict(StrategyConfig()).items():
            if isinstance(value, bool):
                control = QCheckBox("Enabled")
            else:
                control = QDoubleSpinBox()
                control.setDecimals(4)
                control.setRange(0 if name in ("cross_game_penalty", "frequency_strength") else 0.0001, 1)
                control.setSingleStep(0.01)
                if name == "range_strength":
                    control.setRange(0, 100)
                    control.setDecimals(0)
                    control.setSingleStep(1)
                    control.setSuffix("%")
                elif name == "structural_max_deviation":
                    control.setMaximum(0.5)
                elif name == "structural_prior_draws":
                    control.setRange(0.0001, 10000)
            label = labels.get(name, name.replace("_", " ").capitalize())
            control.setAccessibleName(label)
            control.setToolTip("Positive multiplier; 1 is neutral." if name.endswith("factor") else label)
            form.addRow(label, control)
            self.controls[name] = control
        scroll.setWidget(panel)
        layout.addWidget(scroll, 1)
        guidance = QLabel("Range strength applies to both structural factors. High Number Balance is neutral below 6/55. "
            "Set the historical window in Generator or Backtesting; Analytics has its own window. "
            "Jonathan Weighted v1 preserves the original behavior; the range-enabled reference uses the next available version.")
        guidance.setWordWrap(True)
        form.addRow(guidance)
        buttons = QHBoxLayout()
        self.clone_button = QPushButton("Clone to new version")
        self.save_button = QPushButton("Save parameters")
        self.save_button.setObjectName("primaryButton")
        buttons.addWidget(self.clone_button)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.versions.currentIndexChanged.connect(self.load_version)
        self.clone_button.clicked.connect(self.clone_version)
        self.save_button.clicked.connect(self.save_version)
        self.refresh_versions()

    def refresh_versions(self, selected=None):
        selected = selected or self.versions.currentData()
        self.versions.blockSignals(True)
        self.versions.clear()
        for identifier, label in self.repository.list_versions():
            self.versions.addItem(label, identifier)
        index = self.versions.findData(selected)
        self.versions.setCurrentIndex(max(0, index))
        self.versions.blockSignals(False)
        self.load_version()

    def load_version(self):
        identifier = self.versions.currentData()
        if identifier is None:
            return
        _, config = self.repository.get_config(identifier)
        locked = self.repository.is_locked(identifier)
        for name, value in asdict(config).items():
            control = self.controls[name]
            if isinstance(value, bool):
                control.setChecked(value)
            else:
                control.setValue(value * 100 if name == "range_strength" else value)
            control.setEnabled(not locked)
        self.save_button.setEnabled(not locked)
        self.status.setText("Read-only version. Clone to edit." if locked else "Editable draft. Using it in generation or a backtest locks this version.")

    def clone_version(self):
        try:
            identifier = self.repository.clone(self.versions.currentData())
            self.refresh_versions(identifier)
            self.changed.emit()
        except Exception as exc:
            self.status.setText(f"Clone failed: {exc}")

    def save_version(self):
        try:
            values = {name: control.isChecked() if isinstance(control, QCheckBox) else control.value()
                      for name, control in self.controls.items()}
            values["range_strength"] /= 100
            self.repository.save_config(self.versions.currentData(), StrategyConfig(**values))
            self.status.setText("Parameters saved locally.")
            self.changed.emit()
        except Exception as exc:
            self.status.setText(f"Save failed: {exc}")
