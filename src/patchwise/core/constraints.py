from pathlib import Path
import yaml


def load_constraints(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def find_pin(constraints: dict, package: str) -> dict | None:
    for pin in constraints.get("pins", []):
        if pin.get("package") == package:
            return pin
    return None


def find_upgrade_group(constraints: dict, package: str) -> dict | None:
    for group in constraints.get("upgradeTogether", []):
        if package in group.get("packages", []):
            return group
    return None
