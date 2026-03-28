"""
DocIntel - Stage 3 Orchestrator (Extraction)
Processes files in the database to calculate hashes and extract text.
Prioritizes FASE_1 and FASE_2.
Respects exclusion rules for development directories.
"""
import time
import sqlite3
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = 'F:/DocIntel'
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from db.connection import get_connection
from db.operations import update_file_hash, update_file_text, log_audit
from extractors.hasher import calculate_sha256, should_exclude
from extractors.text_extractor import extract_content
from logs.observability import PipelineObserver

def run_extraction(batch_size=1000, limit=None):
    """Orchestrates the extraction process."""
    observer = PipelineObserver()
    observer.set_fase("Etapa 3 - Extração")
    observer.set_action("Iniciando extração em lote")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Priority: FASE_1, then FASE_2, then others. Only files NOT yet hashed.
    query = """
    SELECT id, caminho_completo, tamanho_bytes, fase_correspondente
    FROM files
    WHERE (status_indexacao = 'PENDENTE' OR status_indexacao IS NULL)
    ORDER BY 
        CASE fase_correspondente 
            WHEN 'FASE_1' THEN 1 
            WHEN 'FASE_2' THEN 2 
            ELSE 3 
        END,
        tamanho_bytes ASC
    """
    if limit:
        query += f" LIMIT {limit}"
        
    cursor.execute(query)
    files_to_process = cursor.fetchall()
    total_files = len(files_to_process)
    
    print(f"[EXTRACTION] Encontrados {total_files:,} arquivos para processar.")
    log_audit("Etapa 3", "Início da Extração", alvo=f"{total_files} arquivos")
    
    start_time = time.time()
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    for row in files_to_process:
        fid, path, size, fase = row
        
        # Check exclusion rules
        if should_exclude(path):
            cursor.execute("UPDATE files SET status_indexacao = 'EXCLUIDO' WHERE id = ?", (fid,))
            skipped_count += 1
            if processed_count % batch_size == 0:
                conn.commit()
            continue
            
        try:
            # 1. Calculate Hash
            sha256 = calculate_sha256(path)
            if sha256:
                update_file_hash(fid, sha256)
                
            # 2. Extract Text (Only for FASE_1 / FASE_2 or documents)
            # Add logic here if we want to limit text extraction to specific types
            extracted_text = extract_content(path)
            if extracted_text:
                update_file_text(fid, extracted_text)
                
            processed_count += 1
        except Exception as e:
            error_count += 1
            observer.record_error(path, str(e))
            
        # Update progress
        if processed_count % 100 == 0:
            elapsed = time.time() - start_time
            rate = processed_count / elapsed if elapsed > 0 else 0
            eta = (total_files - processed_count) / rate if rate > 0 else 0
            
            observer.update_progress(
                arquivos=processed_count,
                dirs=skipped_count, # Using dirs as a proxy for skipped in simple dashboard
                diretorio=os.path.dirname(path)
            )
            observer.flush_reports()
            print(f"[EXTRACTION] {processed_count:,}/{total_files:,} processados... ({rate:.1f} arq/s)")
            
        if processed_count % batch_size == 0:
            conn.commit()
            
    conn.commit()
    conn.close()
    
    end_time = time.time()
    summary = f"Processados: {processed_count}, Pulados: {skipped_count}, Erros: {error_count}, Tempo: {end_time - start_time:.1f}s"
    observer.set_action("Extração concluída")
    log_audit("Etapa 3", "Fim da Extração", resultado="SUCESSO", detalhes=summary)
    print(f"[EXTRACTION] Concluído. {summary}")

if __name__ == "__main__":
    run_extraction(limit=5000) # Test batch of 5000
