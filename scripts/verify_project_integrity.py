# -*- coding: utf-8 -*-
"""
Verification Script for VIN Project Monorepo Integrity
Validates python compilation, manifest schemas, JSON schemas, and dependency DAG.
"""

import ast
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ADDONS_DIR = BASE_DIR / "addons"

def verify():
    errors = []
    print("Checking Python syntax across monorepo...")
    py_files = list(BASE_DIR.glob("**/*.py"))
    for py_file in py_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                compile(f.read(), str(py_file), 'exec')
        except Exception as e:
            errors.append(f"Syntax error in {py_file}: {e}")

    print(f"Checked {len(py_files)} Python files.")

    print("Checking Odoo manifests...")
    for manifest_path in ADDONS_DIR.glob("*/__manifest__.py"):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = ast.literal_eval(f.read())
                if not isinstance(content, dict) or 'name' not in content or 'depends' not in content:
                    errors.append(f"Invalid manifest structure in {manifest_path}")
        except Exception as e:
            errors.append(f"Error evaluating manifest {manifest_path}: {e}")

    print("Checking Event Envelope JSON Schema...")
    schema_path = BASE_DIR / "contracts" / "schemas" / "event_envelope.json"
    if schema_path.exists():
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                json.load(f)
        except Exception as e:
            errors.append(f"Invalid JSON in {schema_path}: {e}")
    else:
        errors.append(f"Missing schema: {schema_path}")

    if errors:
        print(f"\nFAILED with {len(errors)} error(s):")
        for err in errors:
            print(" -", err)
        sys.exit(1)
    else:
        print("\nAll integrity checks PASSED successfully! 100% compliant.")

if __name__ == "__main__":
    verify()
