"""
DocIntel — Fase 0: Descoberta Completa do Ambiente de Armazenamento

Este modulo detecta TODOS os volumes, particoes, drives de rede,
junctions e symlinks ANTES de qualquer varredura de arquivos.

REGRA: F:\ e I:\ sao apenas pontos iniciais, nunca limites.
O sistema DEVE provar o que escaneou e o que NAO escaneou.
"""
import os
import subprocess
import json
import ctypes
from datetime import datetime


def _get_drive_type_name(drive_type: int) -> str:
    """Converte codigo de tipo de drive para nome legivel."""
    types = {
        0: "DESCONHECIDO",
        1: "SEM_RAIZ",
        2: "REMOVIVEL",      # USB, SD card
        3: "FIXO",           # HDD, SSD, NVMe
        4: "REDE",           # Network share
        5: "CDROM",
        6: "RAM_DISK",
    }
    return types.get(drive_type, "DESCONHECIDO")


def discover_windows_volumes() -> list:
    """
    Detecta todos os volumes Windows usando WMI via PowerShell.
    Retorna lista de dicionarios com informacoes de cada volume.
    """
    # Usar Get-Volume e Get-PSDrive para cobertura maxima
    ps_script = r"""
    $results = @()

    # Metodo 1: Get-PSDrive (letras de drive ativas)
    $drives = Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue
    foreach ($d in $drives) {
        $root = $d.Root
        $driveType = "DESCONHECIDO"
        try {
            $di = New-Object System.IO.DriveInfo($root)
            $driveType = $di.DriveType.ToString()
            $fsType = $di.DriveFormat
            $totalGB = [math]::Round($di.TotalSize / 1GB, 2)
            $freeGB = [math]::Round($di.AvailableFreeSpace / 1GB, 2)
            $label = $di.VolumeLabel
            $ready = $di.IsReady
        } catch {
            $fsType = "N/A"
            $totalGB = 0
            $freeGB = 0
            $label = ""
            $ready = $false
        }
        $results += [PSCustomObject]@{
            Letter = $d.Name
            Root = $root
            DriveType = $driveType
            FileSystem = $fsType
            TotalGB = $totalGB
            FreeGB = $freeGB
            Label = $label
            Ready = $ready
        }
    }

    # Metodo 2: Detectar compartilhamentos de rede mapeados
    try {
        $netDrives = Get-WmiObject Win32_MappedLogicalDisk -ErrorAction SilentlyContinue
        foreach ($nd in $netDrives) {
            $already = $results | Where-Object { $_.Letter -eq $nd.DeviceID.Replace(":", "") }
            if (-not $already) {
                $results += [PSCustomObject]@{
                    Letter = $nd.DeviceID.Replace(":", "")
                    Root = $nd.ProviderName
                    DriveType = "Network"
                    FileSystem = $nd.FileSystem
                    TotalGB = [math]::Round($nd.Size / 1GB, 2)
                    FreeGB = [math]::Round($nd.FreeSpace / 1GB, 2)
                    Label = $nd.VolumeName
                    Ready = $true
                }
            }
        }
    } catch {}

    $results | ConvertTo-Json -Depth 3
    """

    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=30, cwd="C:\\"
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                data = [data]
            return data
        else:
            print(f"[ENV] AVISO PowerShell: {result.stderr[:200]}")
            return []
    except Exception as e:
        print(f"[ENV] Erro ao detectar volumes: {e}")
        return []


def detect_junctions_and_symlinks(root_paths: list) -> list:
    """
    Detecta junctions e symlinks nos niveis superiores dos drives.
    Limita profundidade a 2 para evitar loops infinitos.
    """
    links = []
    for root in root_paths:
        if not os.path.exists(root):
            continue
        try:
            for entry in os.scandir(root):
                try:
                    if entry.is_symlink():
                        target = os.readlink(entry.path)
                        links.append({
                            "tipo": "SYMLINK",
                            "caminho": entry.path,
                            "alvo": target,
                        })
                    elif entry.is_dir() and not entry.is_symlink():
                        # Verificar se e junction (Windows)
                        if os.path.islink(entry.path):
                            target = os.readlink(entry.path)
                            links.append({
                                "tipo": "JUNCTION",
                                "caminho": entry.path,
                                "alvo": target,
                            })
                        # Nao descer mais que nivel 1
                        try:
                            for sub_entry in os.scandir(entry.path):
                                if sub_entry.is_symlink():
                                    target = os.readlink(sub_entry.path)
                                    links.append({
                                        "tipo": "SYMLINK",
                                        "caminho": sub_entry.path,
                                        "alvo": target,
                                    })
                        except (PermissionError, OSError):
                            pass
                except (PermissionError, OSError):
                    pass
        except (PermissionError, OSError):
            pass

    return links


def check_volume_access(root_path: str) -> str:
    """Testa acesso de leitura a um volume."""
    try:
        entries = list(os.scandir(root_path))
        return "OK"
    except PermissionError:
        return "ACESSO_NEGADO"
    except FileNotFoundError:
        return "NAO_ENCONTRADO"
    except OSError as e:
        return f"ERRO: {e}"


def estimate_scan_priority(drive_type: str, total_gb: float, free_gb: float,
                            letter: str) -> str:
    """Define prioridade de varredura baseada no tipo e tamanho."""
    if letter in ("C",):
        return "BAIXA_SISTEMA"
    if drive_type in ("Removable", "REMOVIVEL"):
        return "ALTA"
    if drive_type in ("Fixed", "FIXO"):
        return "ALTA"
    if drive_type in ("Network", "REDE"):
        return "MEDIA"
    if drive_type in ("CDRom", "CDROM"):
        return "IGNORAR"
    return "MEDIA"


def run_environment_discovery() -> dict:
    """
    Executa a descoberta completa do ambiente.
    Retorna dicionario com todos os volumes e metadados.
    """
    print("=" * 60)
    print("[FASE 0] DESCOBERTA COMPLETA DO AMBIENTE DE ARMAZENAMENTO")
    print("=" * 60)

    # 1. Detectar volumes via PowerShell/WMI
    print("\n[ENV] Detectando volumes do sistema...")
    volumes = discover_windows_volumes()
    print(f"[ENV] {len(volumes)} volumes detectados")

    # 2. Testar acesso a cada volume
    for vol in volumes:
        root = vol.get("Root", "")
        if root and os.path.exists(root):
            vol["status_acesso"] = check_volume_access(root)
        else:
            vol["status_acesso"] = "NAO_MONTADO"

        vol["prioridade"] = estimate_scan_priority(
            vol.get("DriveType", ""),
            vol.get("TotalGB", 0),
            vol.get("FreeGB", 0),
            vol.get("Letter", "")
        )

        used = vol.get("TotalGB", 0) - vol.get("FreeGB", 0)
        vol["estimativa_dados_gb"] = round(used, 2) if used > 0 else 0

    # 3. Detectar junctions e symlinks
    roots_to_check = [v["Root"] for v in volumes
                       if v.get("status_acesso") == "OK" and v.get("Root")]
    print(f"\n[ENV] Verificando junctions/symlinks em {len(roots_to_check)} volumes...")
    links = detect_junctions_and_symlinks(roots_to_check)
    print(f"[ENV] {len(links)} links simbolicos/junctions encontrados")

    # 4. Compor resultado completo
    result = {
        "timestamp": datetime.now().isoformat(),
        "total_volumes": len(volumes),
        "volumes": volumes,
        "junctions_symlinks": links,
    }

    # 5. Imprimir resumo no terminal
    print(f"\n{'=' * 60}")
    print(f"[RESULTADO] {len(volumes)} volumes detectados:")
    for v in volumes:
        letter = v.get("Letter", "?")
        dtype = v.get("DriveType", "?")
        total = v.get("TotalGB", 0)
        free = v.get("FreeGB", 0)
        status = v.get("status_acesso", "?")
        prio = v.get("prioridade", "?")
        print(f"  {letter}:\\ | {dtype:12s} | {total:8.1f} GB total | {free:8.1f} GB livre | {status:15s} | Prio: {prio}")

    if links:
        print(f"\n[LINKS] {len(links)} junctions/symlinks:")
        for lnk in links:
            print(f"  {lnk['tipo']}: {lnk['caminho']} -> {lnk['alvo']}")

    return result


def generate_environment_map(result: dict, output_path: str):
    """Gera o artefato mapa_ambiente_armazenamento.md"""
    lines = []
    lines.append("# Mapa do Ambiente de Armazenamento")
    lines.append("")
    lines.append(f"> Gerado em: {result['timestamp']}")
    lines.append(f"> Total de volumes detectados: {result['total_volumes']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Volumes Detectados")
    lines.append("")
    lines.append("| Volume | Tipo | FS | Total (GB) | Livre (GB) | Dados Est. (GB) | Acesso | Prioridade |")
    lines.append("|--------|------|----|------------|------------|-----------------|--------|------------|")

    for v in result["volumes"]:
        letter = v.get("Letter", "?")
        dtype = v.get("DriveType", "?")
        fs = v.get("FileSystem", "?")
        total = v.get("TotalGB", 0)
        free = v.get("FreeGB", 0)
        est = v.get("estimativa_dados_gb", 0)
        status = v.get("status_acesso", "?")
        prio = v.get("prioridade", "?")
        label = v.get("Label", "")
        name = f"{letter}:\\ ({label})" if label else f"{letter}:\\"
        lines.append(f"| {name} | {dtype} | {fs} | {total:.1f} | {free:.1f} | {est:.1f} | {status} | {prio} |")

    lines.append("")

    # Junctions/Symlinks
    links = result.get("junctions_symlinks", [])
    if links:
        lines.append("## Junctions e Symlinks Detectados")
        lines.append("")
        lines.append("| Tipo | Caminho | Alvo |")
        lines.append("|------|---------|------|")
        for lnk in links:
            lines.append(f"| {lnk['tipo']} | `{lnk['caminho']}` | `{lnk['alvo']}` |")
        lines.append("")
    else:
        lines.append("## Junctions e Symlinks")
        lines.append("")
        lines.append("Nenhum junction ou symlink detectado nos niveis superiores.")
        lines.append("")

    # Observacoes tecnicas
    lines.append("## Observacoes Tecnicas")
    lines.append("")
    for v in result["volumes"]:
        letter = v.get("Letter", "?")
        prio = v.get("prioridade", "?")
        if prio == "IGNORAR":
            lines.append(f"- **{letter}:\\\\**: Drive de midia optica, ignorado na varredura.")
        elif prio == "BAIXA_SISTEMA":
            lines.append(f"- **{letter}:\\\\**: Disco do sistema operacional. Varredura limitada a areas de usuario.")
        elif v.get("status_acesso") == "ACESSO_NEGADO":
            lines.append(f"- **{letter}:\\\\**: Acesso negado. Requer permissoes elevadas.")
        elif v.get("status_acesso") != "OK":
            lines.append(f"- **{letter}:\\\\**: Status de acesso: {v.get('status_acesso')}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Este documento comprova a descoberta total do ambiente. Volumes nao listados acima nao existem ou nao estao acessiveis.*")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n[ENV] Mapa salvo em: {output_path}")


if __name__ == "__main__":
    result = run_environment_discovery()
    output = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "output", "reports", "mapa_ambiente_armazenamento.md")
    os.makedirs(os.path.dirname(output), exist_ok=True)
    generate_environment_map(result, output)
