# training/repo_sync.py
# ------------------------------------------------------------
# Commits changed JSON files to your GitHub repo/branch using a PAT.

import os, json
from typing import List
from datetime import datetime

def _load(path):
    with open(path, "rb") as f:
        return f.read()

def push_updates_to_github(paths: List[str], commit_message: str = None) -> dict:
    # Expect Streamlit secrets:
    #   GH_PAT, GH_REPO ("owner/name"), GH_BRANCH (default "main"),
    #   GH_COMMIT_NAME, GH_COMMIT_EMAIL
    try:
        import streamlit as st
        secrets = st.secrets
    except Exception:
        # Fallback to env if running locally
        class _S: pass
        secrets = _S()
        secrets.GH_PAT = os.getenv("GH_PAT")
        secrets.GH_REPO = os.getenv("GH_REPO")
        secrets.GH_BRANCH = os.getenv("GH_BRANCH", "main")
        secrets.GH_COMMIT_NAME = os.getenv("GH_COMMIT_NAME", "BactAI-D Bot")
        secrets.GH_COMMIT_EMAIL = os.getenv("GH_COMMIT_EMAIL", "bot@example.com")

    from github import Github
    g = Github(secrets.GH_PAT)
    repo = g.get_repo(secrets.GH_REPO)
    branch = secrets.GH_BRANCH or "main"

    if not commit_message:
        commit_message = f"chore(train): update learned artifacts ({datetime.utcnow().isoformat()}Z)"

    ref = repo.get_git_ref(f"heads/{branch}")
    base_sha = ref.object.sha
    base_tree = repo.get_git_tree(base_sha)
    element_list = []

    for p in paths:
        if not os.path.exists(p):
            continue
        blob = repo.create_git_blob(_load(p).decode("utf-8"), "utf-8")
        element_list.append(repo.GitTreeElement(
            path=p,
            mode="100644",
            type="blob",
            sha=blob.sha
        ))

    new_tree = repo.create_git_tree(element_list, base_tree)
    parent = repo.get_git_commit(base_sha)
    commit = repo.create_git_commit(commit_message, new_tree, [parent])
    ref.edit(commit.sha)

    return {"committed": paths, "branch": branch, "commit": commit.sha}
