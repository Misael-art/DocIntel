"""
DocIntel - Politica de governanca operacional de armazenamento.
"""
from __future__ import annotations

from config.settings import (
    C_USER_ROOT,
    F_DRIVE_CURATED_ROOT,
    GOOGLE_DRIVE_MAX_FILE_SIZE_BYTES,
    GOOGLE_DRIVE_ROOT,
    HEAVY_FILE_THRESHOLD_BYTES,
    I_DRIVE_CURATED_ROOT,
    MIN_FREE_BYTES_BY_DRIVE,
)


POLICY_VERSION = "2026-03-curation-v1"

COLLECTIONS = {
    "PESSOAL_CRITICO": "Pessoal_Critico",
    "PROJETOS_ATIVOS": "Projetos_Ativos",
    "PROJETOS_LEGADO": "Projetos_Legado",
    "FERRAMENTAS_ESSENCIAIS": "Ferramentas_Essenciais",
    "ACERVO_PESADO": "Acervo_Pesado",
    "BACKUPS_ESPELHOS": "Backups_Espelhos",
    "TRIAGEM_MANUAL": "Triagem_Manual",
}

DESTINATIONS = {
    "GOOGLE_DRIVE": {
        "label": "Google Drive",
        "root": GOOGLE_DRIVE_ROOT,
        "logical_root": "GOOGLE_DRIVE://",
        "min_free_bytes": None,
        "allow_execute": GOOGLE_DRIVE_ROOT is not None,
    },
    "I_DRIVE": {
        "label": "I:\\",
        "root": I_DRIVE_CURATED_ROOT,
        "logical_root": I_DRIVE_CURATED_ROOT,
        "min_free_bytes": MIN_FREE_BYTES_BY_DRIVE["I:\\"],
        "allow_execute": True,
    },
    "F_DRIVE": {
        "label": "F:\\",
        "root": F_DRIVE_CURATED_ROOT,
        "logical_root": F_DRIVE_CURATED_ROOT,
        "min_free_bytes": MIN_FREE_BYTES_BY_DRIVE["F:\\"],
        "allow_execute": True,
    },
    "REVIEW_QUEUE": {
        "label": "Review Queue",
        "root": None,
        "logical_root": "REVIEW_QUEUE://",
        "min_free_bytes": None,
        "allow_execute": False,
    },
    "KEEP_ON_SOURCE": {
        "label": "Manter na origem",
        "root": None,
        "logical_root": "KEEP_ON_SOURCE://",
        "min_free_bytes": None,
        "allow_execute": False,
    },
}

DESTINATION_SUBDIRS = {
    ("GOOGLE_DRIVE", COLLECTIONS["PESSOAL_CRITICO"]): "Pessoal_Critico",
    ("I_DRIVE", COLLECTIONS["PROJETOS_ATIVOS"]): "Projetos_Ativos",
    ("I_DRIVE", COLLECTIONS["PROJETOS_LEGADO"]): "Projetos_Legado",
    ("I_DRIVE", COLLECTIONS["FERRAMENTAS_ESSENCIAIS"]): "Ferramentas_Essenciais",
    ("F_DRIVE", COLLECTIONS["ACERVO_PESADO"]): "Acervo_Pesado",
    ("F_DRIVE", COLLECTIONS["BACKUPS_ESPELHOS"]): "Backups_Espelhos",
}

CRITICAL_PATH_HINTS = (
    "\\importante\\",
    "\\finan",
    "\\finance",
    "\\imigra",
    "\\document",
    "\\contrat",
    "\\certid",
    "\\steam\\",
)

PROJECT_PATH_HINTS = (
    "\\projects\\",
    "\\project\\",
    "\\workspace\\",
    "\\src\\",
    "\\repo\\",
)

BACKUP_PATH_HINTS = (
    "\\backup",
    "\\backups\\",
    "\\espelho\\",
    "\\mirror\\",
    "\\old\\",
    "\\legacy\\",
    "\\archive\\",
    "\\staging\\",
)

HEAVY_PATH_HINTS = (
    "\\roms\\",
    "\\rom\\",
    "\\isos\\",
    "\\games\\",
    "\\jogos\\",
    "\\emulators\\",
    "\\emuladores\\",
    "\\retroarch\\",
    "\\launchbox\\",
    "\\retrobat\\",
    "\\bizhawk\\",
    "\\dolphin\\",
    "\\duckstation\\",
    "\\pcsx2\\",
    "\\rpcs3\\",
    "\\xenia\\",
    "\\yuzu\\",
    "\\ryujinx\\",
    "\\citra\\",
    "\\steamlibrary\\",
)

PROJECT_CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".cs", ".cpp", ".c", ".h", ".hpp",
    ".java", ".kt", ".go", ".rs", ".php", ".rb", ".swift", ".sql", ".sh",
    ".ps1", ".md", ".toml", ".yaml", ".yml", ".json", ".xml", ".ini",
}

HEAVY_EXTENSIONS = {
    ".iso", ".bin", ".cue", ".rvz", ".wbfs", ".nes", ".sfc", ".smc", ".gba",
    ".gb", ".gbc", ".3ds", ".nsp", ".xci", ".zip", ".7z", ".rar", ".pkg",
    ".ps2", ".ps3", ".psp", ".chd", ".mkv", ".mp4", ".avi", ".mov", ".flac",
    ".wav", ".mp3", ".psd", ".blend", ".pst", ".vhd", ".vhdx",
}

PERSONAL_DOC_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".csv",
    ".jpg", ".jpeg", ".png", ".tiff", ".webp",
}

PROGRAM_EXTENSIONS = {
    ".exe", ".msi", ".bat", ".cmd", ".lnk", ".dll", ".appx", ".zip", ".7z",
}

C_USER_TARGETS = {
    "Desktop": [
        f"{C_USER_ROOT}\\Desktop",
        f"{C_USER_ROOT}\\OneDrive\\Desktop",
    ],
    "Downloads": [
        f"{C_USER_ROOT}\\Downloads",
        f"{C_USER_ROOT}\\OneDrive\\Downloads",
    ],
    "Documents": [
        f"{C_USER_ROOT}\\Documents",
        f"{C_USER_ROOT}\\OneDrive\\Documents",
        f"{C_USER_ROOT}\\OneDrive\\Documentos",
    ],
}

ACTION_COPY = "COPY_TO_DESTINATION"
ACTION_DRAIN_C = "DRAIN_C_BY_COPY"
ACTION_KEEP = "KEEP_IN_PLACE"
ACTION_REVIEW = "REVIEW_BEFORE_ACTION"
