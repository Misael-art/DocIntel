"""
DocIntel - Fast Stratified Sampling Script (Fixed)
"""
import sqlite3
import json
import random
import os

DB_PATH = 'F:/DocIntel/output/inventario_global.db'
REPORT_PATH = 'F:/DocIntel/output/reports/validacao_qualidade.md'

def get_sampling():
    if not os.path.exists(DB_PATH):
        print(f"Erro: Banco não encontrado em {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    fases = {
        'FASE_1': 'Documentacao Critica',
        'FASE_2': 'Projetos',
        'FASE_3': 'Programas/Ferramentas',
        'FASE_4': 'Acervo Pesado',
        'INDEFINIDO': 'Ambiguo/Indefinido'
    }

    lines = []
    lines.append('# Validacao de Qualidade — Amostragem Estratificada')
    lines.append('')
    lines.append('> Pipeline CONGELADO. Nenhuma extracao sera iniciada sem aprovacao.')
    lines.append('')

    for fase, desc in fases.items():
        total = conn.execute('SELECT COUNT(*) FROM files WHERE fase_correspondente = ?', (fase,)).fetchone()[0]
        
        rows = []
        if total > 0:
            samples_count = min(60, total)
            # Use random offsets for speed
            for _ in range(samples_count):
                offset = random.randint(0, total - 1)
                row = conn.execute('''
                    SELECT caminho_completo, nome_arquivo, extensao, tamanho_bytes,
                           pasta_raiz, profundidade, fase_correspondente, data_modificacao
                    FROM files
                    WHERE fase_correspondente = ?
                    LIMIT 1 OFFSET ?
                ''', (fase, offset)).fetchone()
                if row:
                    rows.append(row)

        dist = conn.execute('''
            SELECT folder, count, total_bytes FROM (
                SELECT pasta_raiz as folder, COUNT(*) as count, SUM(tamanho_bytes) as total_bytes
                FROM files WHERE fase_correspondente = ?
                GROUP BY pasta_raiz
            ) ORDER BY count DESC
        ''', (fase,)).fetchall()

        lines.append(f'## {desc} ({fase}) — {total:,} arquivos')
        lines.append('')
        lines.append('### Distribuicao por pasta raiz')
        lines.append('')
        lines.append('| Pasta Raiz | Arquivos | Tamanho (MB) | % do total |')
        lines.append('|-----------|----------|-------------|------------|')
        for d in dist:
            pct = (d['count'] / total * 100) if total > 0 else 0
            mb = (d['total_bytes'] or 0) / 1024 / 1024
            lines.append(f"| `{d['folder'] or '(raiz)'}` | {d['count']:,} | {mb:,.1f} | {pct:.1f}% |")
        lines.append('')

        lines.append('### Amostra aleatoria (60 arquivos)')
        lines.append('')
        lines.append('| # | Caminho | Extensao | Tamanho | Data Modificacao | Classificacao Atual | Confianca |')
        lines.append('|---|---------|----------|---------|-----------------|--------------------|-----------|')
        for i, r in enumerate(rows, 1):
            path = r['caminho_completo']
            if len(path) > 80:
                path = '...' + path[-77:]
            ext = r['extensao'] or '(nenhuma)'
            sz = r['tamanho_bytes'] or 0
            if sz > 1024*1024:
                sz_str = f'{sz/1024/1024:.1f} MB'
            elif sz > 1024:
                sz_str = f'{sz/1024:.0f} KB'
            else:
                sz_str = f'{sz} B'
            dm = (r['data_modificacao'] or '')[:10]
            
            lines.append(f"| {i} | `{path}` | {ext} | {sz_str} | {dm} | {fase} | BAIXA |")

        lines.append('')
        lines.append('---')
        lines.append('')

    # Analysis sections
    lines.append('## ⚠️ Problemas Potenciais Detectados')
    lines.append('')
    
    # Steam check
    steam_count = conn.execute("SELECT COUNT(*) FROM files WHERE pasta_raiz='Steam' AND (fase_correspondente='FASE_1' OR fase_correspondente IS NULL)").fetchone()[0]
    if steam_count > 0:
        lines.append(f'### Problema: Pasta Steam na FASE_1')
        lines.append(f'- **{steam_count:,} arquivos** da pasta `Steam` estão mapeados incorretamente.')
        lines.append('- Steam deve ser FASE_4 (Acervo Pesado) / FASE_3 (Apps).')
        lines.append('')

    # Desktop check (from external audit)
    lines.append('### Problema: Desktop do C:\\ ignorado com 1.1M arquivos')
    lines.append('- Auditoria externa detectou 1,112,748 arquivos no Desktop.')
    lines.append('- Primariamente arquivos de desenvolvimento (.js, .ts).')
    lines.append('- **Sugerido:** Incluir `C:\\Users\\misae\\OneDrive\\Desktop` no inventário como FASE_2 (Projetos).')
    lines.append('')

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'Relatorio salvo em {REPORT_PATH}')
    conn.close()

if __name__ == "__main__":
    get_sampling()
