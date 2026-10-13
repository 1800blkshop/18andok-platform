#!/usr/bin/env python3
import os
from pathlib import Path

APPROVAL_DIR = Path(os.getenv("APPROVAL_DIR", "./approvals"))
APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

def create_approval(intent_id: str) -> str:
    flag = APPROVAL_DIR / f"{intent_id}.approved"
    flag.write_text("approved\n", encoding="utf-8")
    return str(flag)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: approval_helper.py <intent_id>")
        raise SystemExit(1)
    print(create_approval(sys.argv[1]))
