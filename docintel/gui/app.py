"""PySide6 desktop launcher for the current DocIntel operational flow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from docintel.gui.runtime import (
    RuntimeContext,
    build_script_command,
    collect_runtime_context,
    open_in_shell,
)


class DocIntelLauncherWindow(QMainWindow):
    """Small but real desktop control surface for the safe operational flow."""

    def __init__(self) -> None:
        super().__init__()
        self.context = collect_runtime_context()
        self.process = QProcess(self)
        self.action_buttons: list[QPushButton] = []

        self.setWindowTitle("DocIntel Control Center")
        self.resize(1180, 760)

        self._build_ui()
        self._bind_process()
        self.refresh_context()

    def _build_ui(self) -> None:
        self.setStatusBar(QStatusBar(self))

        toolbar = QToolBar("Principal", self)
        toolbar.setMovable(False)
        refresh_action = QAction("Atualizar Contexto", self)
        refresh_action.triggered.connect(self.refresh_context)
        toolbar.addAction(refresh_action)
        self.addToolBar(toolbar)

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        left_column = QVBoxLayout()
        right_column = QVBoxLayout()

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            "background:#102a43;color:#f0f4f8;border:1px solid #243b53;"
            "padding:12px;border-radius:8px;font-size:14px;"
        )

        context_group = QGroupBox("Ambiente")
        form = QFormLayout(context_group)
        self.repo_value = QLabel()
        self.python_value = QLabel()
        self.db_value = QLabel()
        self.git_value = QLabel()
        self.remote_value = QLabel()
        for label in (
            self.repo_value,
            self.python_value,
            self.db_value,
            self.git_value,
            self.remote_value,
        ):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setWordWrap(True)
        form.addRow("Repositorio", self.repo_value)
        form.addRow("Python", self.python_value)
        form.addRow("SQLite", self.db_value)
        form.addRow("Git", self.git_value)
        form.addRow("Remote", self.remote_value)

        actions_group = QGroupBox("Acoes Seguras")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(10)

        actions = [
            ("Atualizar Status", lambda: self.run_script("monitor_extraction.py")),
            ("Supervisao Segura", lambda: self.run_script("supervise_post_extraction.py")),
            ("Planejamento Seguro", lambda: self.run_script("organization_planner.py")),
            ("Abrir Dashboard", self.open_dashboard),
            ("Abrir Relatorios", self.open_reports),
            ("Abrir README", self.open_readme),
        ]
        for text, callback in actions:
            button = QPushButton(text)
            button.setMinimumHeight(42)
            button.clicked.connect(callback)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            actions_layout.addWidget(button)
            self.action_buttons.append(button)
        actions_layout.addStretch(1)

        log_group = QGroupBox("Execucao")
        log_layout = QVBoxLayout(log_group)
        self.process_state_label = QLabel("Nenhum processo em execucao.")
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QPlainTextEdit.NoWrap)
        log_layout.addWidget(self.process_state_label)
        log_layout.addWidget(self.log_output, 1)

        left_column.addWidget(self.summary_label)
        left_column.addWidget(context_group)
        left_column.addWidget(actions_group, 1)

        right_column.addWidget(log_group, 1)

        layout.addLayout(left_column, 1)
        layout.addLayout(right_column, 2)

        self.setCentralWidget(central)

    def _bind_process(self) -> None:
        self.process.readyReadStandardOutput.connect(self._append_stdout)
        self.process.readyReadStandardError.connect(self._append_stderr)
        self.process.started.connect(self._on_process_started)
        self.process.finished.connect(self._on_process_finished)
        self.process.errorOccurred.connect(self._on_process_error)

    def refresh_context(self) -> None:
        self.context = collect_runtime_context()
        self._apply_context(self.context)
        self.statusBar().showMessage("Contexto atualizado.", 5000)

    def _apply_context(self, context: RuntimeContext) -> None:
        self.summary_label.setText(context.stage3_summary)
        self.repo_value.setText(str(context.repo_root))
        self.python_value.setText(context.python_executable)
        self.db_value.setText(str(context.db_path))
        self.git_value.setText(f"{context.git_branch} @ {context.git_commit}")
        self.remote_value.setText(context.git_remote)

    def run_script(self, script_name: str, *args: str) -> None:
        if self.process.state() != QProcess.NotRunning:
            QMessageBox.warning(
                self,
                "Processo em andamento",
                "Ja existe uma operacao em andamento. Aguarde a conclusao antes de iniciar outra.",
            )
            return

        command = build_script_command(script_name, *args)
        self.log_output.appendPlainText(f"> {' '.join(command)}")
        self.process.setProgram(command[0])
        self.process.setArguments(command[1:])
        self.process.setWorkingDirectory(str(self.context.repo_root))
        self.process.start()

    def open_dashboard(self) -> None:
        if self.context.dashboard_path.exists():
            open_in_shell(self.context.dashboard_path)
            return
        QMessageBox.information(
            self,
            "Dashboard indisponivel",
            "O dashboard ainda nao existe. Execute 'Atualizar Status' para gerar os artefatos.",
        )

    def open_reports(self) -> None:
        self.context.reports_dir.mkdir(parents=True, exist_ok=True)
        open_in_shell(self.context.reports_dir)

    def open_readme(self) -> None:
        open_in_shell(self.context.readme_path)

    def _append_stdout(self) -> None:
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="ignore")
        if data:
            self.log_output.appendPlainText(data.rstrip())

    def _append_stderr(self) -> None:
        data = bytes(self.process.readAllStandardError()).decode("utf-8", errors="ignore")
        if data:
            self.log_output.appendPlainText(data.rstrip())

    def _set_buttons_enabled(self, enabled: bool) -> None:
        for button in self.action_buttons:
            button.setEnabled(enabled)

    def _on_process_started(self) -> None:
        self._set_buttons_enabled(False)
        self.process_state_label.setText("Processo em execucao...")
        self.statusBar().showMessage("Processo iniciado.", 5000)

    def _on_process_finished(self, exit_code: int, _exit_status) -> None:
        self._set_buttons_enabled(True)
        self.process_state_label.setText(f"Processo finalizado com codigo {exit_code}.")
        self.statusBar().showMessage(f"Processo concluido com codigo {exit_code}.", 8000)
        QTimer.singleShot(1000, self.refresh_context)

    def _on_process_error(self, _error) -> None:
        self._set_buttons_enabled(True)
        self.process_state_label.setText("Falha ao iniciar o processo.")
        self.statusBar().showMessage("Falha ao iniciar o processo.", 8000)


def run_gui(*, smoke_test: bool = False) -> int:
    app = QApplication.instance() or QApplication([])
    window = DocIntelLauncherWindow()
    if smoke_test:
        QTimer.singleShot(50, window.close)
    window.show()
    return app.exec()
