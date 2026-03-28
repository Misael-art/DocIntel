"""
DocIntel — Operações CRUD Idempotentes
"""
from __future__ import annotations

import json

from db.connection import get_connection


def upsert_file(file_data: dict) -> int:
    """Insere ou atualiza um registro de arquivo. Retorna o ID."""
    conn = get_connection()
    cursor = conn.cursor()

    # Tentar inserir; se já existir, atualizar campos atualizáveis
    cursor.execute("""
        INSERT INTO files (
            caminho_completo, nome_arquivo, extensao, tamanho_bytes,
            data_criacao, data_modificacao, data_ultimo_acesso,
            disco_origem, pasta_raiz, profundidade, fase_correspondente
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(caminho_completo) DO UPDATE SET
            tamanho_bytes = excluded.tamanho_bytes,
            data_modificacao = excluded.data_modificacao,
            data_ultimo_acesso = excluded.data_ultimo_acesso,
            updated_at = datetime('now')
    """, (
        file_data["caminho_completo"],
        file_data["nome_arquivo"],
        file_data.get("extensao"),
        file_data.get("tamanho_bytes"),
        file_data.get("data_criacao"),
        file_data.get("data_modificacao"),
        file_data.get("data_ultimo_acesso"),
        file_data["disco_origem"],
        file_data.get("pasta_raiz"),
        file_data.get("profundidade"),
        file_data.get("fase_correspondente"),
    ))

    file_id = cursor.execute(
        "SELECT id FROM files WHERE caminho_completo = ?",
        (file_data["caminho_completo"],)
    ).fetchone()[0]

    conn.commit()
    conn.close()
    return file_id


def update_file_hash(file_id: int, sha256: str, md5: str = None):
    """Atualiza os hashes de um arquivo."""
    conn = get_connection()
    conn.execute("""
        UPDATE files SET hash_sha256 = ?, hash_md5 = ?,
        status_indexacao = 'HASH_CALCULADO', updated_at = datetime('now')
        WHERE id = ?
    """, (sha256, md5, file_id))
    conn.commit()
    conn.close()


def update_file_text(file_id: int, texto: str, mime_type: str = None):
    """Atualiza o texto extraído de um arquivo."""
    conn = get_connection()
    conn.execute("""
        UPDATE files SET texto_extraido = ?, mime_type = ?,
        status_indexacao = 'EXTRAIDO', updated_at = datetime('now')
        WHERE id = ?
    """, (texto, mime_type, file_id))
    conn.commit()
    conn.close()


def update_file_classification(file_id: int, criticidade: str, confianca: float,
                                revisao: bool, fase: str = None, obs: str = None):
    """Atualiza a classificação de um arquivo."""
    conn = get_connection()
    conn.execute("""
        UPDATE files SET
            nivel_criticidade = ?,
            nivel_confianca_classificacao = ?,
            requer_revisao_humana = ?,
            status_triagem = 'TRIADO',
            fase_correspondente = COALESCE(?, fase_correspondente),
            observacoes = COALESCE(?, observacoes),
            updated_at = datetime('now')
        WHERE id = ?
    """, (criticidade, confianca, int(revisao), fase, obs, file_id))
    conn.commit()
    conn.close()


def insert_classification(file_id: int, classe: str, secundarias: str,
                           justificativa: str, metodo: str, score: float):
    """Insere uma classificação com justificativa."""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO classifications
        (file_id, classe_principal, classes_secundarias, justificativa_textual,
         metodo_classificacao, score)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (file_id, classe, secundarias, justificativa, metodo, score))
    conn.commit()
    conn.close()


def insert_document(file_id: int, doc_data: dict):
    """Insere análise semântica de documento."""
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO documents
        (file_id, tipo_documento, subtipo_documento, assunto_principal,
         resumo_semantico, entidades_detectadas, pessoa_principal_relacionada,
         pessoas_secundarias, organizacoes_detectadas, datas_relevantes,
         numeros_relevantes, contexto_juridico, contexto_financeiro,
         contexto_profissional, contexto_familiar, contexto_migratorio,
         contexto_tecnico, contexto_medico, sensibilidade, tags_semanticas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        file_id,
        doc_data.get("tipo_documento"),
        doc_data.get("subtipo_documento"),
        doc_data.get("assunto_principal"),
        doc_data.get("resumo_semantico"),
        doc_data.get("entidades_detectadas"),
        doc_data.get("pessoa_principal_relacionada"),
        doc_data.get("pessoas_secundarias"),
        doc_data.get("organizacoes_detectadas"),
        doc_data.get("datas_relevantes"),
        doc_data.get("numeros_relevantes"),
        doc_data.get("contexto_juridico"),
        doc_data.get("contexto_financeiro"),
        doc_data.get("contexto_profissional"),
        doc_data.get("contexto_familiar"),
        doc_data.get("contexto_migratorio"),
        doc_data.get("contexto_tecnico"),
        doc_data.get("contexto_medico"),
        doc_data.get("sensibilidade", "NORMAL"),
        doc_data.get("tags_semanticas"),
    ))
    conn.commit()
    conn.close()


def insert_project(project_data: dict) -> int:
    """Insere ou atualiza um registro de projeto."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO projects (
            pasta_raiz, nome_projeto, categoria_projeto, status_projeto,
            ativo_ou_legado, ultimo_sinal_atividade, stack_detectada,
            linguagem_predominante, tem_git, tem_node_modules, tem_build,
            backup_ou_workspace_real, tamanho_total_bytes, total_arquivos, observacoes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pasta_raiz) DO UPDATE SET
            status_projeto = excluded.status_projeto,
            ativo_ou_legado = excluded.ativo_ou_legado,
            ultimo_sinal_atividade = excluded.ultimo_sinal_atividade,
            updated_at = datetime('now')
    """, (
        project_data["pasta_raiz"],
        project_data.get("nome_projeto"),
        project_data.get("categoria_projeto"),
        project_data.get("status_projeto", "INDEFINIDO"),
        project_data.get("ativo_ou_legado", "INDEFINIDO"),
        project_data.get("ultimo_sinal_atividade"),
        project_data.get("stack_detectada"),
        project_data.get("linguagem_predominante"),
        project_data.get("tem_git", 0),
        project_data.get("tem_node_modules", 0),
        project_data.get("tem_build", 0),
        project_data.get("backup_ou_workspace_real", "INDEFINIDO"),
        project_data.get("tamanho_total_bytes"),
        project_data.get("total_arquivos"),
        project_data.get("observacoes"),
    ))
    pid = cursor.lastrowid or cursor.execute(
        "SELECT id FROM projects WHERE pasta_raiz = ?",
        (project_data["pasta_raiz"],)
    ).fetchone()[0]
    conn.commit()
    conn.close()
    return pid


def insert_duplicate(fid_a: int, fid_b: int, tipo: str,
                      similaridade: float, criterio: str, recomendacao: str):
    """Registra uma duplicata detectada."""
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO duplicates
        (file_id_origem, file_id_relacionado, tipo_duplicidade,
         similaridade, criterio, recomendacao)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (fid_a, fid_b, tipo, similaridade, criterio, recomendacao))
    conn.commit()
    conn.close()


def log_audit(
    etapa: str,
    acao: str,
    alvo: str = None,
    resultado: str = None,
    detalhes: str = None,
    *,
    severity: str = "INFO",
    correlation_id: str | None = None,
    details_json: dict | None = None,
):
    """Registra uma entrada no log de auditoria."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO audit_log (
            etapa, acao, alvo, resultado, detalhes, severity, correlation_id, details_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        etapa,
        acao,
        alvo,
        resultado,
        detalhes,
        severity,
        correlation_id,
        json.dumps(details_json, ensure_ascii=True) if details_json is not None else None,
    ))
    conn.commit()
    conn.close()


def upsert_organization_decisions(decisions: list[dict]):
    """Insere ou atualiza decisoes operacionais em lote."""
    if not decisions:
        return
    conn = get_connection()
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
        for item in decisions
    ])
    conn.commit()
    conn.close()
