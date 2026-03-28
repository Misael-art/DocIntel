"""
DocIntel - Steam Reclassification Script
Granular update based on sub-tree patterns.
"""
import sqlite3
import os

DB_PATH = 'F:/DocIntel/output/inventario_global.db'

def reclassify():
    if not os.path.exists(DB_PATH):
        print(f"Erro: Banco não encontrado.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("[REFINE] Coletando IDs de arquivos Steam...")
    cursor.execute("SELECT id, caminho_completo FROM files WHERE pasta_raiz = 'Steam'")
    rows = cursor.fetchall()
    print(f"[REFINE] {len(rows):,} arquivos encontrados.")

    updates = []
    for file_id, path in rows:
        new_fase = 'FASE_4' # Default for Steam
        # Use simpler string checks for speed
        if 'Steam\\Informacoes' in path:
            new_fase = 'FASE_1'
        elif 'Steam\\Steamapps\\DevProjetos' in path:
            new_fase = 'FASE_2'
        elif 'Steam\\Steamapps\\DevKits' in path:
            new_fase = 'FASE_3'
        
        updates.append((new_fase, file_id))

    print("[REFINE] Aplicando atualizações em batches...")
    # Use batches to avoid long locks
    batch_size = 50000
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]
        cursor.executemany("UPDATE files SET fase_correspondente = ? WHERE id = ?", batch)
        conn.commit()
        print(f"  -> {min(i+batch_size, len(updates)):,} arquivos processados...")

    conn.close()
    print("[REFINE] Reclassificação concluída.")

if __name__ == "__main__":
    reclassify()
