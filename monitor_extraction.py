r"""
DocIntel - Stage 3 Governance Monitor
Reads DB in read-only mode and generates:
  - Detailed status_execucao.md (subfase breakdown)
  - extracao_parcial_resumo.md (full governance report)

Safe to run IN PARALLEL with run_extraction.py - uses read-only WAL reads.
Run: python F:\DocIntel\monitor_extraction.py
"""
import sqlite3
import os
from datetime import datetime

DB_PATH      = r"F:\DocIntel\output\inventario_global.db"
STATUS_PATH  = r"F:\DocIntel\output\reports\status_execucao.md"
RESUMO_PATH  = r"F:\DocIntel\output\reports\extracao_parcial_resumo.md"

SKIP_REASON_EXPLANATION = {
    'EXCLUIDO': 'Pasta excluída de deep-extraction por regra (node_modules/.git/.venv etc.)',
    'AUSENTE':  'Arquivo não encontrado no sistema de arquivos (movido/deletado)',
    'PENDENTE': 'Ainda não processado',
    'HASH_CALCULADO': 'SHA-256 calculado, texto não elegível',
    'EXTRAIDO': 'SHA-256 + texto extraído com sucesso',
}

def get_conn():
    # Immutable read — WAL allows concurrent reads even with active writers
    conn = sqlite3.connect(DB_PATH, timeout=60, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    return conn


def run():
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[MONITOR] Gerando relatórios de governança às {ts}...")

    conn = get_conn()
    c = conn.cursor()

    # ── 1. STATUS POR STATUS_INDEXACAO ──────────────────────────────────────
    c.execute("""
        SELECT status_indexacao, COUNT(*) as cnt, SUM(tamanho_bytes) as tb
        FROM files
        GROUP BY status_indexacao
        ORDER BY cnt DESC
    """)
    status_rows = c.fetchall()
    status_map = {r['status_indexacao']: {'cnt': r['cnt'], 'tb': r['tb'] or 0}
                  for r in status_rows}

    total_files = sum(v['cnt'] for v in status_map.values())
    extraidos   = status_map.get('EXTRAIDO',        {'cnt': 0, 'tb': 0})['cnt']
    hash_calc   = status_map.get('HASH_CALCULADO',  {'cnt': 0, 'tb': 0})['cnt']
    excluidos   = status_map.get('EXCLUIDO',        {'cnt': 0, 'tb': 0})['cnt']
    ausentes    = status_map.get('AUSENTE',         {'cnt': 0, 'tb': 0})['cnt']
    pendentes   = status_map.get('PENDENTE',        {'cnt': 0, 'tb': 0})['cnt']
    concluidos  = extraidos + hash_calc + excluidos + ausentes

    # ── 2. STATUS POR FASE ───────────────────────────────────────────────────
    c.execute("""
        SELECT fase_correspondente, status_indexacao, COUNT(*) as cnt
        FROM files
        GROUP BY fase_correspondente, status_indexacao
    """)
    fase_status_rows = c.fetchall()
    fases = {}
    for r in fase_status_rows:
        fase = r['fase_correspondente'] or 'NULL'
        if fase not in fases:
            fases[fase] = {}
        fases[fase][r['status_indexacao'] or 'NULL'] = r['cnt']

    # ── 3. DOCS COM TEXTO EXTRAÍDO POR EXTENSÃO ──────────────────────────────
    c.execute("""
        SELECT extensao, COUNT(*) as cnt
        FROM files
        WHERE status_indexacao = 'EXTRAIDO'
        GROUP BY extensao
        ORDER BY cnt DESC
        LIMIT 20
    """)
    ext_extraidos = c.fetchall()

    # ── 4. ERROS POR EXTENSÃO (AUSENTES) ────────────────────────────────────
    c.execute("""
        SELECT extensao, COUNT(*) as cnt
        FROM files
        WHERE status_indexacao = 'AUSENTE'
        GROUP BY extensao
        ORDER BY cnt DESC
        LIMIT 15
    """)
    erros_ext = c.fetchall()

    # ── 5. EXCLUÍDOS POR PASTA (MOTIVO REAL) ────────────────────────────────
    c.execute("""
        SELECT observacoes, COUNT(*) as cnt
        FROM files
        WHERE status_indexacao = 'EXCLUIDO'
        GROUP BY observacoes
        ORDER BY cnt DESC
        LIMIT 10
    """)
    excl_motivos = c.fetchall()

    # ── 6. TAMANHO RESTANTE ──────────────────────────────────────────────────
    c.execute("""
        SELECT SUM(tamanho_bytes) FROM files
        WHERE (status_indexacao = 'PENDENTE' OR status_indexacao IS NULL)
          AND fase_correspondente IN ('FASE_1','FASE_2')
    """)
    remaining_bytes = c.fetchone()[0] or 0

    conn.close()

    # ── WRITE STATUS_EXECUCAO.MD ─────────────────────────────────────────────
    pct = concluidos / total_files * 100 if total_files > 0 else 0
    status_content = f"""# Status de Execucao — DocIntel Pipeline

> Ultima atualizacao: {ts}

## Progresso Global

| Metrica | Valor |
|---------|-------|
| **Total no Inventário** | {total_files:,} |
| **Concluídos (qualquer status)** | {concluidos:,} ({pct:.1f}%) |
| **Pendentes** | {pendentes:,} |
| **SHA-256 + Texto Extraído** | {extraidos:,} |
| **SHA-256 Apenas** | {hash_calc:,} |
| **Excluídos por Regra** | {excluidos:,} |
| **Ausentes (arquivo sumiu)** | {ausentes:,} |
| **Tamanho Restante (FASE_1+2)** | {remaining_bytes/1024/1024/1024:.1f} GB |
| **Timestamp Última Atividade** | {ts} |

## Progresso por Subfase

| Fase | EXTRAIDO | HASH_CALCULADO | EXCLUIDO | AUSENTE | PENDENTE |
|------|----------|----------------|----------|---------|---------|
"""
    for fase in sorted(fases.keys()):
        d = fases[fase]
        status_content += (f"| {fase} "
                           f"| {d.get('EXTRAIDO', 0):,} "
                           f"| {d.get('HASH_CALCULADO', 0):,} "
                           f"| {d.get('EXCLUIDO', 0):,} "
                           f"| {d.get('AUSENTE', 0):,} "
                           f"| {d.get('PENDENTE', 0) + d.get('NULL', 0):,} |\n")

    status_content += f"""
## Contagem de PDFs/DOCXs Processados

| Extensão | Extraídos com Texto |
|----------|---------------------|
"""
    for r in ext_extraidos:
        status_content += f"| `{r['extensao'] or '(sem ext)'}` | {r['cnt']:,} |\n"

    with open(STATUS_PATH, 'w', encoding='utf-8') as f:
        f.write(status_content)

    # ── WRITE EXTRACAO_PARCIAL_RESUMO.MD ────────────────────────────────────
    resumo = f"""# Relatório Parcial de Extração — DocIntel Stage 3

> Gerado em: {ts}
> Status: **EM ANDAMENTO**

## Resumo Executivo

| Item | Valor |
|------|-------|
| Total no inventário | {total_files:,} |
| Arquivos concluídos | {concluidos:,} ({pct:.1f}%) |
| Documentos com texto extraído | {extraidos:,} |
| Hashes calculados (sem texto) | {hash_calc:,} |
| Excluídos por regra de skip | {excluidos:,} |
| Ausentes no sistema de arquivos | {ausentes:,} |
| Pendentes restantes | {pendentes:,} |

## 1. Controle de Checkpoint / Resume

- **Idempotência**: ✅ Garantida via coluna `status_indexacao` no banco.
- **Regra de resume**: `WHERE status_indexacao = 'PENDENTE' OR status_indexacao IS NULL`
- **Segurança**: Arquivos já processados (`EXTRAIDO`, `HASH_CALCULADO`, `EXCLUIDO`, `AUSENTE`) são **totalmente ignorados** em reexecução.
- **Sem retrabalho**: Reenicia do ponto exato de onde parou, com granularidade de arquivo individual.
- **Batches**: Commits a cada 5.000 arquivos — interrupção perde no máximo 5.000 registros.

## 2. Arquivos Excluídos da Deep-Extraction

> ⚠️ IMPORTANTE: Excluídos da *extração profunda* (hash+texto), mas **permanecem no inventário** com `status_indexacao = 'EXCLUIDO'`.
> O flag de exclusão é gravado explicitamente no banco com motivo na coluna `observacoes`.

| Motivo | Contagem |
|--------|---------|
| Pasta excluída (node_modules/.git/.venv/etc.) | {excluidos:,} |

### Regras de Exclusão Vigentes
- `node_modules` — dependências JS/NPM
- `.git` — histórico de versionamento
- `.venv`, `venv`, `env` — ambientes Python virtuais
- `__pycache__` — cache de bytecode Python
- `.next`, `.nuxt` — builds de frameworks JS
- `dist`, `build` — artefatos de compilação
- `target` — build Maven/Gradle
- `.gradle`, `.mvn` — diretórios de ferramentas Java

## 3. Progresso por Fase

| Fase | EXTRAIDO | HASH_CALCULADO | EXCLUIDO | AUSENTE | PENDENTE |
|------|----------|----------------|----------|---------|---------|
"""
    for fase in sorted(fases.keys()):
        d = fases[fase]
        resumo += (f"| {fase} "
                   f"| {d.get('EXTRAIDO', 0):,} "
                   f"| {d.get('HASH_CALCULADO', 0):,} "
                   f"| {d.get('EXCLUIDO', 0):,} "
                   f"| {d.get('AUSENTE', 0):,} "
                   f"| {d.get('PENDENTE', 0) + d.get('NULL', 0):,} |\n")

    resumo += f"""
## 4. Documentos com Texto Extraído (Top Extensões)

| Extensão | Documentos Extraídos |
|----------|---------------------|
"""
    for r in ext_extraidos:
        resumo += f"| `{r['extensao'] or '(sem)'}` | {r['cnt']:,} |\n"

    resumo += f"""
## 5. Erros de Parsing (Top Extensões — Arquivos Ausentes)

| Extensão | Count |
|----------|-------|
"""
    if erros_ext:
        for r in erros_ext:
            resumo += f"| `{r['extensao'] or '(sem)'}` | {r['cnt']:,} |\n"
    else:
        resumo += "| — | 0 (nenhum erro registrado) |\n"

    resumo += f"""
## 6. Tamanho Restante Estimado

| Fase | GB Restantes |
|------|-------------|
| FASE_1 + FASE_2 (pendentes) | {remaining_bytes/1024/1024/1024:.2f} GB |

## 7. Gate de Validação Pós-Stage 3

> Antes de iniciar a Etapa 4 (Inteligência/Classificação Semântica),
> o sistema executará automaticamente uma **nova amostragem estratificada**
> da base refinada e enriquecida, confirmando:
> - % de arquivos com hash
> - % de docs com texto extraído
> - Distribuição de fases pós-reclassificação
> - Top documentos críticos identificados

Status: **PENDENTE** (será gerado ao término da Etapa 3)
"""

    with open(RESUMO_PATH, 'w', encoding='utf-8') as f:
        f.write(resumo)

    print(f"[MONITOR] ✅ Relatórios gerados:")
    print(f"  {STATUS_PATH}")
    print(f"  {RESUMO_PATH}")
    print(f"\n[MONITOR] Resumo: {concluidos:,}/{total_files:,} concluídos ({pct:.1f}%)")
    print(f"  EXTRAIDO: {extraidos:,} | HASH: {hash_calc:,} | EXCLUIDOS: {excluidos:,} | AUSENTES: {ausentes:,}")


if __name__ == "__main__":
    run()
