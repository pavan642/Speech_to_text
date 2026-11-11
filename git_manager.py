# git_manager.py
"""Pushes the app folder to a configured git remote (init / add / commit / push)."""
import logging
import os
import shutil
import subprocess

logger = logging.getLogger("SpeechEditor")


class GitError(RuntimeError):
    pass


def _git(args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=180
    )


def push_all(repo_path: str, remote_url: str, branch: str, message: str) -> str:
    """Commits everything and pushes to <remote_url> <branch>. Returns a log."""
    if not shutil.which("git"):
        raise GitError("git is not installed (not found in PATH).")
    if not os.path.isdir(repo_path):
        raise GitError(f"Repo path does not exist: {repo_path}")
    if not remote_url:
        raise GitError("No git remote URL configured — open ⚙️ Settings.")
    branch = branch or "main"

    log = []

    def run(*args, check=True):
        proc = _git(list(args), repo_path)
        out = (proc.stdout + proc.stderr).strip()
        if out:
            log.append(f"$ git {' '.join(args)}\n{out}")
        if check and proc.returncode != 0:
            raise GitError(out or f"git {' '.join(args)} failed ({proc.returncode})")
        return proc

    # 1. Init repo if needed
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        run("init")

    # 2. Stage everything (.gitignore is respected: settings.json, history/)
    run("add", "-A")

    # 3. Commit only if something is staged
    staged = _git(["diff", "--cached", "--quiet"], repo_path)
    if staged.returncode != 0:
        run("commit", "-m", message)
    else:
        log.append("Nothing new to commit.")

    # 4. Point origin at the configured remote
    remote = _git(["remote", "get-url", "origin"], repo_path)
    if remote.returncode != 0:
        run("remote", "add", "origin", remote_url)
    elif remote.stdout.strip() != remote_url:
        run("remote", "set-url", "origin", remote_url)

    # 5. Push the branch upstream
    run("checkout", "-B", branch)
    run("push", "-u", "origin", branch)

    logger.info("Git push completed.")
    return "\n\n".join(log) or "Done."
