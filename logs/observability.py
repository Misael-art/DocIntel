"""
DocIntel — Modulo de Observabilidade em Tempo Real

Atualiza status_execucao.md, progresso_volumes.md, erros_execucao.md,
eventos_execucao.log e dashboard.html durante a execucao do pipeline.

REGRA: Nenhuma etapa longa pode rodar como caixa-preta.
"""
import os
import json
import time
import threading
from datetime import datetime
from config.settings import REPORTS_DIR, OUTPUT_DIR


class PipelineObserver:
    """Observador em tempo real do pipeline DocIntel."""

    def __init__(self):
        self.fase_atual = "INICIALIZACAO"
        self.volume_atual = "—"
        self.diretorio_atual = "—"
        self.arquivos_processados = 0
        self.dirs_processados = 0
        self.erros = 0
        self.erros_detalhados = []
        self.t0 = time.time()
        self.ultima_acao = "Inicializacao do pipeline"
        self.volumes_status = {}
        self.eventos = []
        self._lock = threading.Lock()
        self._update_interval = 2  # segundos
        self._log_path = os.path.join(OUTPUT_DIR, "eventos_execucao.log")

        # Inicializar log de eventos
        with open(self._log_path, "w", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] Pipeline DocIntel iniciado\n")

    def set_fase(self, fase: str):
        with self._lock:
            self.fase_atual = fase
            self._log_event(f"Fase alterada para: {fase}")

    def set_volume(self, volume: str, status: str = "EM_ANDAMENTO"):
        with self._lock:
            self.volume_atual = volume
            self.volumes_status[volume] = {
                "status": status,
                "arquivos": 0, "dirs": 0, "erros": 0,
                "inicio": datetime.now().isoformat(),
                "fim": None, "tempo_s": 0
            }
            self._log_event(f"Volume {volume}: {status}")

    def complete_volume(self, volume: str, arquivos: int, dirs: int, erros: int, tempo_s: float):
        with self._lock:
            if volume in self.volumes_status:
                self.volumes_status[volume].update({
                    "status": "COMPLETO",
                    "arquivos": arquivos, "dirs": dirs, "erros": erros,
                    "fim": datetime.now().isoformat(),
                    "tempo_s": round(tempo_s, 1)
                })
            self._log_event(f"Volume {volume}: COMPLETO ({arquivos:,} arquivos, {erros} erros, {tempo_s:.1f}s)")

    def update_progress(self, arquivos: int, dirs: int, diretorio: str = None):
        with self._lock:
            self.arquivos_processados = arquivos
            self.dirs_processados = dirs
            if diretorio:
                self.diretorio_atual = diretorio

    def record_error(self, filepath: str, error: str):
        with self._lock:
            self.erros += 1
            if len(self.erros_detalhados) < 500:
                self.erros_detalhados.append({
                    "timestamp": datetime.now().isoformat(),
                    "arquivo": filepath,
                    "erro": str(error)[:200]
                })

    def set_action(self, acao: str):
        with self._lock:
            self.ultima_acao = acao
            self._log_event(acao)

    def _log_event(self, msg: str):
        ts = datetime.now().isoformat()
        entry = f"[{ts}] {msg}\n"
        self.eventos.append(entry)
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def flush_reports(self):
        """Grava todos os relatorios de observabilidade no disco."""
        with self._lock:
            self._write_status()
            self._write_progress()
            self._write_errors()
            self._write_dashboard()

    def _write_status(self):
        elapsed = time.time() - self.t0
        rate = self.arquivos_processados / elapsed if elapsed > 0 else 0
        path = os.path.join(REPORTS_DIR, "status_execucao.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Status de Execucao — DocIntel Pipeline\n\n")
            f.write(f"> Ultima atualizacao: {datetime.now().isoformat()}\n\n")
            f.write(f"| Campo | Valor |\n|-------|-------|\n")
            f.write(f"| **Fase Atual** | {self.fase_atual} |\n")
            f.write(f"| **Volume Atual** | {self.volume_atual} |\n")
            f.write(f"| **Diretorio Atual** | `{self.diretorio_atual[:80]}` |\n")
            f.write(f"| **Arquivos Processados** | {self.arquivos_processados:,} |\n")
            f.write(f"| **Diretorios Processados** | {self.dirs_processados:,} |\n")
            f.write(f"| **Taxa** | {rate:,.0f} arquivos/s |\n")
            f.write(f"| **Tempo Decorrido** | {elapsed:.0f}s |\n")
            f.write(f"| **Ultima Acao** | {self.ultima_acao} |\n")

    def _write_progress(self):
        path = os.path.join(REPORTS_DIR, "progresso_volumes.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Progresso por Volume\n\n")
            f.write("| Volume | Status | Arquivos | Dirs | Erros | Tempo |\n")
            f.write("|--------|--------|----------|------|-------|-------|\n")
            for vol, info in self.volumes_status.items():
                f.write(f"| {vol} | **{info['status']}** | "
                        f"{info['arquivos']:,} | {info['dirs']:,} | "
                        f"{info['erros']:,} | {info['tempo_s']}s |\n")

    def _write_errors(self):
        path = os.path.join(REPORTS_DIR, "erros_execucao.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Erros de Execucao\n\n")
            f.write(f"> Total: {self.erros} erros\n\n")
            if self.erros_detalhados:
                f.write("| Timestamp | Arquivo | Erro |\n|-----------|---------|------|\n")
                for e in self.erros_detalhados[-50:]:
                    f.write(f"| {e['timestamp']} | `{e['arquivo'][:60]}` | {e['erro'][:80]} |\n")

    def _write_dashboard(self):
        """Gera dashboard HTML atualizado."""
        path = os.path.join(OUTPUT_DIR, "dashboard.html")
        elapsed = time.time() - self.t0
        rate = self.arquivos_processados / elapsed if elapsed > 0 else 0

        vol_rows = ""
        for vol, info in self.volumes_status.items():
            badge = "badge-complete" if info["status"] == "COMPLETO" else "badge-pending"
            fill = "complete" if info["status"] == "COMPLETO" else ""
            vol_rows += f"""<tr><td><strong>{vol}</strong></td>
                <td>{info['arquivos']:,}</td>
                <td><span class="badge {badge}">{info['status']}</span></td>
                <td><div class="progress-bar"><div class="progress-fill {fill}"></div></div></td></tr>"""

        html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="3"><title>DocIntel Live</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;padding:20px}}
h1{{text-align:center;font-size:1.6em;margin-bottom:16px;color:#a78bfa}}
.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px}}
.c{{background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155}}
.c h3{{font-size:.75em;text-transform:uppercase;letter-spacing:1px;color:#94a3b8;margin-bottom:4px}}
.c .v{{font-size:1.8em;font-weight:700}}table{{width:100%;border-collapse:collapse;margin:8px 0}}
th{{text-align:left;padding:8px;background:#1e293b;color:#94a3b8;font-size:.75em;text-transform:uppercase;border-bottom:2px solid #334155}}
td{{padding:8px;border-bottom:1px solid #1e293b;font-size:.85em}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.7em;font-weight:600}}
.badge-complete{{background:#052e16;color:#22c55e}}.badge-pending{{background:#1e1b4b;color:#818cf8}}
.progress-bar{{width:100%;height:6px;background:#1e293b;border-radius:3px;overflow:hidden}}
.progress-fill.complete{{height:100%;background:#22c55e;width:100%;border-radius:3px}}
.s{{background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;margin-bottom:12px}}
.s h2{{font-size:1em;margin-bottom:8px;color:#c4b5fd}}.ts{{text-align:center;color:#475569;font-size:.75em;margin-top:12px}}</style></head><body>
<h1>DocIntel Live Dashboard</h1>
<div class="g">
<div class="c"><h3>Fase</h3><div class="v">{self.fase_atual}</div></div>
<div class="c"><h3>Arquivos</h3><div class="v">{self.arquivos_processados:,}</div></div>
<div class="c"><h3>Throughput</h3><div class="v">{rate:,.0f}/s</div></div>
<div class="c"><h3>Erros</h3><div class="v" style="color:#ef4444">{self.erros}</div></div>
<div class="c"><h3>Tempo</h3><div class="v">{elapsed:.0f}s</div></div>
</div>
<div class="s"><h2>Volumes</h2><table><thead><tr><th>Volume</th><th>Arquivos</th><th>Status</th><th>Progresso</th></tr></thead>
<tbody>{vol_rows}</tbody></table></div>
<p class="ts">Auto-refresh 3s • {datetime.now().strftime('%H:%M:%S')}</p></body></html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)


# Singleton global
observer = PipelineObserver()
