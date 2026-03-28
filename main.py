"""
DocIntel — Orquestrador Principal do Pipeline
"""
import sys
import os
import time

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import init_database, get_connection
from db.operations import log_audit
from scanner.discovery import run_full_discovery
from scanner.environment import run_environment_discovery, generate_environment_map
from config.settings import OUTPUT_DIR, REPORTS_DIR


def generate_coverage_report(scan_stats: dict, env_result: dict):
    """Gera cobertura_varredura.md apos o scan."""
    path = os.path.join(REPORTS_DIR, "cobertura_varredura.md")
    lines = []
    lines.append("# Cobertura da Varredura")
    lines.append("")
    lines.append(f"> Gerado apos scan completo")
    lines.append("")
    lines.append("| Volume | Arquivos | Diretorios | Erros | Status |")
    lines.append("|--------|----------|------------|-------|--------|")
    lines.append(f"| F:\\\\ | {scan_stats.get('total_files', '?'):,} | {scan_stats.get('total_dirs', '?'):,} | {scan_stats.get('errors', '?'):,} | COMPLETO |")
    lines.append("")
    lines.append("*Volumes D:\\\\, E:\\\\ (EFI) e J:\\\\ (nao montado) foram excluidos por serem partições de sistema ou inacessiveis.*")
    lines.append("")
    lines.append("*C:\\\\ foi excluido por ser o disco do sistema operacional (prioridade BAIXA_SISTEMA).*")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[REPORT] Cobertura salva em: {path}")


def run_phase0():
    """Fase 0: Descoberta do ambiente."""
    print("\n" + "=" * 60)
    print("FASE 0: DESCOBERTA DO AMBIENTE")
    print("=" * 60)
    result = run_environment_discovery()
    map_path = os.path.join(REPORTS_DIR, "mapa_ambiente_armazenamento.md")
    generate_environment_map(result, map_path)
    log_audit("FASE_0", "ENVIRONMENT_DISCOVERY", "TODOS_VOLUMES",
              "CONCLUIDO", f"{result['total_volumes']} volumes detectados")
    return result


def run_phase_scan():
    """Etapa 2: Varredura completa de arquivos."""
    print("\n" + "=" * 60)
    print("ETAPA 2: VARREDURA COMPLETA DE ARQUIVOS")
    print("=" * 60)
    stats = run_full_discovery()
    log_audit("ETAPA_2", "FILE_DISCOVERY", "F:\\ + I:\\",
              "CONCLUIDO", f"{stats['total_files']:,} arquivos indexados")
    return stats


def print_db_summary():
    """Imprime resumo do banco de dados."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    by_disco = conn.execute(
        "SELECT disco_origem, COUNT(*) as cnt FROM files GROUP BY disco_origem ORDER BY cnt DESC"
    ).fetchall()
    by_fase = conn.execute(
        "SELECT fase_correspondente, COUNT(*) as cnt FROM files GROUP BY fase_correspondente ORDER BY cnt DESC"
    ).fetchall()
    by_ext = conn.execute(
        "SELECT extensao, COUNT(*) as cnt FROM files GROUP BY extensao ORDER BY cnt DESC LIMIT 20"
    ).fetchall()
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"RESUMO DO BANCO DE DADOS")
    print(f"{'=' * 60}")
    print(f"\nTotal de registros: {total:,}")
    print(f"\nPor disco:")
    for row in by_disco:
        print(f"  {row['disco_origem']}: {row['cnt']:,}")
    print(f"\nPor fase:")
    for row in by_fase:
        print(f"  {row['fase_correspondente'] or 'SEM_FASE'}: {row['cnt']:,}")
    print(f"\nTop 20 extensoes:")
    for row in by_ext:
        print(f"  {row['extensao'] or '(sem ext)'}: {row['cnt']:,}")


if __name__ == "__main__":
    t0 = time.time()

    # 1. Inicializar banco
    print("[MAIN] Inicializando banco de dados...")
    init_database()

    # 2. Fase 0
    env_result = run_phase0()

    # 3. Etapa 2: Scan
    scan_stats = run_phase_scan()

    # 4. Cobertura
    generate_coverage_report(scan_stats, env_result)

    # 5. Resumo
    print_db_summary()

    elapsed = time.time() - t0
    print(f"\n[MAIN] Pipeline concluido em {elapsed:.1f} segundos.")
    log_audit("MAIN", "PIPELINE_COMPLETE", "FASE_0+ETAPA_2",
              "CONCLUIDO", f"Tempo total: {elapsed:.1f}s")
