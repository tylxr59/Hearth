"""The public Nest installer archive: what the USB wizard needs, and nothing else.

Contents are computed, not listed by hand:

1. Python modules reachable by imports from ``provision.py`` and ``installer/``.
2. Every file of each ``firmware/<component>`` or ``tools/<component>``
   directory that one of those modules belongs to. Builders read their C
   sources, configs, patches and licences by path.
3. C fault fixtures under ``tests/`` named by an included module, plus anything
   an included C file pulls in with ``#include "..."``.
4. A short README, the licences and the user guides.

This module is standard library only and must also work from an extracted
archive: the wizard snapshots its own source into every private session, and
that snapshot must equal the published archive minus its top-level folder.
"""

import argparse
import ast
import os
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("backend", "firmware", "installer", "provisioning", "tools")
COMPONENT_PARENTS = ("firmware", "tools")
SUFFIXES = {
    ".py",
    ".c",
    ".h",
    ".S",
    ".map",
    ".json",
    ".sh",
    ".md",
    ".patch",
    ".txt",
    ".config",
    ".lds",
}
NAMES = {"Dockerfile", "LICENSE", "Makefile", "COPYING.GPL-2.0"}
DOCUMENTS = (
    "LICENSE",
    "THIRD_PARTY.md",
    "provision.py",
    "docs/installation.md",
    "docs/advanced-cli.md",
    "docs/troubleshooting.md",
    "docs/recovery.md",
    "docs/development/firmware-kit.md",
)
TOKEN = re.compile(r"[\w./-]+")
INCLUDE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)


def _inside(root, path):
    """Normalise without following symlinks; None if outside the shippable trees."""
    path = Path(os.path.normpath(path))
    if not path.is_relative_to(root) or path == root:
        return None
    if path.relative_to(root).parts[0] not in (*PACKAGES, "tests"):
        return None
    return path


def _public(path):
    return (
        path.is_file()
        and not path.is_symlink()
        and "__pycache__" not in path.parts
        and (path.suffix in SUFFIXES or path.name in NAMES)
    )


def _module_file(root, dotted):
    base = root.joinpath(*dotted.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _imports(root, path):
    """Yield dotted project modules imported anywhere in ``path``."""
    tree = ast.parse(path.read_bytes(), str(path))
    package = path.relative_to(root).with_suffix("").parts[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package[: len(package) - node.level + 1]
                module = ".".join((*parts, *(node.module or "").split("."))).strip(".")
            else:
                module = node.module or ""
            yield module
            for alias in node.names:
                yield f"{module}.{alias.name}"


def _strings(path):
    """String constants in a Python file; path-like tokens in any other text."""
    if path.suffix == ".py":
        tree = ast.parse(path.read_bytes(), str(path))
        return {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
    return set(TOKEN.findall(path.read_text(errors="replace")))


def _component(root, path):
    """``firmware/<name>`` or ``tools/<name>`` directory owning ``path``, if any."""
    parts = path.relative_to(root).parts
    if len(parts) >= 3 and parts[0] in COMPONENT_PARENTS:
        return root / parts[0] / parts[1]
    return None


def _references(root, path):
    """Repo files named by string: paths, component names and test fixtures."""
    for value in _strings(path):
        value = value.strip().lstrip("./")
        if not value or len(value) > 200 or "\n" in value:
            continue
        candidates = [root / value, root / "tests" / value]
        candidates += [root / parent / value for parent in COMPONENT_PARENTS]
        for candidate in candidates:
            resolved = _inside(root, candidate)
            if resolved is None or resolved.is_symlink():
                continue
            relative = resolved.relative_to(root).parts
            if resolved.is_dir() and len(relative) == 2 and relative[0] in COMPONENT_PARENTS:
                yield from (p for p in resolved.rglob("*") if _public(p))
            elif (
                resolved.is_file()
                and _public(resolved)
                and (relative[0] != "tests" or resolved.suffix in (".c", ".h"))
            ):
                yield resolved


def selection(root=ROOT):
    """Every repo file the installer needs, as a fixpoint over imports and paths."""
    root = Path(os.path.normpath(Path(root).absolute()))
    todo = [root / "provision.py", *sorted((root / "installer").glob("*.py"))]
    todo.append(root / "tools/installer_archive.py")
    seen = set()
    while todo:
        path = todo.pop()
        if path != root / "provision.py":
            path = _inside(root, path)
        if path is None or path in seen or not _public(path):
            continue
        seen.add(path)
        relative = path.relative_to(root)
        if relative.parts[0] in PACKAGES:
            for depth in range(1, len(relative.parts)):
                init = root.joinpath(*relative.parts[:depth], "__init__.py")
                if init.is_file():
                    todo.append(init)
        component = _component(root, path)
        if component is not None:
            todo.extend(p for p in component.rglob("*") if _public(p))
        if path.suffix == ".py":
            for dotted in _imports(root, path):
                if dotted.split(".")[0] in PACKAGES:
                    found = _module_file(root, dotted)
                    if found is not None:
                        todo.append(found)
        if path.suffix in (".c", ".h", ".S"):
            text = path.read_text(errors="replace")
            todo.extend(path.parent / name for name in INCLUDE.findall(text))
        # Prose never selects code: only sources, scripts and data are scanned.
        if relative.parts[0] != "tests" and path.suffix != ".md":
            todo.extend(_references(root, path))
    return seen


def files(root=ROOT):
    """Map archive names to bytes for the installer, rooted at ``root``."""
    root = Path(os.path.normpath(Path(root).absolute()))
    names = {p.relative_to(root).as_posix(): p for p in selection(root)}
    for name in DOCUMENTS:
        names[name] = root / name
    readme = root / "installer/README.md"
    names["README.md"] = readme if readme.is_file() else root / "README.md"
    return {name: path.read_bytes() for name, path in sorted(names.items())}


def write(path, data, prefix=""):
    """Deterministic ZIP: fixed timestamps, modes and ordering."""
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, content in sorted(data.items()):
            info = zipfile.ZipInfo(prefix + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, content)


def installer_archive(path, prefix=""):
    write(path, files(ROOT), prefix)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the public Nest installer archive")
    parser.add_argument("output")
    parser.add_argument("--list", action="store_true", help="print the selected files only")
    args = parser.parse_args()
    if args.list:
        print("\n".join(files(ROOT)))
    else:
        installer_archive(args.output)
