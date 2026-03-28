r"""
DocIntel - Planejador de organizacao operacional multi-destino.

Modo padrao:
  - reutiliza a base atual do DocIntel
  - deriva classificacao operacional por arquivo
  - inclui auditoria formal de C:\\ em Desktop/Downloads/Documents
  - gera manifests menores por destino e por fila de revisao
  - preserva um manifest consolidado apenas por compatibilidade

Modo de execucao:
  - processa um manifest especifico em copy-first
  - nunca move ou apaga a origem
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import shutil
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timedelta

from config.organization_policy import (
    ACTION_COPY,
    ACTION_DRAIN_C,
    ACTION_KEEP,
    ACTION_REVIEW,
    BACKUP_PATH_HINTS,
    COLLECTIONS,
    CRITICAL_PATH_HINTS,
    DESTINATIONS,
    DESTINATION_SUBDIRS,
    HEAVY_EXTENSIONS,
    HEAVY_FILE_THRESHOLD_BYTES,
    HEAVY_PATH_HINTS,
    PERSONAL_DOC_EXTENSIONS,
    POLICY_VERSION,
    PROGRAM_EXTENSIONS,
    PROJECT_CODE_EXTENSIONS,
    PROJECT_PATH_HINTS,
)
from config.settings import (
    CRITICAL_DOC_EXTENSIONS,
    DB_PATH,
    GOOGLE_DRIVE_MAX_FILE_SIZE_BYTES,
    ORGANIZATION_REPORTS_DIR,
    PROJECT_MARKERS,
    SOURCE_DRIVES,
)
from db.connection import init_database
from db.operations import log_audit
from storage_audit import get_volume_info, iter_c_user_files, summarize_c_user_targets


MANIFEST_DIR = ORGANIZATION_REPORTS_DIR
COMBINED_MANIFEST_PATH = os.path.join(MANIFEST_DIR, "organization_manifest.csv")
SUMMARY_PATH = os.path.join(MANIFEST_DIR, "organization_summary.md")
TOP_RISKS_PATH = os.path.join(MANIFEST_DIR, "top_riscos_operacionais.md")
EXECUTION_LOG_PATH = os.path.join(MANIFEST_DIR, "organization_execution_log.csv")

MANIFEST_PATHS = {
    "GOOGLE_DRIVE": os.path.join(MANIFEST_DIR, "google_drive_manifest.csv"),
    "C_DRAIN": os.path.join(MANIFEST_DIR, "drain_c_manifest.csv"),
    "I_DRIVE": os.path.join(MANIFEST_DIR, "i_drive_curated_manifest.csv"),
    "F_DRIVE": os.path.join(MANIFEST_DIR, "f_drive_cold_storage_manifest.csv"),
    "REVIEW": os.path.join(MANIFEST_DIR, "review_queue_manifest.csv"),
}

MANIFEST_FIELDS = [
    "file_id",
    "source_path",
    "source_drive",
    "fase_correspondente",
    "status_indexacao",
    "size_bytes",
    "hash_sha256",
    "categoria_operacional",
    "temperatura_acesso",
    "destino_recomendado",
    "colecao_canonica",
    "confidence_label",
    "recommended_action",
    "normalized_name",
    "destination_logical",
    "destination_path",
    "decision_reason",
    "risk_level",
    "duplicate_hint",
    "execution_blockers",
    "requires_human_review",
]


EXECUTABLE_MANIFEST_REQUIRED_FIELDS = {
    "file_id",
    "source_path",
    "recommended_action",
    "destination_path",
    "execution_blockers",
    "hash_sha256",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Generate or execute a multi-destination operational plan.")
    parser.add_argument("--execute", action="store_true", help="Execute copy actions from a manifest.")
    parser.add_argument("--manifest", default=COMBINED_MANIFEST_PATH, help="Manifest path for execution or compatibility output.")
    parser.add_argument("--execution-log", default=EXECUTION_LOG_PATH, help="CSV log for execution mode.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for DB rows; 0 means full inventory.")
    parser.add_argument("--skip-c-audit", action="store_true", help="Do not scan C:\\ user folders in this run.")
    return parser.parse_args()


def validate_execution_manifest(manifest_path: str):
    if not os.path.exists(manifest_path):
        raise SystemExit(f"[ORG] Manifest nao encontrado: {manifest_path}")

    with open(manifest_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(EXECUTABLE_MANIFEST_REQUIRED_FIELDS - fieldnames)
        if missing:
            raise SystemExit(
                "[ORG] Manifest invalido para execucao real. "
                f"Campos ausentes: {', '.join(missing)}"
            )


def get_read_conn():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    return conn


def iter_db_rows(conn: sqlite3.Connection, limit: int = 0):
    sql = """
        SELECT id, caminho_completo, nome_arquivo, extensao, tamanho_bytes,
               hash_sha256, disco_origem, pasta_raiz, fase_correspondente,
               status_indexacao, data_modificacao
        FROM files
        WHERE disco_origem IN ({placeholders})
        ORDER BY id
    """
    placeholders = ", ".join("?" for _ in SOURCE_DRIVES)
    sql = sql.format(placeholders=placeholders)
    if limit > 0:
        sql += f" LIMIT {int(limit)}"
    for row in conn.execute(sql, tuple(SOURCE_DRIVES)):
        yield {
            "file_id": row["id"],
            "source_path": row["caminho_completo"],
            "source_drive": row["disco_origem"] or "",
            "size_bytes": int(row["tamanho_bytes"] or 0),
            "extensao": (row["extensao"] or "").lower(),
            "nome_arquivo": row["nome_arquivo"],
            "pasta_raiz": row["pasta_raiz"] or "",
            "fase_correspondente": row["fase_correspondente"] or "INDEFINIDO",
            "status_indexacao": row["status_indexacao"] or "PENDENTE",
            "hash_sha256": row["hash_sha256"] or "",
            "data_modificacao": row["data_modificacao"],
            "is_c_audit": False,
        }


def build_duplicate_map(conn: sqlite3.Connection) -> dict[str, int]:
    dup_map = {}
    rows = conn.execute("""
        SELECT hash_sha256, COUNT(*) AS cnt
        FROM files
        WHERE hash_sha256 IS NOT NULL AND hash_sha256 != ''
        GROUP BY hash_sha256
        HAVING COUNT(*) > 1
    """).fetchall()
    for row in rows:
        dup_map[row["hash_sha256"]] = row["cnt"]
    return dup_map


def sanitize_segment(value: str) -> str:
    if not value:
        return "Sem_Nome"
    cleaned = value.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace(":", "_")
    for char in '<>:"/\\|?*':
        cleaned = cleaned.replace(char, "_")
    cleaned = cleaned.rstrip(". ")
    return cleaned or "Sem_Nome"


def normalize_filename(name: str) -> str:
    base, ext = os.path.splitext(name)
    normalized = base.strip()
    normalized = re.sub(r"(\d{2})[-_ ](\d{2})[-_ ](\d{4})", r"\3-\2-\1", normalized)
    normalized = re.sub(r"(\d{4})[-_ ](\d{2})[-_ ](\d{2})", r"\1-\2-\3", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.replace(" - ", "_")
    normalized = normalized.replace("__", "_")
    normalized = normalized.strip(" ._")
    normalized = sanitize_segment(normalized)
    return f"{normalized}{ext.lower()}" if ext else normalized


def safe_rel_source(record: dict) -> str:
    path = record["source_path"]
    drive = record["source_drive"] or os.path.splitdrive(path)[0] + "\\"
    if record.get("is_c_audit"):
        home = os.path.expanduser("~")
        try:
            rel = os.path.relpath(path, home)
        except ValueError:
            rel = os.path.basename(path)
    else:
        try:
            rel = os.path.relpath(path, drive)
        except ValueError:
            rel = os.path.basename(path)
    parts = [sanitize_segment(part) for part in rel.split("\\") if part and part != "."]
    return os.path.join(*parts) if parts else sanitize_segment(os.path.basename(path))


def detect_project_marker(record: dict) -> bool:
    path = record["source_path"].lower().replace("/", "\\")
    name = record["nome_arquivo"]
    ext = record["extensao"]
    return (
        any(marker.lower() == name.lower() for marker in PROJECT_MARKERS)
        or ext in PROJECT_CODE_EXTENSIONS
        or any(hint in path for hint in PROJECT_PATH_HINTS)
    )


def is_backup_like(record: dict) -> bool:
    path = record["source_path"].lower().replace("/", "\\")
    fase = record["fase_correspondente"]
    return fase == "FASE_5" or any(hint in path for hint in BACKUP_PATH_HINTS)


def is_heavy_asset(record: dict) -> bool:
    path = record["source_path"].lower().replace("/", "\\")
    fase = record["fase_correspondente"]
    ext = record["extensao"]
    size_bytes = int(record["size_bytes"] or 0)
    return (
        fase == "FASE_4"
        or ext in HEAVY_EXTENSIONS
        or size_bytes >= HEAVY_FILE_THRESHOLD_BYTES
        or any(hint in path for hint in HEAVY_PATH_HINTS)
    )


def is_gaming_context(record: dict) -> bool:
    path = record["source_path"].lower().replace("/", "\\")
    tokens = (
        "rom",
        "emulator",
        "emulador",
        "emutool",
        "retroarch",
        "retro",
        "megadrive",
        "genesis",
        "sgdk",
        "bios",
        "game",
        "jogo",
    )
    return any(token in path for token in tokens)


def is_personal_critical(record: dict) -> bool:
    path = record["source_path"].lower().replace("/", "\\")
    fase = record["fase_correspondente"]
    ext = record["extensao"]
    if fase == "FASE_1":
        return True
    if detect_project_marker(record) or is_backup_like(record) or is_heavy_asset(record) or is_gaming_context(record):
        return False
    return (
        ext in CRITICAL_DOC_EXTENSIONS
        or ext in PERSONAL_DOC_EXTENSIONS and any(hint in path for hint in CRITICAL_PATH_HINTS)
    )


def is_program_essential(record: dict) -> bool:
    fase = record["fase_correspondente"]
    ext = record["extensao"]
    return fase == "FASE_3" or ext in PROGRAM_EXTENSIONS


def infer_temperature(record: dict, default: str) -> str:
    stamp = record.get("data_modificacao")
    if not stamp:
        return default
    try:
        modified_at = datetime.fromisoformat(stamp)
    except ValueError:
        return default
    age = datetime.now() - modified_at
    if age <= timedelta(days=30):
        return "DIARIO"
    if age <= timedelta(days=180):
        return "RECORRENTE"
    if age <= timedelta(days=730):
        return "RARO"
    return "ARQUIVO_MORTO"


def logical_path(destination_key: str, collection: str, record: dict) -> str:
    rel_src = safe_rel_source(record)
    normalized_name = normalize_filename(record["nome_arquivo"])
    rel_dir = os.path.dirname(rel_src)
    subdir = DESTINATION_SUBDIRS.get((destination_key, collection), collection)
    parts = [subdir]
    if rel_dir:
        parts.append(rel_dir)
    parts.append(normalized_name)
    return os.path.join(*parts)


def build_destination_paths(destination_key: str, collection: str, record: dict) -> tuple[str, str]:
    rel = logical_path(destination_key, collection, record)
    config = DESTINATIONS[destination_key]
    logical_root = config["logical_root"]
    logical_dest = os.path.join(logical_root, rel) if logical_root else rel
    physical_root = config["root"]
    physical_dest = os.path.join(physical_root, rel) if physical_root else ""
    return logical_dest, physical_dest


def decide_record(record: dict, duplicate_count: int, capacity_by_dest: dict[str, int]) -> dict:
    path = record["source_path"].lower().replace("/", "\\")
    size_bytes = int(record["size_bytes"] or 0)
    source_drive = record["source_drive"]
    is_c_audit = record.get("is_c_audit", False)
    is_heavy = is_heavy_asset(record)
    is_gaming = is_gaming_context(record)
    is_backup = is_backup_like(record)
    is_project = detect_project_marker(record)
    is_personal = is_personal_critical(record)
    is_program = is_program_essential(record)

    category = "AMBIGUO"
    temperature = "RARO"
    collection = COLLECTIONS["TRIAGEM_MANUAL"]
    destination_key = "REVIEW_QUEUE"
    action = ACTION_REVIEW
    reason = "Necessita triagem humana antes de qualquer consolidacao."
    confidence = "BAIXA"
    risk = "MEDIO"
    requires_review = 1

    if is_c_audit:
        risk = "ALTO"

    if is_backup:
        category = "FRIO"
        temperature = "ARQUIVO_MORTO"
        collection = COLLECTIONS["BACKUPS_ESPELHOS"]
        destination_key = "F_DRIVE"
        action = ACTION_KEEP if source_drive == "F:\\" else ACTION_COPY
        reason = "Backup ou espelho deve permanecer fora do C: e fora da nuvem."
        confidence = "ALTA"
        risk = "BAIXO" if source_drive != "C:\\" else "ALTO"
        requires_review = 0
    elif is_heavy or is_gaming:
        category = "FRIO"
        temperature = "ARQUIVO_MORTO"
        collection = COLLECTIONS["ACERVO_PESADO"]
        destination_key = "F_DRIVE"
        action = ACTION_KEEP if source_drive == "F:\\" else ACTION_COPY
        reason = "Acervo pesado, jogos, ROMs, emuladores e material correlato devem ficar em F:."
        confidence = "ALTA"
        requires_review = 0
    elif is_personal and size_bytes <= GOOGLE_DRIVE_MAX_FILE_SIZE_BYTES:
        category = "CRITICO"
        temperature = infer_temperature(record, "RECORRENTE")
        collection = COLLECTIONS["PESSOAL_CRITICO"]
        destination_key = "GOOGLE_DRIVE"
        action = ACTION_DRAIN_C if is_c_audit else ACTION_COPY
        reason = "Documento pessoal/profissional critico elegivel para nuvem de alta disponibilidade."
        confidence = "ALTA" if record["fase_correspondente"] == "FASE_1" else "MEDIA"
        risk = "ALTO" if is_c_audit else "BAIXO"
        requires_review = 0 if record["fase_correspondente"] == "FASE_1" else 1
    elif is_project:
        legacy = is_backup or "legacy" in path or "old" in path or "archive" in path
        category = "UTIL"
        temperature = infer_temperature(record, "RECORRENTE")
        collection = COLLECTIONS["PROJETOS_LEGADO"] if legacy or temperature in {"RARO", "ARQUIVO_MORTO"} else COLLECTIONS["PROJETOS_ATIVOS"]
        destination_key = "I_DRIVE"
        action = ACTION_DRAIN_C if is_c_audit else (ACTION_KEEP if source_drive == "I:\\" else ACTION_COPY)
        reason = "Projeto e documentacao tecnica devem viver em I: como area de trabalho."
        confidence = "ALTA" if record["fase_correspondente"] == "FASE_2" else "MEDIA"
        risk = "ALTO" if is_c_audit else "BAIXO"
        requires_review = 0
    elif is_program:
        category = "UTIL"
        temperature = infer_temperature(record, "RARO")
        collection = COLLECTIONS["FERRAMENTAS_ESSENCIAIS"]
        destination_key = "I_DRIVE"
        action = ACTION_DRAIN_C if is_c_audit else (ACTION_KEEP if source_drive == "I:\\" else ACTION_COPY)
        reason = "Programa ou ferramenta essencial deve ficar fora do C: e perto do workspace."
        confidence = "MEDIA"
        risk = "ALTO" if is_c_audit else "BAIXO"
        requires_review = 0
    elif is_c_audit:
        category = "AMBIGUO"
        temperature = "RECORRENTE"
        collection = COLLECTIONS["TRIAGEM_MANUAL"]
        destination_key = "REVIEW_QUEUE"
        action = ACTION_REVIEW
        reason = "Arquivo no C: sem classe segura para drenagem automatica."
        confidence = "BAIXA"
        risk = "ALTO"
        requires_review = 1

    logical_dest, physical_dest = build_destination_paths(destination_key, collection, record)
    blockers = []
    if destination_key == "GOOGLE_DRIVE" and not DESTINATIONS["GOOGLE_DRIVE"]["root"]:
        blockers.append("GOOGLE_DRIVE_ROOT_UNCONFIGURED")
        requires_review = 1
        risk = "ALTO"

    if action in {ACTION_COPY, ACTION_DRAIN_C} and destination_key in capacity_by_dest:
        remaining = capacity_by_dest[destination_key]
        if remaining < size_bytes:
            blockers.append("CAPACITY_EXCEEDED_FOR_DESTINATION")
            requires_review = 1
            risk = "ALTO"
        else:
            capacity_by_dest[destination_key] -= size_bytes

    if duplicate_count > 1:
        risk = "MEDIO" if risk == "BAIXO" else risk
        requires_review = 1 if action in {ACTION_COPY, ACTION_DRAIN_C} else requires_review

    if destination_key == "REVIEW_QUEUE":
        physical_dest = ""

    return {
        "file_id": record.get("file_id"),
        "source_path": record["source_path"],
        "source_drive": source_drive,
        "fase_correspondente": record["fase_correspondente"],
        "status_indexacao": record["status_indexacao"],
        "size_bytes": size_bytes,
        "hash_sha256": record.get("hash_sha256", ""),
        "categoria_operacional": category,
        "temperatura_acesso": temperature,
        "destino_recomendado": destination_key,
        "colecao_canonica": collection,
        "confidence_label": confidence,
        "acao_recomendada": action,
        "nome_normalizado": normalize_filename(record["nome_arquivo"]),
        "destino_logico": logical_dest,
        "destino_fisico": physical_dest,
        "justificativa_curta": reason,
        "risco_operacional": risk,
        "duplicate_hint": f"DUPLICATE_HASH_COUNT={duplicate_count}" if duplicate_count > 1 else "",
        "execution_blockers": ";".join(blockers),
        "requer_revisao_humana": requires_review,
        "policy_version": POLICY_VERSION,
    }


def select_manifest_bucket(decision: dict) -> str:
    if decision["source_drive"] == "C:\\":
        return "C_DRAIN"
    if decision["destino_recomendado"] == "GOOGLE_DRIVE":
        return "GOOGLE_DRIVE"
    if decision["destino_recomendado"] == "I_DRIVE":
        return "I_DRIVE"
    if decision["destino_recomendado"] == "F_DRIVE":
        return "F_DRIVE"
    return "REVIEW"


def file_hash(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def choose_destination(dest_path: str, source_hash: str, source_path: str) -> tuple[str, str]:
    if not os.path.exists(dest_path):
        return dest_path, "NEW_DESTINATION"
    if source_hash:
        try:
            if file_hash(dest_path) == source_hash:
                return dest_path, "ALREADY_PRESENT_SAME_HASH"
        except OSError:
            pass
    base, ext = os.path.splitext(dest_path)
    suffix = sanitize_segment(source_hash[:8] if source_hash else os.path.basename(source_path))
    candidate = f"{base}__dup_{suffix}{ext}"
    counter = 1
    while os.path.exists(candidate):
        candidate = f"{base}__dup_{suffix}_{counter}{ext}"
        counter += 1
    return candidate, "COLLISION_RENAMED"


def persist_decision_batch(conn: sqlite3.Connection, batch: list[dict]):
    """Persist organization decisions with a single long-lived connection."""
    if not batch:
        return
    conn.executemany("""
        INSERT INTO organization_decisions (
            file_id, source_path, source_drive, fase_correspondente,
            categoria_operacional, temperatura_acesso, destino_recomendado,
            colecao_canonica, acao_recomendada, nome_normalizado,
            destino_logico, destino_fisico, justificativa_curta,
            risco_operacional, confidence_label, duplicate_hint,
            execution_blockers, requer_revisao_humana, policy_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_path) DO UPDATE SET
            file_id = excluded.file_id,
            source_drive = excluded.source_drive,
            fase_correspondente = excluded.fase_correspondente,
            categoria_operacional = excluded.categoria_operacional,
            temperatura_acesso = excluded.temperatura_acesso,
            destino_recomendado = excluded.destino_recomendado,
            colecao_canonica = excluded.colecao_canonica,
            acao_recomendada = excluded.acao_recomendada,
            nome_normalizado = excluded.nome_normalizado,
            destino_logico = excluded.destino_logico,
            destino_fisico = excluded.destino_fisico,
            justificativa_curta = excluded.justificativa_curta,
            risco_operacional = excluded.risco_operacional,
            confidence_label = excluded.confidence_label,
            duplicate_hint = excluded.duplicate_hint,
            execution_blockers = excluded.execution_blockers,
            requer_revisao_humana = excluded.requer_revisao_humana,
            policy_version = excluded.policy_version,
            updated_at = datetime('now')
    """, [
        (
            item.get("file_id"),
            item["source_path"],
            item.get("source_drive"),
            item.get("fase_correspondente"),
            item.get("categoria_operacional"),
            item.get("temperatura_acesso"),
            item.get("destino_recomendado"),
            item.get("colecao_canonica"),
            item.get("acao_recomendada"),
            item.get("nome_normalizado"),
            item.get("destino_logico"),
            item.get("destino_fisico"),
            item.get("justificativa_curta"),
            item.get("risco_operacional", "MEDIO"),
            item.get("confidence_label", "MEDIA"),
            item.get("duplicate_hint"),
            item.get("execution_blockers"),
            int(item.get("requer_revisao_humana", 0)),
            item.get("policy_version"),
        )
        for item in batch
    ])
    conn.commit()


def write_manifest_index(stats: dict):
    """Write a lightweight index instead of duplicating all rows in a compatibility manifest."""
    with open(COMBINED_MANIFEST_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["manifest_key", "path", "rows"])
        writer.writeheader()
        for key, path in MANIFEST_PATHS.items():
            writer.writerow({
                "manifest_key": key,
                "path": path,
                "rows": stats["by_bucket"].get(key, 0),
            })


def execute_manifest(manifest_path: str, execution_log_path: str):
    validate_execution_manifest(manifest_path)
    os.makedirs(os.path.dirname(execution_log_path), exist_ok=True)
    processed = copied = skipped = blocked = 0
    with open(manifest_path, newline="", encoding="utf-8") as csvfile, \
            open(execution_log_path, "w", newline="", encoding="utf-8") as logfile:
        reader = csv.DictReader(csvfile)
        writer = csv.DictWriter(logfile, fieldnames=["file_id", "source_path", "destination_path", "result", "details"])
        writer.writeheader()
        for row in reader:
            processed += 1
            action = row["recommended_action"]
            blockers = row.get("execution_blockers", "")
            if action not in {ACTION_COPY, ACTION_DRAIN_C}:
                writer.writerow({"file_id": row["file_id"], "source_path": row["source_path"], "destination_path": row["destination_path"], "result": "SKIPPED_NON_COPY_ACTION", "details": action})
                skipped += 1
                continue
            if blockers:
                writer.writerow({"file_id": row["file_id"], "source_path": row["source_path"], "destination_path": row["destination_path"], "result": "BLOCKED_BY_POLICY", "details": blockers})
                blocked += 1
                continue
            src = row["source_path"]
            dest = row["destination_path"]
            source_hash = row["hash_sha256"] or ""
            if not dest:
                writer.writerow({"file_id": row["file_id"], "source_path": src, "destination_path": dest, "result": "MISSING_DESTINATION", "details": "Manifest sem destino fisico executavel."})
                blocked += 1
                continue
            if not os.path.exists(src):
                writer.writerow({"file_id": row["file_id"], "source_path": src, "destination_path": dest, "result": "SOURCE_MISSING", "details": "Arquivo de origem nao encontrado no momento da copia."})
                blocked += 1
                continue
            chosen_dest, reason = choose_destination(dest, source_hash, src)
            os.makedirs(os.path.dirname(chosen_dest), exist_ok=True)
            if reason == "ALREADY_PRESENT_SAME_HASH":
                writer.writerow({"file_id": row["file_id"], "source_path": src, "destination_path": chosen_dest, "result": reason, "details": "Hash identico ja presente no destino."})
                skipped += 1
                continue
            shutil.copy2(src, chosen_dest)
            if os.path.getsize(src) != os.path.getsize(chosen_dest):
                raise RuntimeError(f"Size mismatch after copy: {src} -> {chosen_dest}")
            writer.writerow({"file_id": row["file_id"], "source_path": src, "destination_path": chosen_dest, "result": "COPIED", "details": reason})
            copied += 1
    print(f"[ORG] Manifest processed: {processed:,}")
    print(f"[ORG] Copied: {copied:,}")
    print(f"[ORG] Skipped: {skipped:,}")
    print(f"[ORG] Blocked: {blocked:,}")
    print(f"[ORG] Execution log: {execution_log_path}")


def build_capacity_budgets() -> dict[str, int]:
    budgets = {}
    for key in ("I_DRIVE", "F_DRIVE"):
        config = DESTINATIONS[key]
        info = get_volume_info(config["root"])
        free = info["free"] if info["exists"] else 0
        reserve = config["min_free_bytes"] or 0
        budgets[key] = max(free - reserve, 0)
    return budgets


def write_summary(summary_path: str, stats: dict, volumes: dict, c_summary: dict):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Plano de Curadoria Operacional - DocIntel",
        "",
        f"> Gerado em: {ts}",
        f"> Politica: `{POLICY_VERSION}`",
        "> O manifest consolidado e mantido apenas por compatibilidade; a operacao deve usar manifests menores por destino.",
        "",
        "## Destinos",
        "",
        "| Destino | Root | Livre (GB) | Reserva Minima (GB) | Situacao |",
        "|---------|------|------------|---------------------|----------|",
    ]
    for key in ("GOOGLE_DRIVE", "I_DRIVE", "F_DRIVE"):
        config = DESTINATIONS[key]
        info = volumes[key]
        reserve = config["min_free_bytes"] or 0
        root = config["root"] or "(nao configurado)"
        free_gb = info["free"] / 1024 / 1024 / 1024 if info["exists"] else 0
        reserve_gb = reserve / 1024 / 1024 / 1024
        status = "PRONTO" if (key == "GOOGLE_DRIVE" and config["allow_execute"]) or (info["exists"] and free_gb >= reserve_gb) else "BLOQUEADO/ATENCAO"
        lines.append(f"| {key} | `{root}` | {free_gb:.1f} | {reserve_gb:.1f} | {status} |")

    lines.extend([
        "",
        "## Resumo Decisorio",
        "",
        "| Metrica | Valor |",
        "|---------|-------|",
        f"| Registros avaliados | {stats['total_rows']:,} |",
        f"| Google Drive | {stats['by_bucket']['GOOGLE_DRIVE']:,} |",
        f"| Drenagem do C: | {stats['by_bucket']['C_DRAIN']:,} |",
        f"| Curadoria para I: | {stats['by_bucket']['I_DRIVE']:,} |",
        f"| Arquivo frio em F: | {stats['by_bucket']['F_DRIVE']:,} |",
        f"| Revisao manual | {stats['by_bucket']['REVIEW']:,} |",
        f"| Bloqueados por politica | {stats['blocked']:,} |",
        f"| Duplicatas sinalizadas | {stats['duplicates']:,} |",
        "",
        "## Colecoes Canonicas",
        "",
        "| Colecao | Arquivos |",
        "|---------|----------|",
    ])
    for collection, count in sorted(stats["by_collection"].items()):
        lines.append(f"| {collection} | {count:,} |")

    lines.extend([
        "",
        "## Auditoria Formal do C:",
        "",
        "| Bucket | Arquivos | GB |",
        "|--------|----------|----|",
    ])
    for bucket, data in c_summary.items():
        lines.append(f"| {bucket} | {data['files']:,} | {data['bytes'] / 1024 / 1024 / 1024:.2f} |")

    lines.extend([
        "",
        "## Manifests Operacionais",
        "",
    ])
    for label, path in MANIFEST_PATHS.items():
        lines.append(f"- `{label}` -> `{path}`")
    lines.append(f"- `COMPAT` -> `{COMBINED_MANIFEST_PATH}`")
    lines.extend([
        "",
        "## Guardrails",
        "",
        "- Google Drive recebe apenas material critico e pequeno.",
        "- C: e tratado como disco operacional e fonte de drenagem, nunca destino final.",
        "- I: recebe trabalho vivo e ferramentas essenciais.",
        "- F: recebe acervo pesado, espelhos e material frio.",
        "- Execucao permanece copy-first, sem move ou exclusao de origem.",
    ])

    with open(summary_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def write_risks_report(path: str, stats: dict):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Top Riscos Operacionais",
        "",
        f"> Gerado em: {ts}",
        "",
        "## Totais",
        "",
        f"- Registros com bloqueio de execucao: {stats['blocked']:,}",
        f"- Registros marcados para revisao humana: {stats['review_required']:,}",
        f"- Registros com duplicata por hash: {stats['duplicates']:,}",
        "",
        "## Principais riscos",
        "",
    ]
    for risk, count in stats["by_risk"].most_common():
        lines.append(f"- {risk}: {count:,}")
    lines.extend(["", "## Principais bloqueios", ""])
    for blocker, count in stats["by_blocker"].most_common():
        lines.append(f"- {blocker}: {count:,}")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def build_plan(limit: int = 0, include_c_audit: bool = True):
    init_database()
    os.makedirs(MANIFEST_DIR, exist_ok=True)
    conn = get_read_conn()
    duplicate_map = build_duplicate_map(conn)
    capacity_by_dest = build_capacity_budgets()
    volumes = {key: get_volume_info(DESTINATIONS[key]["root"]) for key in ("GOOGLE_DRIVE", "I_DRIVE", "F_DRIVE")}

    writers = {}
    handles = {}
    temp_manifest_paths = {}
    for key, path in MANIFEST_PATHS.items():
        fd, temp_path = tempfile.mkstemp(prefix=f"{key.lower()}_", suffix=".csv", dir=MANIFEST_DIR)
        os.close(fd)
        temp_manifest_paths[key] = temp_path
        handle = open(temp_path, "w", newline="", encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        handles[key] = handle
        writers[key] = writer

    write_conn = sqlite3.connect(DB_PATH, timeout=60)
    write_conn.execute("PRAGMA journal_mode=WAL")
    write_conn.execute("PRAGMA synchronous=NORMAL")

    stats = {
        "total_rows": 0,
        "by_bucket": Counter(),
        "by_collection": Counter(),
        "by_risk": Counter(),
        "by_blocker": Counter(),
        "blocked": 0,
        "duplicates": 0,
        "review_required": 0,
    }
    batch = []

    def process_record(record: dict):
        duplicate_count = duplicate_map.get(record.get("hash_sha256", ""), 0)
        decision = decide_record(record, duplicate_count, capacity_by_dest)
        manifest_row = {
            "file_id": decision["file_id"] or "",
            "source_path": decision["source_path"],
            "source_drive": decision["source_drive"],
            "fase_correspondente": decision["fase_correspondente"],
            "status_indexacao": decision["status_indexacao"],
            "size_bytes": decision["size_bytes"],
            "hash_sha256": decision["hash_sha256"],
            "categoria_operacional": decision["categoria_operacional"],
            "temperatura_acesso": decision["temperatura_acesso"],
            "destino_recomendado": decision["destino_recomendado"],
            "colecao_canonica": decision["colecao_canonica"],
            "confidence_label": decision["confidence_label"],
            "recommended_action": decision["acao_recomendada"],
            "normalized_name": decision["nome_normalizado"],
            "destination_logical": decision["destino_logico"],
            "destination_path": decision["destino_fisico"],
            "decision_reason": decision["justificativa_curta"],
            "risk_level": decision["risco_operacional"],
            "duplicate_hint": decision["duplicate_hint"],
            "execution_blockers": decision["execution_blockers"],
            "requires_human_review": decision["requer_revisao_humana"],
        }
        bucket = select_manifest_bucket(decision)
        writers[bucket].writerow(manifest_row)
        stats["total_rows"] += 1
        stats["by_bucket"][bucket] += 1
        stats["by_collection"][decision["colecao_canonica"]] += 1
        stats["by_risk"][decision["risco_operacional"]] += 1
        if decision["execution_blockers"]:
            stats["blocked"] += 1
            for blocker in decision["execution_blockers"].split(";"):
                if blocker:
                    stats["by_blocker"][blocker] += 1
        if decision["duplicate_hint"]:
            stats["duplicates"] += 1
        if decision["requer_revisao_humana"]:
            stats["review_required"] += 1
        batch.append(decision)
        if len(batch) >= 10000:
            persist_decision_batch(write_conn, batch)
            batch.clear()

    for record in iter_db_rows(conn, limit=limit):
        process_record(record)
    if include_c_audit:
        for record in iter_c_user_files():
            process_record(record)
    if batch:
        persist_decision_batch(write_conn, batch)

    for handle in handles.values():
        handle.close()
    for key, temp_path in temp_manifest_paths.items():
        os.replace(temp_path, MANIFEST_PATHS[key])
    write_conn.close()
    conn.close()

    c_summary = summarize_c_user_targets() if include_c_audit else {}
    write_summary(SUMMARY_PATH, stats, volumes, c_summary)
    write_risks_report(TOP_RISKS_PATH, stats)
    write_manifest_index(stats)
    log_audit("ORGANIZATION", "CURATION_PLAN_GENERATED", MANIFEST_DIR, "CONCLUIDO",
              f"{stats['total_rows']:,} registros avaliados; policy={POLICY_VERSION}")
    return {
        "summary_path": SUMMARY_PATH,
        "combined_manifest": COMBINED_MANIFEST_PATH,
        "manifest_paths": MANIFEST_PATHS,
        "top_risks_path": TOP_RISKS_PATH,
        "stats": stats,
    }


def main():
    args = parse_args()
    if args.execute:
        execute_manifest(args.manifest, args.execution_log)
        return
    result = build_plan(limit=args.limit, include_c_audit=not args.skip_c_audit)
    print(f"[ORG] Summary report: {result['summary_path']}")
    print(f"[ORG] Top risks: {result['top_risks_path']}")
    print(f"[ORG] Combined manifest: {result['combined_manifest']}")
    for name, path in result["manifest_paths"].items():
        print(f"[ORG] {name}: {path}")
    print(f"[ORG] Rows analyzed: {result['stats']['total_rows']:,}")


if __name__ == "__main__":
    main()
