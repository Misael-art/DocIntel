"""
DocIntel - Post-Etapa 3 Gate Script
=====================================
Generates all required reports after Stage 3 (Extraction) completes.
DOES NOT initiate Etapa 4 under any circumstance.

Outputs:
  - relatorio_final_extracao.md   (full extraction summary)
  - amostragem_pos_extracao.md    (stratified validation sampling)
  - status_distribuicao_final.md  (status_indexacao distribution)
  - anomalias_erros.md            (errors and anomalies)
  - GATE_ETAPA4_BLOQUEADO.md      (hard gate — must be removed to proceed)

Usage:
  python F:\\DocIntel\\post_extraction_gate.py
"""
import os
import random
from datetime import datetime

from docintel.db.connection import get_connection

DB_PATH   = r"F:\DocIntel\output\inventario_global.db"
OUT_DIR   = r"F:\DocIntel\output\reports"
GATE_BLOCK = r"F:\DocIntel\GATE_ETAPA4_BLOQUEADO.md"
GATE_OK    = r"F:\DocIntel\GATE_ETAPA4_APROVADO.md"

TEXT_EXTS = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.md',
             '.rtf', '.odt', '.csv', '.json', '.xml', '.html', '.htm'}

SKIP_DIRS = {'node_modules', '.git', '.venv', '__pycache__', '.next',
             '.nuxt', 'dist', 'build', 'target', '.gradle', '.mvn', 'venv', 'env', '.tox'}


def conn():
    return get_connection(DB_PATH, query_only=True, timeout=60)


def q(c, sql, params=()):
    return c.execute(sql, params).fetchall()


def q1(c, sql, params=()):
    r = c.execute(sql, params).fetchone()
    return r[0] if r else None


# ─── 1. STATUS DISTRIBUTION ───────────────────────────────────────────────────
def get_status_dist(c):
    return q(c, """
        SELECT status_indexacao, COUNT(*) as cnt, SUM(tamanho_bytes) as tb
        FROM files GROUP BY status_indexacao ORDER BY cnt DESC
    """)


# ─── 2. PHASE × STATUS CROSS-TAB ─────────────────────────────────────────────
def get_fase_status(c):
    rows = q(c, """
        SELECT fase_correspondente, status_indexacao, COUNT(*) as cnt
        FROM files GROUP BY fase_correspondente, status_indexacao
    """)
    fases = {}
    for r in rows:
        f = r['fase_correspondente'] or 'NULL'
        fases.setdefault(f, {})
        fases[f][r['status_indexacao'] or 'NULL'] = r['cnt']
    return fases


# ─── 3. EXTRACTION BY EXTENSION ───────────────────────────────────────────────
def get_ext_breakdown(c):
    return q(c, """
        SELECT extensao,
               SUM(CASE WHEN status_indexacao = 'EXTRAIDO' THEN 1 ELSE 0 END) as extraido,
               SUM(CASE WHEN status_indexacao = 'HASH_CALCULADO' THEN 1 ELSE 0 END) as hash_only,
               SUM(CASE WHEN status_indexacao = 'EXCLUIDO' THEN 1 ELSE 0 END) as excluido,
               COUNT(*) as total
        FROM files
        WHERE fase_correspondente IN ('FASE_1')
        GROUP BY extensao ORDER BY total DESC LIMIT 30
    """)


# ─── 4. ANOMALIES & ERRORS ────────────────────────────────────────────────────
def get_anomalies(c):
    ausentes  = q(c, """
        SELECT extensao, COUNT(*) as cnt FROM files
        WHERE status_indexacao = 'AUSENTE'
        GROUP BY extensao ORDER BY cnt DESC LIMIT 20
    """)
    excluidos = q(c, """
        SELECT observacoes, COUNT(*) as cnt FROM files
        WHERE status_indexacao = 'EXCLUIDO'
        GROUP BY observacoes ORDER BY cnt DESC LIMIT 20
    """)
    # Files > 1GB that were hashed (slow outliers)
    enormous = q(c, """
        SELECT caminho_completo, tamanho_bytes / 1024 / 1024 as mb
        FROM files
        WHERE tamanho_bytes > 1073741824
          AND status_indexacao IN ('EXTRAIDO','HASH_CALCULADO')
        ORDER BY tamanho_bytes DESC LIMIT 10
    """)
    # FASE_1 files that are plain binaries (no text, not excluded)
    binary_in_fase1 = q1(c, """
        SELECT COUNT(*) FROM files
        WHERE fase_correspondente = 'FASE_1'
          AND status_indexacao = 'HASH_CALCULADO'
          AND extensao NOT IN ('.pdf','.docx','.doc','.xlsx','.xls',
                               '.txt','.md','.rtf','.odt','.csv',
                               '.json','.xml','.html','.htm')
    """)
    return ausentes, excluidos, enormous, binary_in_fase1


# ─── 5. STRATIFIED SAMPLING ───────────────────────────────────────────────────
def get_sample(c, fase, status, limit=15):
    total = q1(c, f"""
        SELECT COUNT(*) FROM files
        WHERE fase_correspondente = ? AND status_indexacao = ?
    """, (fase, status))
    if not total or total == 0:
        return []
    # Offset-based sampling (fast, no ORDER BY RANDOM full scan)
    step = max(1, total // limit)
    results = []
    cur = c.cursor()
    for i in range(0, min(total, limit * step), step):
        cur.execute("""
            SELECT nome_arquivo, extensao, tamanho_bytes,
                   status_indexacao, fase_correspondente,
                   caminho_completo,
                   SUBSTR(texto_extraido, 1, 120) as preview
            FROM files
            WHERE fase_correspondente = ? AND status_indexacao = ?
            LIMIT 1 OFFSET ?
        """, (fase, status, i))
        row = cur.fetchone()
        if row:
            results.append(row)
    return results


# ─── 6. SEMANTICS EXPLANATION ─────────────────────────────────────────────────
SEMANTICS_DOC = """
## Semântica da Tabela por Fase — EXTRAIDO vs HASH_CALCULADO

### O que significa `status_indexacao`?

| Status | Significado | Próxima Etapa |
|--------|-------------|---------------|
| `PENDENTE` | Arquivo inventariado, sem qualquer processamento profundo | SHA-256 + extração de texto |
| `HASH_CALCULADO` | SHA-256 calculado. Arquivo binário/não-textual, ou extensão fora do escopo de extração | Classificação por heurística |
| `EXTRAIDO` | SHA-256 + texto extraído com sucesso. Pronto para análise semântica | Classificação semântica (Etapa 4) |
| `EXCLUIDO` | Inventariado mas fora do escopo de deep-extraction (node_modules/.git/etc.). flag `SKIP_RULE:<dir>` em `observacoes` | Nenhuma — apenas inventário |
| `AUSENTE` | Caminho registrado mas arquivo não encontrado no momento da extração | Investigar manualmente |

### Por que existem HASH_CALCULADO dentro da FASE_1?

FASE_1 = documentação crítica (contratos, certidões, laudos, etc.)  
Mas nem todo arquivo nessa pasta é um documento legível. Exemplos:

- Arquivos `.db_` (LibreOffice help database) → sem texto, só hash
- Arquivos `.png`, `.jpg` (imagens de documentos) → hash calculado, texto futuro via OCR
- Arquivos `.xml` de configuração → texto extraído mas classificado como suporte, não como doc crítico
- Arquivos `.ui`, `.rdb`, `.so`, `.dll` (binários de apps) → hash apenas, texto impossível

### Regra aplicada na Etapa 3:
```
SE fase_correspondente = 'FASE_1' E extensao IN (pdf, docx, xlsx, txt, md, csv, html, xml...):
    → extrair texto → status = EXTRAIDO
SENÃO:
    → apenas SHA-256 → status = HASH_CALCULADO  
SE caminho contém pasta excluída:
    → nenhum processamento → status = EXCLUIDO
```

### Implicações para Etapa 4:
- Arquivos `EXTRAIDO` em FASE_1: **prontos para análise semântica completa**
- Arquivos `HASH_CALCULADO` em FASE_1: precisam de **revisão manual ou OCR** para documentos críticos
- Arquivos `HASH_CALCULADO` em FASE_2+: processados por heurística de projeto (linguagem, stack, etc.)
"""


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def run():
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[GATE] Iniciando relatório pós-Etapa 3 — {ts}")

    c = conn()

    # ── Totals ────────────────────────────────────────────────────────────────
    total        = q1(c, "SELECT COUNT(*) FROM files") or 0
    total_bytes  = q1(c, "SELECT SUM(tamanho_bytes) FROM files") or 0
    extraidos    = q1(c, "SELECT COUNT(*) FROM files WHERE status_indexacao='EXTRAIDO'") or 0
    hash_calc    = q1(c, "SELECT COUNT(*) FROM files WHERE status_indexacao='HASH_CALCULADO'") or 0
    excluidos    = q1(c, "SELECT COUNT(*) FROM files WHERE status_indexacao='EXCLUIDO'") or 0
    ausentes     = q1(c, "SELECT COUNT(*) FROM files WHERE status_indexacao='AUSENTE'") or 0
    pendentes    = q1(c, "SELECT COUNT(*) FROM files WHERE status_indexacao='PENDENTE' OR status_indexacao IS NULL") or 0
    concluidos   = extraidos + hash_calc + excluidos + ausentes
    pct          = concluidos / total * 100 if total > 0 else 0

    # FASE_1 specifics
    f1_extraido  = q1(c, "SELECT COUNT(*) FROM files WHERE fase_correspondente='FASE_1' AND status_indexacao='EXTRAIDO'") or 0
    f1_hash      = q1(c, "SELECT COUNT(*) FROM files WHERE fase_correspondente='FASE_1' AND status_indexacao='HASH_CALCULADO'") or 0
    f1_excl      = q1(c, "SELECT COUNT(*) FROM files WHERE fase_correspondente='FASE_1' AND status_indexacao='EXCLUIDO'") or 0
    f1_total     = q1(c, "SELECT COUNT(*) FROM files WHERE fase_correspondente='FASE_1'") or 0

    # Check if Etapa 3 target is complete
    remaining_f1_f2 = q1(c, """
        SELECT COUNT(*) FROM files
        WHERE fase_correspondente IN ('FASE_1','FASE_2')
          AND (status_indexacao='PENDENTE' OR status_indexacao IS NULL)
    """) or 0
    etapa3_complete = remaining_f1_f2 == 0

    status_dist  = get_status_dist(c)
    fases        = get_fase_status(c)
    ext_break    = get_ext_breakdown(c)
    ausentes_ext, excl_motivos, enormous, binary_in_fase1 = get_anomalies(c)

    # ── RELATÓRIO FINAL DE EXTRAÇÃO ────────────────────────────────────────────
    completion_flag = "✅ COMPLETA" if etapa3_complete else f"⏳ EM ANDAMENTO — {remaining_f1_f2:,} pendentes (FASE_1+2)"
    relatorio = f"""# Relatório Final de Extração — DocIntel Etapa 3

> Gerado em: {ts}
> Status da Etapa 3: **{completion_flag}**

## 1. Resumo Executivo

| Métrica | Valor |
|---------|-------|
| **Total no inventário** | {total:,} arquivos |
| **Tamanho total** | {total_bytes/1024/1024/1024:.1f} GB |
| **Concluídos (qualquer status)** | {concluidos:,} ({pct:.1f}%) |
| **SHA-256 + Texto Extraído** | {extraidos:,} |
| **SHA-256 apenas (binários)** | {hash_calc:,} |
| **Excluídos por regra** | {excluidos:,} |
| **Ausentes no filesystem** | {ausentes:,} |
| **Pendentes** | {pendentes:,} |

## 2. Detalhamento FASE_1 (Documentação Crítica)

| Status em FASE_1 | Contagem | % do total FASE_1 |
|------------------|----------|-------------------|
| EXTRAIDO (texto + hash) | {f1_extraido:,} | {f1_extraido/f1_total*100:.1f}% |
| HASH_CALCULADO (só hash) | {f1_hash:,} | {f1_hash/f1_total*100:.1f}% |
| EXCLUIDO (regra de skip) | {f1_excl:,} | {f1_excl/f1_total*100:.1f}% |
| **TOTAL FASE_1** | **{f1_total:,}** | 100% |

{SEMANTICS_DOC}

## 3. Distribuição por Status × Fase

| Fase | EXTRAIDO | HASH_CALCULADO | EXCLUIDO | AUSENTE | PENDENTE |
|------|----------|----------------|----------|---------|---------|
"""
    for fase in ['FASE_1','FASE_2','FASE_3','FASE_4','FASE_5','INDEFINIDO','NULL']:
        d = fases.get(fase, {})
        relatorio += (f"| {fase} "
                      f"| {d.get('EXTRAIDO',0):,} "
                      f"| {d.get('HASH_CALCULADO',0):,} "
                      f"| {d.get('EXCLUIDO',0):,} "
                      f"| {d.get('AUSENTE',0):,} "
                      f"| {d.get('PENDENTE',0)+d.get('NULL',0):,} |\n")

    relatorio += "\n## 4. Extração por Extensão (FASE_1)\n\n"
    relatorio += "| Ext | EXTRAIDO | HASH_CALCULADO | EXCLUIDO | Total |\n"
    relatorio += "|-----|----------|----------------|----------|-------|\n"
    for r in ext_break:
        ext = r['extensao'] or '(sem)'
        relatorio += f"| `{ext}` | {r['extraido']:,} | {r['hash_only']:,} | {r['excluido']:,} | {r['total']:,} |\n"

    relatorio += f"""
## 5. Anomalias e Erros

### 5.1 Arquivos Ausentes no Filesystem
> Arquivos que estavam no inventário mas não foram encontrados no momento da extração.

"""
    if ausentes_ext:
        relatorio += "| Extensão | Count |\n|----------|-------|\n"
        for r in ausentes_ext:
            relatorio += f"| `{r['extensao'] or '(sem)'}` | {r['cnt']:,} |\n"
    else:
        relatorio += "> ✅ **Zero arquivos ausentes.** Todos os arquivos processados existem no filesystem.\n"

    relatorio += "\n### 5.2 Arquivos Excluídos por Regra (com motivo)\n\n"
    if excl_motivos:
        relatorio += "| Motivo (observacoes) | Count |\n|----------------------|-------|\n"
        for r in excl_motivos:
            relatorio += f"| `{r['observacoes'] or '—'}` | {r['cnt']:,} |\n"
    else:
        relatorio += "> Nenhum arquivo excluído até o momento.\n"

    relatorio += "\n### 5.3 Arquivos Muito Grandes (> 1 GB) Processados\n\n"
    if enormous:
        relatorio += "| Arquivo | Tamanho (MB) |\n|---------|-------------|\n"
        for r in enormous:
            name = os.path.basename(r['caminho_completo'])
            relatorio += f"| `{name}` | {r['mb']:,.0f} MB |\n"
    else:
        relatorio += "> Nenhum arquivo > 1 GB foi processado com deep-extraction.\n"

    relatorio += f"""
### 5.4 Binários em FASE_1 (documentação crítica sem texto)
> Arquivos em FASE_1 com status HASH_CALCULADO e extensão não-textual.
> Estes podem requerer OCR ou revisão manual na Etapa 4.

**Total:** {binary_in_fase1 or 0:,} arquivos

---

## 6. Gate de Aprovação — Etapa 4

> 🔴 **STATUS: PENDENTE DE APROVAÇÃO HUMANA**

A Etapa 4 (Inteligência / Classificação Semântica) **NÃO SERÁ INICIADA** até que o usuário:
1. Revise este relatório
2. Revise a amostragem estratificada (`amostragem_pos_extracao.md`)
3. Emita aprovação explícita

Arquivo de bloqueio: `GATE_ETAPA4_BLOQUEADO.md` (criado automaticamente)
"""

    out = os.path.join(OUT_DIR, 'relatorio_final_extracao.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(relatorio)
    print(f"[GATE] OK {out}")

    # ── AMOSTRAGEM ESTRATIFICADA PÓS-EXTRAÇÃO ─────────────────────────────────
    amostra = f"""# Amostragem Estratificada Pós-Extração — DocIntel

> Gerado em: {ts}
> Objetivo: Validar qualidade da extração antes de iniciar Etapa 4

---

"""
    groups = [
        ('FASE_1', 'EXTRAIDO',       'FASE_1 — Documentos Críticos com Texto Extraído'),
        ('FASE_1', 'HASH_CALCULADO', 'FASE_1 — Documentos Críticos apenas com Hash (binários)'),
        ('FASE_2', 'HASH_CALCULADO', 'FASE_2 — Projetos (SHA-256 calculado)'),
        ('FASE_3', 'PENDENTE',       'FASE_3 — Programas / Ferramentas (pendentes)'),
        ('INDEFINIDO', 'PENDENTE',   'INDEFINIDO — Desktop C:\\ (pendentes de classificação)'),
    ]

    for fase, status, titulo in groups:
        samples = get_sample(c, fase, status, limit=10)
        amostra += f"## {titulo}\n\n"
        if not samples:
            amostra += f"> Nenhum arquivo nesta combinação ({fase}/{status}).\n\n"
            continue
        amostra += "| Arquivo | Ext | Tamanho | Preview do Texto |\n"
        amostra += "|---------|-----|---------|------------------|\n"
        for s in samples:
            nome = (s['nome_arquivo'] or '')[:40]
            ext  = s['extensao'] or ''
            kb   = (s['tamanho_bytes'] or 0) / 1024
            prev = (s['preview'] or '—').replace('\n', ' ')[:80].replace('|', '/')
            amostra += f"| `{nome}` | `{ext}` | {kb:.1f} KB | {prev} |\n"
        amostra += "\n"

    aout = os.path.join(OUT_DIR, 'amostragem_pos_extracao.md')
    with open(aout, 'w', encoding='utf-8') as f:
        f.write(amostra)
    print(f"[GATE] OK {aout}")

    # ── STATUS DISTRIBUTION FINAL ─────────────────────────────────────────────
    sdist = f"""# Distribuição Final por Status de Indexação — DocIntel

> Gerado em: {ts}

| Status | Arquivos | GB | % do Total |
|--------|---------|-----|------------|
"""
    for r in status_dist:
        st = r['status_indexacao'] or 'NULL'
        tb = (r['tb'] or 0) / 1024 / 1024 / 1024
        pct_row = r['cnt'] / total * 100 if total > 0 else 0
        sdist += f"| `{st}` | {r['cnt']:,} | {tb:.1f} | {pct_row:.2f}% |\n"

    sdist += f"\n**Total:** {total:,} arquivos / {total_bytes/1024/1024/1024:.1f} GB\n"

    sout = os.path.join(OUT_DIR, 'status_distribuicao_final.md')
    with open(sout, 'w', encoding='utf-8') as f:
        f.write(sdist)
    print(f"[GATE] OK {sout}")

    c.close()

    # ── GATE FILE (hard block) ─────────────────────────────────────────────────
    gate_content = f"""# 🔴 GATE ETAPA 4 — BLOQUEADO

> Criado em: {ts}

## Status da Extração
- Total: **{total:,}** arquivos
- Concluídos: **{concluidos:,}** ({pct:.1f}%)
- Pendentes (FASE_1+2): **{remaining_f1_f2:,}**

## Ação Necessária

O usuário deve revisar os seguintes relatórios:
1. `output/reports/relatorio_final_extracao.md`
2. `output/reports/amostragem_pos_extracao.md`
3. `output/reports/status_distribuicao_final.md`

Para desbloquear a Etapa 4, o usuário deve emitir aprovação explícita no chat.
O sistema NÃO lerá este arquivo sozinho — a aprovação deve ser feita pelo usuário.

## Regra de Proteção
```
NENHUM script de classificação semântica (Etapa 4) pode iniciar
sem a presença de GATE_ETAPA4_APROVADO.md neste diretório.
```
"""
    with open(GATE_BLOCK, 'w', encoding='utf-8') as f:
        f.write(gate_content)
    print(f"[GATE] Gate criado: {GATE_BLOCK}")

    print(f"\n[GATE] === RESUMO FINAL ===")
    print(f"  Total: {total:,} | Extraídos: {extraidos:,} | Hash: {hash_calc:,} | Excluídos: {excluidos:,} | Ausentes: {ausentes:,}")
    print(f"  Etapa 3 completa: {'SIM' if etapa3_complete else f'NAO - {remaining_f1_f2:,} pendentes'}")
    print(f"\n  Etapa 4 BLOQUEADA ate aprovacao explicita do usuario.")


if __name__ == "__main__":
    run()
