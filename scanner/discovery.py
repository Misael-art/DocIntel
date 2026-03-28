"""
DocIntel — Scanner de Descoberta Recursiva (Etapa A) — OTIMIZADO
Usa batch inserts com transacoes para performance em escala de TB.
"""
import os
import sys
import time
import sqlite3
from datetime import datetime
from config.settings import SOURCE_DRIVES, SYSTEM_EXCLUDE_DIRS, DB_PATH
from config.taxonomy import FASE_MAP_F, FASE_MAP_I


BATCH_SIZE = 2000  # Commit a cada N arquivos


def _get_fase(disco: str, pasta_raiz: str) -> str:
    fase_map = FASE_MAP_F if disco == "F:\\" else FASE_MAP_I
    return fase_map.get(pasta_raiz, "INDEFINIDO")


def scan_drive(drive_root: str, conn: sqlite3.Connection) -> dict:
    """Varre recursivamente um disco com batch inserts."""
    stats = {"total_files": 0, "total_dirs": 0, "errors": 0}
    drive_letter = os.path.splitdrive(drive_root)[0] + "\\"

    print(f"[SCAN] Iniciando varredura de {drive_root}...")
    t0 = time.time()
    batch = []

    for dirpath, dirnames, filenames in os.walk(drive_root, topdown=True):
        # Excluir diretorios de sistema
        dirnames[:] = [d for d in dirnames if d not in SYSTEM_EXCLUDE_DIRS]
        stats["total_dirs"] += 1

        rel_path = os.path.relpath(dirpath, drive_root)
        parts = rel_path.split(os.sep) if rel_path != "." else []
        pasta_raiz = parts[0] if parts else ""
        profundidade = len(parts)

        for fname in filenames:
            filepath = os.path.join(dirpath, fname)
            _, ext = os.path.splitext(fname)

            try:
                st = os.stat(filepath)
                batch.append((
                    filepath,
                    fname,
                    ext.lower() if ext else None,
                    st.st_size,
                    datetime.fromtimestamp(st.st_ctime).isoformat(),
                    datetime.fromtimestamp(st.st_mtime).isoformat(),
                    datetime.fromtimestamp(st.st_atime).isoformat(),
                    drive_letter,
                    pasta_raiz,
                    profundidade,
                    _get_fase(drive_letter, pasta_raiz),
                ))
                stats["total_files"] += 1
            except (OSError, ValueError):
                stats["errors"] += 1

            # Flush batch
            if len(batch) >= BATCH_SIZE:
                conn.executemany("""
                    INSERT OR IGNORE INTO files
                    (caminho_completo, nome_arquivo, extensao, tamanho_bytes,
                     data_criacao, data_modificacao, data_ultimo_acesso,
                     disco_origem, pasta_raiz, profundidade, fase_correspondente)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch)
                conn.commit()
                batch.clear()
                elapsed = time.time() - t0
                print(f"  [{drive_letter}] {stats['total_files']:,} arquivos... ({elapsed:.0f}s)")

    # Flush remainder
    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO files
            (caminho_completo, nome_arquivo, extensao, tamanho_bytes,
             data_criacao, data_modificacao, data_ultimo_acesso,
             disco_origem, pasta_raiz, profundidade, fase_correspondente)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)
        conn.commit()

    elapsed = time.time() - t0
    summary = (f"Arquivos: {stats['total_files']:,} | "
               f"Dirs: {stats['total_dirs']:,} | "
               f"Erros: {stats['errors']:,} | "
               f"Tempo: {elapsed:.1f}s")
    print(f"[SCAN] {drive_letter} concluido: {summary}")

    # Log de auditoria
    conn.execute("""
        INSERT INTO audit_log (etapa, acao, alvo, resultado, detalhes)
        VALUES (?, ?, ?, ?, ?)
    """, ("DISCOVERY", "SCAN_COMPLETE", drive_root, "CONCLUIDO", summary))
    conn.commit()

    return stats


def run_full_discovery() -> dict:
    """Executa a varredura completa em todos os discos configurados."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")

    total_stats = {"total_files": 0, "total_dirs": 0, "errors": 0}

    for drive in SOURCE_DRIVES:
        if os.path.exists(drive):
            stats = scan_drive(drive, conn)
            for k in total_stats:
                total_stats[k] += stats.get(k, 0)
        else:
            print(f"[SCAN] AVISO: Drive {drive} nao encontrado.")

    conn.close()

    print(f"\n[SCAN] === RESULTADO GLOBAL ===")
    print(f"  Total de arquivos: {total_stats['total_files']:,}")
    print(f"  Total de dirs: {total_stats['total_dirs']:,}")
    print(f"  Erros: {total_stats['errors']:,}")

    return total_stats


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from db.connection import init_database
    init_database()
    run_full_discovery()
