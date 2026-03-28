"""
DocIntel - Reclassificador de Sub-árvores Steam
Aplica granularidade na classificação da pasta Steam:
- Steam\Informacoes -> FASE_1
- Steam\Steamapps\DevProjetos -> FASE_2
- Steam\Steamapps\common -> FASE_4
- Demais -> FASE_4 (ou FASE_3 se for app)
"""
import sqlite3
import os

DB_PATH = 'F:/DocIntel/output/inventario_global.db'

def reclassify_steam():
    if not os.path.exists(DB_PATH):
        print(f"Erro: Banco não encontrado em {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    
    print("[REFINE] Iniciando reclassificação granular da pasta Steam...")

    # 1. Resetar Steam para FASE_4 por padrão (Acervo Pesado)
    # Mas apenas para os que estavam na FASE_1 ou sem fase
    res = conn.execute("""
        UPDATE files 
        SET fase_correspondente = 'FASE_4'
        WHERE pasta_raiz = 'Steam' 
        AND (fase_correspondente = 'FASE_1' OR fase_correspondente IS NULL)
    """)
    print(f"  -> {res.rowcount:,} arquivos resetados para FASE_4")

    # 2. Reclassificar Steam\Informacoes para FASE_1 (Documentação)
    res = conn.execute("""
        UPDATE files 
        SET fase_correspondente = 'FASE_1'
        WHERE caminho_completo LIKE '%Steam\\Informacoes%'
    """)
    print(f"  -> {res.rowcount:,} arquivos movidos para FASE_1 (Informações)")

    # 3. Reclassificar Steam\Steamapps\DevProjetos para FASE_2 (Projetos)
    res = conn.execute("""
        UPDATE files 
        SET fase_correspondente = 'FASE_2'
        WHERE caminho_completo LIKE '%Steam\\Steamapps\\DevProjetos%'
    """)
    print(f"  -> {res.rowcount:,} arquivos movidos para FASE_2 (DevProjetos)")

    # 4. Reclassificar Steam\Steamapps\DevKits para FASE_3 (Ferramentas)
    res = conn.execute("""
        UPDATE files 
        SET fase_correspondente = 'FASE_3'
        WHERE caminho_completo LIKE '%Steam\\Steamapps\\DevKits%'
    """)
    print(f"  -> {res.rowcount:,} arquivos movidos para FASE_3 (DevKits)")

    conn.commit()
    conn.close()
    print("[REFINE] Reclassificação concluída.")

if __name__ == "__main__":
    reclassify_steam()
