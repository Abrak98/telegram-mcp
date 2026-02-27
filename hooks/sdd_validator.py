#!/usr/bin/env python3
"""
SDD Validator — pre-commit hook для Specification-Driven Development.

Функции:
1. Auto-update статуса (approved → committed)
2. Валидация хэшей narrative.md ↔ technical.md
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

SPECS_DIR = Path("specs")


def get_staged_files() -> list[str]:
    """Получить список файлов в staging."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip().split("\n") if result.stdout.strip() else []


def compute_md5(filepath: Path) -> str:
    """Вычислить MD5 хэш файла."""
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def extract_narrative_hash(technical_content: str) -> str | None:
    """Извлечь Narrative-Hash из technical.md."""
    match = re.search(r"Narrative-Hash:\s*([a-f0-9]{32})", technical_content)
    return match.group(1) if match else None


def extract_status(content: str) -> str | None:
    """Извлечь Status из файла."""
    match = re.search(r"Status:\s*(draft|approved|committed|blocked)", content)
    return match.group(1) if match else None


def update_status_to_committed(filepath: Path) -> bool:
    """Обновить Status: approved → committed."""
    content = filepath.read_text()
    if "Status: approved" in content:
        new_content = content.replace("Status: approved", "Status: committed")
        filepath.write_text(new_content)
        subprocess.run(["git", "add", str(filepath)])
        return True
    return False


def find_technical_specs() -> list[Path]:
    """Найти все technical.md файлы."""
    if not SPECS_DIR.exists():
        return []
    return list(SPECS_DIR.rglob("*.technical.md"))


def validate_spec(technical_path: Path) -> tuple[bool, str]:
    """Валидировать одну спеку."""
    technical_content = technical_path.read_text()
    status = extract_status(technical_content)

    if status not in ("approved", "committed"):
        return True, ""

    narrative_path = technical_path.with_suffix("").with_suffix(".narrative.md")
    if not narrative_path.exists():
        return False, f"Missing narrative: {narrative_path}"

    stored_hash = extract_narrative_hash(technical_content)
    if not stored_hash:
        return False, f"No Narrative-Hash in {technical_path}"

    current_hash = compute_md5(narrative_path)
    if stored_hash != current_hash:
        return False, (
            f"Hash mismatch for {technical_path.stem}:\n"
            f"  Stored:  {stored_hash}\n"
            f"  Current: {current_hash}"
        )

    return True, ""


def main() -> int:
    staged_files = get_staged_files()
    errors: list[str] = []

    # Auto-update approved → committed
    for technical_path in find_technical_specs():
        # Проверяем есть ли связанный код/тесты в staging
        component = technical_path.stem.replace(".technical", "")
        has_code = any(
            "src/" in f and component.lower() in f.lower() for f in staged_files
        )
        has_tests = any(
            "tests/spec/" in f and component.lower() in f.lower() for f in staged_files
        )

        if has_code or has_tests:
            if update_status_to_committed(technical_path):
                print(f"✓ Auto-updated {technical_path.name}: approved → committed")

    # Validate all specs
    for technical_path in find_technical_specs():
        valid, error = validate_spec(technical_path)
        if not valid:
            errors.append(error)

    if errors:
        print("\n❌ SDD Validation Failed:\n")
        for error in errors:
            print(f"  {error}\n")
        return 1

    print("✓ SDD validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
