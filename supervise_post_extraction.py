"""
DocIntel - Safe post-extraction supervisor.

This script is intended for manual runs or automation:
  - checks whether Stage 3 is complete for FASE_1 and FASE_2
  - runs the post-extraction gate when complete
  - generates a safe organization plan for Drive_Pessoal
  - never copies files unless explicitly asked with --execute-copy
"""
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime

from config.settings import ORGANIZATION_REPORTS_DIR, REPORTS_DIR
from docintel.core.enums import ExecutionMode
from docintel.core.models import ExecutionRequest
from docintel.guardrails import evaluate_execution_request


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
GATE_SCRIPT = os.path.join(ROOT_DIR, "post_extraction_gate.py")
ORG_SCRIPT = os.path.join(ROOT_DIR, "organization_planner.py")
GATE_OK = os.path.join(ROOT_DIR, "GATE_ETAPA4_APROVADO.md")
STATUS_REPORT = os.path.join(REPORTS_DIR, "status_execucao.md")
SUPERVISION_REPORT = os.path.join(ORGANIZATION_REPORTS_DIR, "supervisao_pos_indexacao.md")


def parse_args():
    parser = argparse.ArgumentParser(description="Supervise Stage 3 completion and prepare safe organization.")
    parser.add_argument("--execute-copy", action="store_true",
                        help="After supervision, execute copy-only organization. Requires GATE_ETAPA4_APROVADO.md.")
    parser.add_argument("--manifest",
                        help="Executable manifest path required for copy/apply mode.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Optional limit passed to the organization planner for testing.")
    return parser.parse_args()


def stage3_status() -> dict:
    if not os.path.exists(STATUS_REPORT):
        raise SystemExit(f"[SUPERVISOR] Relatorio de status nao encontrado: {STATUS_REPORT}")

    raw = open(STATUS_REPORT, "r", encoding="utf-8").read()
    match = re.search(r"\*\*Arquivos Processados\*\* \| ([0-9,]+) / ([0-9,]+)", raw)
    if not match:
        raise SystemExit("[SUPERVISOR] Nao foi possivel interpretar o progresso em status_execucao.md")

    done = int(match.group(1).replace(",", ""))
    total = int(match.group(2).replace(",", ""))
    pending = max(total - done, 0)
    return {
        "pending_f1_f2": pending,
        "done_f1_f2": done,
        "target_total_f1_f2": total,
        "stage3_complete": total > 0 and pending == 0,
    }


def run_python_script(script_path: str, extra_args=None):
    cmd = [sys.executable, script_path]
    if extra_args:
        cmd.extend(extra_args)
    subprocess.run(cmd, check=True, cwd=ROOT_DIR)


def write_supervision_report(status: dict, execute_copy: bool):
    os.makedirs(os.path.dirname(SUPERVISION_REPORT), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# Supervisao Pos-Indexacao")
    lines.append("")
    lines.append(f"> Gerado em: {ts}")
    lines.append("")
    lines.append("| Campo | Valor |")
    lines.append("|-------|-------|")
    lines.append(f"| Alvo FASE_1+FASE_2 | {status['target_total_f1_f2']:,} |")
    lines.append(f"| Concluidos em FASE_1+FASE_2 | {status['done_f1_f2']:,} |")
    lines.append(f"| Pendentes em FASE_1+FASE_2 | {status['pending_f1_f2']:,} |")
    lines.append(f"| Stage 3 completo | {'SIM' if status['stage3_complete'] else 'NAO'} |")
    lines.append(f"| Execucao de copia solicitada | {'SIM' if execute_copy else 'NAO'} |")
    lines.append("")
    lines.append("## Acoes")
    lines.append("")
    if status["stage3_complete"]:
        lines.append("- Gate pos-extracao executado.")
        lines.append("- Plano seguro de organizacao para Drive_Pessoal gerado.")
        if execute_copy:
            lines.append("- Execucao de copia foi autorizada e acionada.")
        else:
            lines.append("- Nenhuma copia foi executada; operacao ficou em modo seguro.")
    else:
        lines.append("- Indexacao ainda em andamento; nenhuma organizacao foi disparada.")

    with open(SUPERVISION_REPORT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main():
    args = parse_args()
    status = stage3_status()

    if not status["stage3_complete"]:
        print(f"[SUPERVISOR] Stage 3 ainda em andamento. Pendentes FASE_1+FASE_2: {status['pending_f1_f2']:,}")
        write_supervision_report(status, execute_copy=False)
        return

    print("[SUPERVISOR] Stage 3 concluido. Rodando gate pos-extracao...")
    run_python_script(GATE_SCRIPT)

    print("[SUPERVISOR] Gerando plano seguro de organizacao...")
    org_args = []
    if args.limit > 0:
        org_args.extend(["--limit", str(args.limit)])
    if args.execute_copy:
        decision = evaluate_execution_request(
            ExecutionRequest(
                mode=ExecutionMode.APPLY,
                manual_approval_present=os.path.exists(GATE_OK),
                manifest_path=args.manifest,
                validation_completed=True,
            )
        )
        if not decision.allowed:
            blockers = ", ".join(decision.blockers)
            raise SystemExit(f"[SUPERVISOR] Execucao de copia bloqueada: {blockers}")
        org_args.extend(["--execute", "--manifest", args.manifest])
    run_python_script(ORG_SCRIPT, org_args)

    write_supervision_report(status, execute_copy=args.execute_copy)
    print(f"[SUPERVISOR] Relatorio salvo em: {SUPERVISION_REPORT}")


if __name__ == "__main__":
    main()
