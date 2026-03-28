r"""Auditoria do C:\\ - areas de usuario."""
import json
from collections import Counter, defaultdict

from config.organization_policy import C_USER_TARGETS
from storage_audit import iter_c_user_files


results = defaultdict(lambda: {"count": 0, "total_size_mb": 0.0, "top_extensions": Counter(), "sample": []})

for item in iter_c_user_files():
    bucket = item["pasta_raiz"]
    ext = item["extensao"] or ""
    data = results[bucket]
    data["count"] += 1
    data["total_size_mb"] += item["size_bytes"] / 1024 / 1024
    data["top_extensions"][ext] += 1
    if len(data["sample"]) < 30:
        data["sample"].append({"path": item["source_path"], "size": item["size_bytes"], "ext": ext})

if not results:
    print("NENHUMA PASTA DE USUARIO ENCONTRADA!")
else:
    for bucket, data in results.items():
        print(f"{bucket}: {data['count']:,} arquivos, {data['total_size_mb']:,.1f} MB")
        for ext_name, cnt in data["top_extensions"].most_common(8):
            print(f"  {ext_name or '(sem ext)'}: {cnt}")

serializable = {}
for bucket, data in results.items():
    serializable[bucket] = {
        "paths": C_USER_TARGETS.get(bucket, []),
        "count": data["count"],
        "total_size_mb": round(data["total_size_mb"], 1),
        "top_extensions": dict(data["top_extensions"].most_common(15)),
        "sample": data["sample"],
    }

output_path = "F:/DocIntel/output/auditoria_c_drive.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(serializable, f, ensure_ascii=False, indent=2)
print(f"\nAuditoria salva em {output_path}")
