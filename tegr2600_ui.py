"""
TEGR 2600 - Graphical User Interface
=====================================
Lightweight PyQt6 GUI for the TEGR 2600 research application.

Features:
    - Drag-and-drop experiment file loading (CSV, TOML, Markdown)
    - Parameter sliders for real-time adjustment
    - Live-updating Phase Coherence and Renyi Entropy charts
    - Export controls for trajectory CSV and publication-quality plots

Built for researchers: load data, click Run, get results.
"""
import sys
import os
import numpy as np
from pathlib import Path
import time
import psutil
import platform
import torch

# Add the TEGR 2600 directory to the Python path
TEGR_DIR = Path(__file__).parent
sys.path.insert(0, str(TEGR_DIR))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFileDialog, QGroupBox, QProgressBar,
    QTextEdit, QTabWidget, QSpinBox, QDoubleSpinBox, QCheckBox,
    QStatusBar, QSplitter, QComboBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData, QTimer
from PyQt6.QtGui import QFont, QColor, QDragEnterEvent, QDropEvent

import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from config_schema import SimulationConfig
from data_ingest import load_experiment
from engine import TEGR2600Engine
from entanglement_metrics import (
    compute_phase_coherence_matrix,
    full_entanglement_report,
)


# ---------------------------------------------------------------------------
# Style Constants (Atari 2600 / NASA Punk Theme)
# ---------------------------------------------------------------------------
DARK_BG = "#000000"      # Pure black
PANEL_BG = "#111111"     # Terminal gray
ACCENT = "#444444"       # Dark gray borders
HIGHLIGHT = "#ff00ff"    # Neon Magenta
TEXT_COLOR = "#00ffff"   # Neon Cyan
GRID_COLOR = "#222222"   # Dim grid lines

STYLESHEET = f"""
    QMainWindow {{
        background-color: {DARK_BG};
    }}
    QWidget {{
        background-color: {DARK_BG};
        color: {TEXT_COLOR};
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 11px;
    }}
    QGroupBox {{
        background-color: {PANEL_BG};
        border: 1px solid {ACCENT};
        border-radius: 6px;
        margin-top: 12px;
        padding: 10px;
        font-weight: bold;
        font-size: 12px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 8px;
        color: {HIGHLIGHT};
    }}
    QPushButton {{
        background-color: {ACCENT};
        color: {TEXT_COLOR};
        border: 1px solid {HIGHLIGHT};
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: bold;
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {HIGHLIGHT};
        color: white;
    }}
    QPushButton:disabled {{
        background-color: #333;
        color: #666;
        border-color: #444;
    }}
    QSlider::groove:horizontal {{
        border: 1px solid {ACCENT};
        height: 6px;
        background: {PANEL_BG};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {HIGHLIGHT};
        border: 1px solid {HIGHLIGHT};
        width: 14px;
        margin: -4px 0;
        border-radius: 7px;
    }}
    QProgressBar {{
        border: 1px solid {ACCENT};
        border-radius: 4px;
        text-align: center;
        color: white;
        font-weight: bold;
    }}
    QProgressBar::chunk {{
        background-color: {HIGHLIGHT};
        border-radius: 3px;
    }}
    QTextEdit {{
        background-color: #0d1117;
        color: #c9d1d9;
        border: 1px solid {ACCENT};
        border-radius: 4px;
        font-family: 'Consolas', monospace;
        font-size: 10px;
    }}
    QTabWidget::pane {{
        border: 1px solid {ACCENT};
        background-color: {DARK_BG};
    }}
    QTabBar::tab {{
        background-color: {PANEL_BG};
        color: {TEXT_COLOR};
        padding: 8px 16px;
        border: 1px solid {ACCENT};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected {{
        background-color: {HIGHLIGHT};
        color: white;
    }}
    QLabel {{
        color: {TEXT_COLOR};
    }}
    QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {PANEL_BG};
        color: {TEXT_COLOR};
        border: 1px solid {ACCENT};
        border-radius: 3px;
        padding: 4px;
    }}
"""


# ---------------------------------------------------------------------------
# Simulation Worker Thread
# ---------------------------------------------------------------------------
class SimulationWorker(QThread):
    """Runs the TEGR 2600 engine in a background thread."""

    progress = pyqtSignal(int, int, dict)   # tick, total, stats
    finished = pyqtSignal()                 # empty signal, trajectory is stored as attribute
    error = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, engine: TEGR2600Engine, state, adjacency):
        super().__init__()
        self.engine = engine
        self.state = state
        self.adjacency = adjacency
        self.trajectory = None

    def run(self):
        try:
            # Redirect progress to signal
            def on_progress(tick, total, stats):
                self.progress.emit(tick, total, stats)

            self.engine.set_progress_callback(on_progress)
            self.trajectory = self.engine.run(self.state, self.adjacency)
            self.finished.emit()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# Matplotlib Canvas Widgets
# ---------------------------------------------------------------------------
class CoherenceCanvas(FigureCanvas):
    """Phase coherence matrix heatmap."""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(4, 3.5), facecolor=DARK_BG)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self._style_axes()

    def _style_axes(self):
        self.ax.set_facecolor(DARK_BG)
        self.ax.tick_params(colors=TEXT_COLOR)
        self.ax.set_title("Phase Coherence Matrix", color=HIGHLIGHT, fontsize=11, fontweight='bold')
        for spine in self.ax.spines.values():
            spine.set_color(ACCENT)

    def update_plot(self, coherence_matrix):
        self.ax.clear()
        self._style_axes()
        n = coherence_matrix.shape[0]
        im = self.ax.imshow(coherence_matrix, cmap='RdBu_r', vmin=-1, vmax=1,
                           interpolation='nearest')
        self.ax.set_xticks(range(n))
        self.ax.set_yticks(range(n))
        self.ax.set_xlabel("Particle j", color=TEXT_COLOR, fontsize=9)
        self.ax.set_ylabel("Particle i", color=TEXT_COLOR, fontsize=9)

        # Annotate cells with black text for readability (only for small N)
        if n <= 15:
            for i in range(n):
                for j in range(n):
                    val = coherence_matrix[i, j]
                    self.ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                               color='black', fontsize=9, fontweight='bold')

        self.fig.tight_layout()
        self.draw()


class EntropyCanvas(FigureCanvas):
    """Renyi entropy time series or sweep plot."""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(5, 3.5), facecolor=DARK_BG)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self._style_axes()

    def _style_axes(self):
        self.ax.set_facecolor(DARK_BG)
        self.ax.tick_params(colors=TEXT_COLOR)
        self.ax.set_title("Entanglement Analysis", color=HIGHLIGHT, fontsize=11, fontweight='bold')
        self.ax.grid(True, alpha=0.2, color=GRID_COLOR)
        for spine in self.ax.spines.values():
            spine.set_color(ACCENT)

    def plot_entropy_timeseries(self, trajectory, partition_a, partition_b):
        """Plot running purity and entropy over simulation time."""
        self.ax.clear()
        self._style_axes()

        T, N, _ = trajectory.shape
        window = max(T // 50, 10)  # Rolling window size
        purities = []
        entropies = []
        times = []

        for t_end in range(window, T, window):
            t_start = max(0, t_end - window)
            chunk = trajectory[t_start:t_end]
            hues = chunk[:, :, 8]  # (window, N)

            # Detrend: subtract mean phase per timestep (rotating frame)
            mean_phase = np.mean(hues, axis=1, keepdims=True)
            detrended = hues - mean_phase

            # Compute coherence for subsystem A
            a_idx = partition_a
            sub_a = detrended[:, a_idx]
            dtheta = sub_a[:, :, np.newaxis] - sub_a[:, np.newaxis, :]
            coh_mean = np.mean(np.cos(dtheta))
            purity = max(min(coh_mean, 1.0), 1e-10)
            entropy = -np.log(purity)

            purities.append(purity)
            entropies.append(entropy)
            times.append(t_end)

        self.ax.plot(times, purities, color=HIGHLIGHT, linewidth=2,
                    label='Purity Tr(rho^2)', alpha=0.9)
        self.ax.plot(times, entropies, color='#00d2ff', linewidth=2,
                    label='S2 Renyi Entropy', linestyle='--', alpha=0.9)

        self.ax.set_xlabel("Tick", color=TEXT_COLOR, fontsize=9)
        self.ax.set_ylabel("Value", color=TEXT_COLOR, fontsize=9)
        self.ax.legend(facecolor=PANEL_BG, edgecolor=ACCENT,
                      labelcolor=TEXT_COLOR, fontsize=8)

        self.fig.tight_layout()
        self.draw()

    def plot_report(self, report: dict):
        """Plot purity bar chart from entanglement report."""
        self.ax.clear()
        self._style_axes()

        partitions = report.get('partitions', {})
        labels = list(partitions.keys())
        purities = [partitions[k]['purity'] for k in labels]
        entropies = [partitions[k]['entropy'] for k in labels]

        x = np.arange(len(labels))
        width = 0.35

        self.ax.bar(x - width/2, purities, width, color=HIGHLIGHT,
                   label='Purity', alpha=0.8)
        self.ax.bar(x + width/2, entropies, width, color='#00d2ff',
                   label='S2 Entropy', alpha=0.8)

        self.ax.set_xticks(x)
        self.ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
        self.ax.set_ylabel("Value", color=TEXT_COLOR, fontsize=9)
        self.ax.legend(facecolor=PANEL_BG, edgecolor=ACCENT,
                      labelcolor=TEXT_COLOR, fontsize=8)

        self.fig.tight_layout()
        self.draw()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class TEGR2600Window(QMainWindow):
    """Main application window for TEGR 2600."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TEGR 2600 - Teleparallel Gravity Research Engine")
        self.setMinimumSize(1200, 750)
        self.setAcceptDrops(True)

        # State
        self.config = SimulationConfig()
        self.state_vector = None
        self.adjacency = None
        self.metadata = {}
        self.trajectory = None
        self.worker = None
        self.loaded_filepath = None

        self._build_ui()
        self.setStyleSheet(STYLESHEET)
        self.statusBar().showMessage("Ready. Drag & drop a CSV, TOML, or Markdown file to load.")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ---- LEFT PANEL: Controls ----
        left_panel = QVBoxLayout()
        left_panel.setSpacing(6)

        # File Loading
        file_group = QGroupBox("Experiment Data")
        file_layout = QVBoxLayout(file_group)
        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet(f"color: {HIGHLIGHT}; font-weight: bold;")
        self.btn_load = QPushButton("Load File...")
        self.btn_load.clicked.connect(self._load_file_dialog)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.btn_load)
        left_panel.addWidget(file_group)

        # Parameters
        params_group = QGroupBox("Simulation Parameters")
        params_layout = QVBoxLayout(params_group)

        # Pauli Strength
        self.pauli_spin = QDoubleSpinBox()
        self.pauli_spin.setRange(0.0, 1000.0)
        self.pauli_spin.setValue(10.0)
        self.pauli_spin.setPrefix("Pauli (U): ")
        self.pauli_spin.setSingleStep(1.0)
        params_layout.addWidget(self.pauli_spin)

        # Torsion Coupling
        self.torsion_spin = QDoubleSpinBox()
        self.torsion_spin.setRange(0.0, 100.0)
        self.torsion_spin.setValue(1.0)
        self.torsion_spin.setPrefix("Torsion (J): ")
        self.torsion_spin.setSingleStep(0.1)
        params_layout.addWidget(self.torsion_spin)

        # U/J Ratio Display
        self.ratio_label = QLabel("U/J = 10.0")
        self.ratio_label.setStyleSheet(f"color: {HIGHLIGHT}; font-size: 14px; font-weight: bold;")
        self.pauli_spin.valueChanged.connect(self._update_ratio)
        self.torsion_spin.valueChanged.connect(self._update_ratio)
        params_layout.addWidget(self.ratio_label)

        # Total Ticks
        self.ticks_spin = QSpinBox()
        self.ticks_spin.setRange(100, 1000000)
        self.ticks_spin.setValue(10000)
        self.ticks_spin.setPrefix("Ticks: ")
        self.ticks_spin.setSingleStep(1000)
        params_layout.addWidget(self.ticks_spin)

        # Grid Resolution
        self.grid_combo = QComboBox()
        self.grid_combo.addItems(["32", "64", "128"])
        self.grid_combo.setCurrentText("64")
        params_layout.addWidget(QLabel("Grid Resolution:"))
        params_layout.addWidget(self.grid_combo)

        # RAE Mode
        self.rae_check = QCheckBox("RAE Phase Clock")
        self.rae_check.setChecked(True)
        params_layout.addWidget(self.rae_check)

        # Pilot Wave
        self.pilot_check = QCheckBox("Pilot Wave Guidance")
        self.pilot_check.setChecked(True)
        params_layout.addWidget(self.pilot_check)

        # Kuramoto Sync (OFF by default = discovery mode)
        self.kuramoto_check = QCheckBox("Kuramoto Sync (validation)")
        self.kuramoto_check.setChecked(False)
        self.kuramoto_check.setToolTip(
            "OFF = Discovery Mode: phases evolve from RAE + Pauli + FDTD only.\n"
            "ON = Validation Mode: adjacency matrix forces phase sync (circular).\n"
            "Run both ways and compare to verify physics."
        )
        params_layout.addWidget(self.kuramoto_check)

        left_panel.addWidget(params_group)

        # Run Controls
        run_group = QGroupBox("Execute")
        run_layout = QVBoxLayout(run_group)

        self.btn_run = QPushButton("Run Simulation")
        self.btn_run.setStyleSheet(f"""
            QPushButton {{
                background-color: {HIGHLIGHT};
                font-size: 14px;
                padding: 12px;
            }}
        """)
        self.btn_run.clicked.connect(self._run_simulation)
        self.btn_run.setEnabled(False)
        run_layout.addWidget(self.btn_run)

        self.timer_label = QLabel("Time: 00:00")
        self.timer_label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 14px; font-weight: bold;")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        run_layout.addWidget(self.timer_label)

        self.sim_timer = QTimer()
        self.sim_timer.timeout.connect(self._update_timer)
        self.sim_seconds = 0

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        run_layout.addWidget(self.progress_bar)

        self.btn_export = QPushButton("Export Results")
        self.btn_export.clicked.connect(self._export_results)
        self.btn_export.setEnabled(False)
        run_layout.addWidget(self.btn_export)
        
        self.btn_export_lattlib = QPushButton("Export to Lattlib (.npy)")
        self.btn_export_lattlib.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: #00ff00;
                border: 1px solid #00ff00;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #00ff00;
                color: black;
            }}
            QPushButton:disabled {{
                background-color: #333;
                color: #666;
                border-color: #444;
            }}
        """)
        self.btn_export_lattlib.clicked.connect(self._export_lattlib)
        self.btn_export_lattlib.setEnabled(False)
        run_layout.addWidget(self.btn_export_lattlib)

        left_panel.addWidget(run_group)
        left_panel.addStretch()

        # ---- RIGHT PANEL: Visualization ----
        right_panel = QVBoxLayout()

        # Tab widget for plots
        self.tabs = QTabWidget()

        # Tab 1: Coherence Matrix
        self.coherence_canvas = CoherenceCanvas()
        self.tabs.addTab(self.coherence_canvas, "Phase Coherence")

        # Tab 2: Entropy Analysis
        self.entropy_canvas = EntropyCanvas()
        self.tabs.addTab(self.entropy_canvas, "Entropy Analysis")

        # Tab 3: Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.tabs.addTab(self.log_output, "Console Log")

        right_panel.addWidget(self.tabs)

        # Layout assembly
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(300)

        right_widget = QWidget()
        right_widget.setLayout(right_panel)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, stretch=1)

    # ---- Drag and Drop ----
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(('.csv', '.toml', '.md')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.csv', '.toml', '.md')):
                self._load_file(path)
                return

    # ---- File Loading ----
    def _load_file_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Load Experiment",
            str(Path(__file__).parent),
            "Experiment Files (*.toml *.csv *.md *.npy);;All Files (*)"
        )
        if filepath:
            self._load_file(filepath)

    def _load_file(self, filepath: str):
        try:
            self.state_vector, self.adjacency, self.metadata = load_experiment(filepath)
            self.loaded_filepath = filepath
            name = self.metadata.get('name', Path(filepath).stem)
            n = self.metadata['num_particles']
            self.file_label.setText(f"{name}\n({n} particles)")
            self.btn_run.setEnabled(True)
            self.log(f"Loaded: {filepath}")
            self.log(f"  Particles: {n}")
            self.log(f"  Format: {self.metadata.get('format', '?')}")
            self.log(f"  Units: mass={self.metadata.get('mass_unit', '?')}, "
                    f"pos={self.metadata.get('position_unit', '?')}")
            self.statusBar().showMessage(f"Loaded {n} particles from {Path(filepath).name}")

            # If TOML, load config from it
            if filepath.lower().endswith('.toml'):
                self.config = SimulationConfig.from_toml(filepath)
                self._sync_ui_from_config()

        except Exception as e:
            self.log(f"ERROR loading file: {e}")
            self.statusBar().showMessage(f"Error: {e}")

    def _sync_ui_from_config(self):
        """Update UI controls from loaded config."""
        self.pauli_spin.setValue(self.config.pauli_strength)
        self.torsion_spin.setValue(self.config.torsion_coupling)
        self.ticks_spin.setValue(self.config.total_ticks)
        self.grid_combo.setCurrentText(str(self.config.grid_resolution))
        self.rae_check.setChecked(self.config.rae_mode)
        self.pilot_check.setChecked(self.config.pilot_wave)
        self.kuramoto_check.setChecked(self.config.kuramoto_enabled)
        self._update_ratio()

    def _update_ratio(self):
        u = self.pauli_spin.value()
        j = self.torsion_spin.value()
        ratio = u / j if j > 0 else float('inf')
        self.ratio_label.setText(f"U/J = {ratio:.1f}")

    def _update_timer(self):
        self.sim_seconds += 1
        m, s = divmod(self.sim_seconds, 60)
        self.timer_label.setText(f"Time: {m:02d}:{s:02d}")

    # ---- Simulation ----
    def _run_simulation(self):
        if self.state_vector is None:
            return

        # Build config from UI
        self.config.pauli_strength = self.pauli_spin.value()
        self.config.torsion_coupling = self.torsion_spin.value()
        self.config.total_ticks = self.ticks_spin.value()
        self.config.grid_resolution = int(self.grid_combo.currentText())
        self.config.rae_mode = self.rae_check.isChecked()
        self.config.pilot_wave = self.pilot_check.isChecked()
        self.config.kuramoto_enabled = self.kuramoto_check.isChecked()
        self.config.output_dir = str(TEGR_DIR / 'output')

        errors = self.config.validate()
        if errors:
            self.log(f"Config validation failed: {'; '.join(errors)}")
            return

        # Disable controls during run
        self.btn_run.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_export_lattlib.setEnabled(False)
        self.progress_bar.setValue(0)

        uj = self.config.pauli_strength / self.config.torsion_coupling if self.config.torsion_coupling > 0 else float('inf')
        self.log(f"\n{'='*60}")
        self.log(f"  TEGR 2600 Simulation Run")
        self.log(f"{'='*60}")
        self.log(f"  File:                 {self.loaded_filepath or 'N/A'}")
        self.log(f"  Particles:            {self.config.num_particles}")
        self.log(f"  Device:               {self.config.device}")
        self.log(f"{'='*60}")
        self.log(f"  Pauli (U):            {self.config.pauli_strength}")
        self.log(f"  Torsion (J):          {self.config.torsion_coupling}")
        self.log(f"  U/J Ratio:            {uj:.2f}")
        self.log(f"  RAE Phase Clock:      {'ON' if self.config.rae_mode else 'OFF'}")
        self.log(f"  Pilot Wave Guidance:  {'ON' if self.config.pilot_wave else 'OFF'}")
        self.log(f"  Kuramoto Sync:        {'ON (validation)' if self.config.kuramoto_enabled else 'OFF (discovery)'}")
        self.log(f"  Kuramoto K:           {self.config.kuramoto_k}")
        self.log(f"  Vacuum Damping:       {'ON' if self.config.vacuum_enabled else 'OFF'} ({self.config.vacuum_damping})")
        self.log(f"  Wave Speed:           {self.config.wave_speed}")
        self.log(f"  Wave Decay:           {self.config.wave_decay}")
        self.log(f"  Grid Resolution:      {self.config.grid_resolution}^3")
        self.log(f"  Total Ticks:          {self.config.total_ticks}")
        self.log(f"  dt:                   {self.config.dt}")
        self.log(f"{'='*60}")

        # Launch worker thread
        self.sim_seconds = 0
        self.run_start_time = time.time()
        self.timer_label.setText("Time: 00:00")
        self.sim_timer.start(1000)

        engine = TEGR2600Engine(self.config)
        self.worker = SimulationWorker(engine, self.state_vector, self.adjacency)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, tick, total, stats):
        pct = int(100 * tick / total) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.statusBar().showMessage(
            f"Tick {tick}/{total} | theta_std={stats.get('theta_std', 0):.4f} | "
            f"{stats.get('elapsed', 0):.1f}s"
        )

    def _on_finished(self):
        self.sim_timer.stop()
        act_N = self.state_vector.shape[0] if self.state_vector is not None else self.config.num_particles
        self.trajectory = self.worker.trajectory[:, :act_N, :]
        self.progress_bar.setValue(100)
        self.btn_run.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_export_lattlib.setEnabled(True)

        T, N, _ = self.trajectory.shape
        elapsed = time.time() - self.run_start_time
        
        # Log basic simulation metrics
        self.log(f"Simulation complete: {T} ticks, {N} particles in {elapsed:.2f} seconds")
        
        # Log system resources
        self.log(f"\n--- System Resources Used ---")
        self.log(f"CPU: {platform.processor()} ({psutil.cpu_count(logical=False)} Cores) | Util: {psutil.cpu_percent()}%")
        
        vm = psutil.virtual_memory()
        self.log(f"DRAM (System RAM): {vm.used / (1024**3):.1f} GB used / {vm.total / (1024**3):.1f} GB total ({vm.percent}%)")
        
        if torch.cuda.is_available():
            self.log(f"GPU: {torch.cuda.get_device_name(0)}")
            self.log(f"VRAM Allocated: {torch.cuda.memory_allocated(0) / (1024**3):.2f} GB")
            self.log(f"VRAM Reserved:  {torch.cuda.memory_reserved(0) / (1024**3):.2f} GB")
        else:
            self.log("GPU: No CUDA GPU detected.")
        self.log(f"-----------------------------\n")

        # Compute and display metrics
        self._update_plots()

        self.statusBar().showMessage("Simulation complete. Results ready for export.")

    def _on_error(self, error_msg):
        self.sim_timer.stop()
        self.log(f"SIMULATION ERROR: {error_msg}")
        self.btn_run.setEnabled(True)
        self.statusBar().showMessage(f"Error: {error_msg}")

    # ---- Visualization ----
    def _update_plots(self):
        if self.trajectory is None:
            return

        N = self.trajectory.shape[1]

        # Phase Coherence Matrix
        coherence = compute_phase_coherence_matrix(self.trajectory)
        self.coherence_canvas.update_plot(coherence)

        # Entropy Analysis
        partition_a = list(range(N // 2))
        partition_b = list(range(N // 2, N))
        self.entropy_canvas.plot_entropy_timeseries(
            self.trajectory, partition_a, partition_b
        )

        # Full report to log
        report = full_entanglement_report(self.trajectory, N)
        self.log(f"\n--- Entanglement Report ---")

        # Full system purity from coherence matrix
        coh = report.get('coherence_matrix', coherence)
        full_purity = float(np.mean(coh))
        full_s2 = -np.log(max(full_purity, 1e-10))
        self.log(f"Full system purity: {full_purity:.4f}")
        self.log(f"Full system S2:     {full_s2:.4f}")

        # Per-partition purities and entropies
        purities = report.get('purities', {})
        entropies = report.get('entropies', {})
        for key in purities:
            self.log(f"  Subsystem {key}: purity={purities[key]:.4f}, S2={entropies.get(key, 0):.4f}")

        # Mutual information
        mutual_info = report.get('mutual_info', {})
        for key, val in mutual_info.items():
            self.log(f"  MI{key} = {val:.4f}")

        # Switch to coherence tab
        self.tabs.setCurrentIndex(0)

    # ---- Export ----
    def _export_results(self):
        if self.trajectory is None:
            return

        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Save trajectory
        np.save(out_dir / 'trajectory.npy', self.trajectory)
        self.log(f"Saved: {out_dir / 'trajectory.npy'}")

        # Save final state CSV
        header = 't,x,y,z,px,py,pz,m0,theta_hue,gamma'
        np.savetxt(
            out_dir / 'final_state.csv', self.trajectory[-1],
            delimiter=',', header=header, comments='', fmt='%.6f'
        )
        self.log(f"Saved: {out_dir / 'final_state.csv'}")

        # Save plots
        fmt = self.config.plot_format
        self.coherence_canvas.fig.savefig(
            out_dir / f'coherence_matrix.{fmt}',
            dpi=300, facecolor=DARK_BG, bbox_inches='tight'
        )
        self.entropy_canvas.fig.savefig(
            out_dir / f'entropy_analysis.{fmt}',
            dpi=300, facecolor=DARK_BG, bbox_inches='tight'
        )
        self.log(f"Saved plots to {out_dir}")
        self.statusBar().showMessage(f"Results exported to {out_dir}")

    def _export_lattlib(self):
        if self.worker is None or self.worker.engine is None:
            self.log("ERROR: No active simulation engine to export from.")
            return
            
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / 'thermalized_lattice.npy'
        
        try:
            # 1. Grab the 3D PyTorch tensor from the engine's current state
            phi_3d = self.worker.engine._phi_curr.detach().cpu().numpy()
            
            # 2. Extract a 2D slice for 1+1D Schwinger
            z_mid = phi_3d.shape[2] // 2
            phi_2d = phi_3d[0, 0, :, :, z_mid] if phi_3d.ndim == 5 else phi_3d[:, :, z_mid]
            
            # 3. Map the TEGR scalar amplitude to U(1) compact phase angles [-pi, pi]
            phase_array = np.mod(phi_2d, 2 * np.pi) - np.pi
            
            # 4. Convert to U(1) complex links
            u1_links = np.exp(1j * phase_array)
            
            # 5. Save
            np.save(out_file, u1_links)
            
            self.log(f"\n--- Lattlib Export Successful ---")
            self.log(f"Extracted 2D U(1) Lattice Shape: {u1_links.shape}")
            self.log(f"Saved Lattlib-compatible matrix to: {out_file}")
            self.statusBar().showMessage(f"Lattlib matrix exported to {out_file.name}")
            
            # --- Automatic Lattlib Validation ---
            self._run_lattlib_validation(u1_links)
            
        except Exception as e:
            self.log(f"ERROR exporting to lattlib format: {e}")
            self.statusBar().showMessage(f"Lattlib export failed: {e}")

    def _run_lattlib_validation(self, u1_links):
        """Attempts to run Kanwar's lattlib natively in the GUI to prove compatibility."""
        self.log("\n--- Validating with Lattlib ---")
        
        import sys
        import os
        
        # Inject the local lattlib path if it exists (for your machine)
        local_lattlib = os.path.abspath(r"C:\Users\Myna Bird\.gemini\antigravity\brain\3269c25f-d3d1-4abe-b2a7-46f098d00d85\scratch\lattlib")
        if os.path.exists(local_lattlib) and local_lattlib not in sys.path:
            sys.path.append(local_lattlib)
            
        try:
            from schwinger.schwinger import ensemble_plaqs
            from schwinger.schwinger_heatbath import SchwingerHBAction
        except ImportError:
            self.log("Note: Lattlib not found in Python path. Skipping internal validation check.")
            self.log("Dr. Kanwar's team will be able to load the .npy file on their end.")
            return
            
        try:
            Lx, Lt = u1_links.shape
            cfg = np.zeros((2, Lx, Lt), dtype=complex)
            cfg[0, :, :] = u1_links
            cfg[1, :, :] = u1_links
            
            beta = 1.0
            action = SchwingerHBAction(beta)
            
            initial_plaq = np.mean(ensemble_plaqs(cfg))
            self.log(f"Initial Plaquette: {np.real(initial_plaq):.4f}")
            
            self.log("Running 50 Heatbath MCMC sweeps natively...")
            for _ in range(50):
                action.heatbath_update(cfg)
                
            final_plaq = np.mean(ensemble_plaqs(cfg))
            self.log(f"Final Plaquette:   {np.real(final_plaq):.4f}")
            self.log("Success! Lattlib MCMC seamlessly accepted and stepped the TEGR lattice.")
        except Exception as e:
            self.log(f"Lattlib validation error: {e}")

    # ---- Logging ----
    def log(self, msg: str):
        self.log_output.append(msg)
        # Auto-scroll to bottom
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TEGR 2600")
    app.setStyle("Fusion")

    window = TEGR2600Window()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
