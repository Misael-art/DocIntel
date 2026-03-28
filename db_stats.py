"""
DocIntel - db_stats.py
Prints a summary of the inventory database.
"""
import sqlite3

DB = 'F:/DocIntel/output/inventario_global.db'
conn = sqlite3.connect(DB, timeout=10)
conn.execute("PRAGMA journal_mode=WAL")

c = conn.cursor()

c.execute('SELECT COUNT(*), SUM(tamanho_bytes) FROM files')
total, total_bytes = c.fetchone()
total_bytes = total_bytes or 0
print(f'\n=== INVENTARIO GLOBAL ===')
print(f'Total de arquivos: {total:,}')
print(f'Tamanho total: {total_bytes/1024/1024/1024:.1f} GB')

print('\n--- Por Fase ---')
c.execute('SELECT fase_correspondente, COUNT(*) as cnt FROM files GROUP BY fase_correspondente ORDER BY cnt DESC')
for fase, cnt in c.fetchall():
    print(f'  {fase or "NULL"}: {cnt:,}')

print('\n--- Por Disco ---')
c.execute('SELECT disco_origem, COUNT(*) as cnt FROM files GROUP BY disco_origem ORDER BY cnt DESC')
for disco, cnt in c.fetchall():
    print(f'  {disco or "NULL"}: {cnt:,}')

print('\n--- Por Status de Indexacao ---')
c.execute('SELECT status_indexacao, COUNT(*) as cnt FROM files GROUP BY status_indexacao ORDER BY cnt DESC')
for st, cnt in c.fetchall():
    print(f'  {st or "NULL"}: {cnt:,}')

conn.close()
print('\n=== FIM ===')
