"""
DocIntel — Configurações Globais do Sistema
"""
import os


def _detect_google_drive_root() -> str | None:
    """Best-effort discovery for a local Google Drive sync root."""
    home = os.path.expanduser("~")
    env_override = os.environ.get("DOCINTEL_GOOGLE_DRIVE_ROOT")
    candidates = [
        env_override,
        os.path.join(home, "Google Drive"),
        os.path.join(home, "Google Drive", "Meu Drive"),
        os.path.join(home, "Google Drive", "My Drive"),
        os.path.join(home, "Meu Drive"),
        os.path.join(home, "My Drive"),
        os.path.join(home, "GoogleDrive"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _detect_temp_staging_root() -> str | None:
    """Resolve a safe temporary staging root when an auxiliary drive is available."""
    env_override = os.environ.get("DOCINTEL_TEMP_STAGING_ROOT")
    candidates = [env_override]
    if os.path.exists(r"L:\\"):
        candidates.extend(
            [
                r"L:\DocIntel_Temp_Staging",
                r"L:\DocIntel_Staging",
            ]
        )
    for path in candidates:
        if not path:
            continue
        drive, _ = os.path.splitdrive(path)
        if drive and os.path.exists(f"{drive}\\"):
            return path
        if os.path.exists(path):
            return path
    return None

# === Discos de Origem (somente-leitura) ===
SOURCE_DRIVES = ["F:\\", "I:\\"]

# === Diretório de Saída do DocIntel ===
DOCINTEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(DOCINTEL_ROOT, "output")
DB_PATH = os.path.join(OUTPUT_DIR, "inventario_global.db")
REPORTS_DIR = os.path.join(OUTPUT_DIR, "reports")
LOGS_DIR = os.path.join(DOCINTEL_ROOT, "logs")

# === Destino de Organizacao Consolidada ===
DRIVE_PESSOAL_ROOT = r"C:\Users\misae\OneDrive\Desktop\Drive_Pessoal"
DRIVE_PESSOAL_DIRS = {
    "FASE_1": "02_Pessoal_e_Profissional",
    "FASE_2": "01_Projetos_Ativos",
    "FASE_3": "03_Programas_Essenciais",
    "FASE_5": "05_Backups_Fragmentos_Antigos",
}
KEEP_HEAVY_MEDIA_ON_SOURCE = True
ORGANIZATION_REPORTS_DIR = os.path.join(REPORTS_DIR, "organizacao_drive_pessoal")
CURATION_REPORTS_DIR = os.path.join(REPORTS_DIR, "organizacao_drive_pessoal")

# === Destinos Multi-Camada (novo modelo) ===
GOOGLE_DRIVE_ROOT = _detect_google_drive_root()
I_DRIVE_CURATED_ROOT = os.environ.get("DOCINTEL_I_CURATED_ROOT", r"I:\DocIntel_Organizado")
F_DRIVE_CURATED_ROOT = os.environ.get("DOCINTEL_F_CURATED_ROOT", r"F:\DocIntel_Organizado")
TEMP_STAGING_ROOT = _detect_temp_staging_root()
C_USER_ROOT = os.path.join(os.path.expanduser("~"))

# === Politica operacional ===
GOOGLE_DRIVE_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
HEAVY_FILE_THRESHOLD_BYTES = 750 * 1024 * 1024
MIN_FREE_BYTES_BY_DRIVE = {
    "C:\\": 25 * 1024 * 1024 * 1024,
    "I:\\": 120 * 1024 * 1024 * 1024,
    "F:\\": 80 * 1024 * 1024 * 1024,
    "L:\\": 100 * 1024 * 1024 * 1024,
}

# === Limites de Extração ===
MAX_TEXT_LENGTH = 10_000          # Máximo de caracteres de texto extraído por arquivo
HASH_BUFFER_SIZE = 65_536         # 64KB buffer para hashing de arquivos grandes
MAX_FILE_SIZE_FOR_HASH = 5 * 1024 * 1024 * 1024  # 5GB - pular hash para arquivos > 5GB

# === Extensões Alvo por Fase ===
CRITICAL_DOC_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".doc", ".xls", ".txt", ".rtf", ".odt"}
PROJECT_MARKERS = {"package.json", ".sln", "Makefile", "CMakeLists.txt", "build.gradle", "pom.xml", "Cargo.toml", "go.mod"}
PROJECT_DIRS = {".git", "ProjectSettings", "node_modules", ".vscode", ".idea"}
INSTALLER_EXTENSIONS = {".exe", ".msi", ".cab", ".zip", ".7z", ".rar"}
MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".mp3", ".flac", ".wav", ".nsz"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg"}

# === Diretórios a Excluir da Varredura (nível de sistema) ===
SYSTEM_EXCLUDE_DIRS = {
    "$RECYCLE.BIN", "System Volume Information", ".Trash-1000",
    "msdownld.tmp", "tmp"
}

# === Scoring ===
CONFIDENCE_THRESHOLD_AUTO = 0.8   # Acima: classificação automática sem revisão
CONFIDENCE_THRESHOLD_REVIEW = 0.6 # Entre 0.6 e 0.8: automática mas marcada para revisão
# Abaixo de 0.6: AMBÍGUO, revisão obrigatória

WEIGHT_CONTENT = 0.50
WEIGHT_STRUCTURE = 0.20
WEIGHT_ENTITIES = 0.20
WEIGHT_MIME = 0.10

# === Criar diretórios de saída ===
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(ORGANIZATION_REPORTS_DIR, exist_ok=True)
