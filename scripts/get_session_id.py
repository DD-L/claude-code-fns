#!/usr/bin/env python3
"""
Get session_id (WT_SESSION) for use in fn-controller / stack_ops.

Reference implementation. Use from:
  - PowerShell:  $env:WT_SESSION is set by Windows Terminal
  - Git Bash:    WT_SESSION is inherited when launched from PowerShell/Claude Code

Usage:
  python scripts/get_session_id.py              # print raw value
  python scripts/get_session_id.py --format raw
  python scripts/get_session_id.py --format powershell   # print PowerShell echo line
  python scripts/get_session_id.py --format bash         # print Bash export line (eval-friendly)

Echo forms (for reference):
  - In PowerShell:  echo "WT_SESSION=$env:WT_SESSION"
  - In Git Bash:    echo "WT_SESSION=$WT_SESSION"
"""

import os
import sys
import argparse


def get_session_id() -> str:
    """Get WT_SESSION from environment (same as PowerShell $env:WT_SESSION)."""
    return os.environ.get("WT_SESSION", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Get session_id (WT_SESSION)")
    parser.add_argument(
        "--format", "-f",
        choices=["raw", "powershell", "bash"],
        default="raw",
        help="Output format: raw value, PowerShell echo line, or Bash export line",
    )
    args = parser.parse_args()
    sid = get_session_id()

    if args.format == "powershell":
        # Line you would run in PowerShell to display WT_SESSION
        print('echo "WT_SESSION=$env:WT_SESSION"')
    elif args.format == "bash":
        # Export form for Bash: eval "$(python get_session_id.py -f bash)" to set WT_SESSION
        print(f"WT_SESSION={sid}")
    else:
        print(sid)


if __name__ == "__main__":
    main()
