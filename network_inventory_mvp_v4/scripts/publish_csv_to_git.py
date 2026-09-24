#!/usr/bin/env python3
"""Commit and push an updated seating CSV to GitHub securely.

Credentials are read only from environment variables:
  GIT_USERNAME  optional (defaults to x-access-token)
  GIT_TOKEN     required for HTTPS repositories

The token is never placed in command-line arguments or printed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd, *, cwd=None, env=None, check=True):
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-url", required=True)
    p.add_argument("--branch", default="main")
    p.add_argument("--project-subdir", required=True)
    p.add_argument("--source-file", required=True)
    p.add_argument("--destination-name", default="floor_33_import_template.csv")
    p.add_argument("--workspace", required=True)
    p.add_argument("--commit-message", required=True)
    p.add_argument("--git-user-name", default="AWX Network Inventory")
    p.add_argument("--git-user-email", default="awx-network-inventory@users.noreply.github.com")
    args = p.parse_args()

    source = Path(args.source_file)
    if not source.exists():
        print(f"ERROR: Source CSV does not exist: {source}", file=sys.stderr)
        return 2

    token = os.environ.get("GIT_TOKEN", "")
    username = os.environ.get("GIT_USERNAME", "x-access-token") or "x-access-token"
    if args.repo_url.startswith("https://") and not token:
        print("ERROR: GIT_TOKEN is required for HTTPS GitHub push.", file=sys.stderr)
        return 2

    workspace = Path(args.workspace)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    askpass_path = None
    if args.repo_url.startswith("https://"):
        fd, askpass_name = tempfile.mkstemp(prefix="awx-git-askpass-", suffix=".sh")
        os.close(fd)
        askpass_path = Path(askpass_name)
        askpass_path.write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  *Username*) printf '%s\\n' \"$GIT_USERNAME\" ;;\n"
            "  *Password*) printf '%s\\n' \"$GIT_TOKEN\" ;;\n"
            "  *) printf '\\n' ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        askpass_path.chmod(0o700)
        env["GIT_ASKPASS"] = str(askpass_path)
        env["GIT_USERNAME"] = username
        env["GIT_TOKEN"] = token

    try:
        clone = run(
            ["git", "clone", "--depth", "1", "--branch", args.branch, args.repo_url, str(workspace)],
            env=env,
            check=False,
        )
        if clone.returncode != 0:
            print("ERROR: Git clone failed.", file=sys.stderr)
            print(clone.stderr.strip(), file=sys.stderr)
            return 3

        destination = workspace / args.project_subdir / "baseline" / args.destination_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

        relative = destination.relative_to(workspace)
        status = run(["git", "status", "--porcelain", "--", str(relative)], cwd=workspace, env=env)
        if not status.stdout.strip():
            print("GitHub publish: no seating CSV changes to commit.")
            return 0

        run(["git", "config", "user.name", args.git_user_name], cwd=workspace, env=env)
        run(["git", "config", "user.email", args.git_user_email], cwd=workspace, env=env)
        run(["git", "add", "--", str(relative)], cwd=workspace, env=env)
        commit = run(["git", "commit", "-m", args.commit_message], cwd=workspace, env=env, check=False)
        if commit.returncode != 0:
            print("ERROR: Git commit failed.", file=sys.stderr)
            print(commit.stderr.strip() or commit.stdout.strip(), file=sys.stderr)
            return 4

        push = run(["git", "push", "origin", args.branch], cwd=workspace, env=env, check=False)
        if push.returncode != 0:
            print("ERROR: Git push failed. Repository was not updated.", file=sys.stderr)
            print(push.stderr.strip(), file=sys.stderr)
            return 5

        print(f"GitHub publish: updated {relative} on branch {args.branch}.")
        return 0
    finally:
        if askpass_path:
            try:
                askpass_path.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
