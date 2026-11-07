#!/usr/bin/env python3
"""Validate themes/*.yaml the way Home Assistant and the Marketplace do.

* plain YAML only: no tags such as !include / !secret (Marketplace rule)
* every theme passes the schema of homeassistant/components/frontend/helpers.py:
  {str: str, optional "modes": {optional "light"/"dark": {str: str}}, at least one mode}
* sanity checks for this theme: hex colours, balanced url("…") / parentheses,
  correctly encoded SVG data URIs.
* with --check-build: the file is up to date with tools/build.py (run locally;
  libm rounding may differ between platforms).

Requires PyYAML.  Usage:  python3 tools/validate.py [--check-build]
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []


class NoTagLoader(yaml.SafeLoader):
    """SafeLoader that refuses every explicit tag, like the Marketplace."""


def _refuse(loader, tag_suffix, node):
    raise yaml.constructor.ConstructorError(None, None, f"tag {node.tag!r} is not allowed", node.start_mark)


NoTagLoader.add_multi_constructor("!", _refuse)


def check_vars(where: str, mapping: object) -> None:
    if not isinstance(mapping, dict):
        errors.append(f"{where}: must be a mapping")
        return
    for key, value in mapping.items():
        if not isinstance(key, str):
            errors.append(f"{where}: key {key!r} is not a string")
        if not isinstance(value, str):
            errors.append(f"{where}.{key}: value {value!r} is not a string (quote it)")
            continue
        if key.startswith("--"):
            errors.append(f"{where}.{key}: drop the leading '--'")
        if value.count("(") != value.count(")"):
            errors.append(f"{where}.{key}: unbalanced parentheses")
        if value.startswith("#") and not re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?([0-9a-fA-F]{2})?", value):
            errors.append(f"{where}.{key}: invalid hex colour {value!r}")
        for uri in re.findall(r'url\("data:image/svg\+xml,([^"]*)"\)', value):
            if re.search(r"[<>#]", uri):
                errors.append(f"{where}.{key}: SVG data URI contains unencoded <, > or #")
        if key == "ha-panel-background" and "data:image/svg+xml," not in value:
            errors.append(f"{where}.{key}: expected the underwater SVG background")


def validate_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.load(text, Loader=NoTagLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as err:
        errors.append(f"{path.name}: {err}")
        return
    if not isinstance(data, dict) or not data:
        errors.append(f"{path.name}: top level must be a non-empty mapping of themes")
        return
    for name, theme in data.items():
        where = f"{path.name}:{name}"
        if not isinstance(theme, dict):
            errors.append(f"{where}: theme must be a mapping")
            continue
        base = {k: v for k, v in theme.items() if k != "modes"}
        check_vars(where, base)
        if "modes" in theme:
            modes = theme["modes"]
            if not isinstance(modes, dict) or not modes:
                errors.append(f"{where}.modes: needs at least one of light/dark")
                continue
            extra = set(modes) - {"light", "dark"}
            if extra:
                errors.append(f"{where}.modes: unknown keys {sorted(extra)}")
            for mode in ("light", "dark"):
                if mode in modes:
                    check_vars(f"{where}.modes.{mode}", modes[mode])
        print(f"  ok  {name}: {len(base)} vars" + (f", modes {sorted(theme['modes'])}" if "modes" in theme else ""))


def check_fresh() -> None:
    theme = ROOT / "themes" / "reef.yaml"
    before = theme.read_bytes()
    subprocess.run([sys.executable, str(ROOT / "tools" / "build.py")], check=True, capture_output=True)
    if theme.read_bytes() != before:
        errors.append("themes/reef.yaml is out of date: run `python3 tools/build.py` and commit the result")


def main() -> int:
    files = sorted((ROOT / "themes").glob("*.yaml"))
    if len(files) != 1:
        errors.append(f"themes/ must contain exactly one YAML file, found {len(files)}")
    for path in files:
        print(path.relative_to(ROOT))
        validate_file(path)
    if "--check-build" in sys.argv:
        check_fresh()
    for e in errors:
        print(f"ERROR {e}")
    print("valid" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
