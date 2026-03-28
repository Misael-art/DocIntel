"""
DocIntel - Hasher Module (Stage 3)
Calculates SHA-256 for files, excluding large development directories.
"""
import hashlib
import os

# List of directory patterns to exclude from deep extraction (hashing/text)
EXCLUDE_PATTERNS = [
    'node_modules',
    '.git',
    '.venv',
    '__pycache__',
    '.next',
    '.nuxt',
    'dist',
    'build'
]

def should_exclude(file_path):
    """Checks if the file path contains any of the exclusion patterns."""
    normalized_path = file_path.lower()
    for pattern in EXCLUDE_PATTERNS:
        if f'\\{pattern}\\' in normalized_path or normalized_path.endswith(f'\\{pattern}'):
            return True
        if f'/{pattern}/' in normalized_path or normalized_path.endswith(f'/{pattern}'):
            return True
    return False

def calculate_sha256(file_path, block_size=65536):
    """Calculates the SHA-256 hash of a file."""
    if not os.path.exists(file_path):
        return None
        
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                sha256.update(block)
        return sha256.hexdigest()
    except (PermissionError, OSError):
        return None

if __name__ == "__main__":
    # Test
    test_path = r"F:\DocIntel\main.py"
    if not should_exclude(test_path):
        print(f"Hash of {test_path}: {calculate_sha256(test_path)}")
    else:
        print(f"File {test_path} is excluded from hashing.")
