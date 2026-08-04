from __future__ import annotations

import ast
from pathlib import Path

import auto_video_sub_domain


def test_domain_package_imports_only_standard_library() -> None:
    package_root = Path(__file__).parents[1] / "src" / "auto_video_sub_domain"
    forbidden_roots = {
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "temporalio",
        "boto3",
        "auto_video_sub_application",
        "auto_video_sub_infrastructure",
        "auto_video_sub_providers",
    }

    imported_roots: set[str] = set()
    for source_file in package_root.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])

    assert imported_roots.isdisjoint(forbidden_roots)
    assert auto_video_sub_domain.__version__ == "0.1.0"
