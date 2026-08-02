# 🐙 GitHub & Git Cheat Sheet

> **Quick-reference for everyday Git & GitHub work.**
> Every command has a short hint next to it (`# like this`) so you can scan fast.
> Replace anything in `<angle-brackets>` with your own value.

---

## 📑 Table of Contents
1. [First-Time Setup](#1-first-time-setup)
2. [Starting a Repository](#2-starting-a-repository)
3. [Daily Workflow (The Core Loop)](#3-daily-workflow-the-core-loop)
4. [Checking Status & History](#4-checking-status--history)
5. [Branching](#5-branching)
6. [Merging & Rebasing](#6-merging--rebasing)
7. [Working with Remotes (GitHub)](#7-working-with-remotes-github)
8. [Undoing Things (Lifesavers)](#8-undoing-things-lifesavers)
9. [Stashing (Park Your Work)](#9-stashing-park-your-work)
10. [Tags & Releases](#10-tags--releases)
11. [Inspecting & Comparing](#11-inspecting--comparing)
12. [.gitignore](#12-gitignore)
13. [Pull Requests (GitHub Flow)](#13-pull-requests-github-flow)
14. [GitHub CLI (gh)](#14-github-cli-gh)
15. [Emergency / "Oh No" Cheatsheet](#15-emergency--oh-no-cheatsheet)
16. [Glossary](#16-glossary)

---

## 1. First-Time Setup
> Run these **once** per machine. They stamp your identity on every commit.

```bash
git config --global user.name  "Ahmed Elshety"        # Your name on every commit
git config --global user.email "you@example.com"      # Must match your GitHub email
git config --global init.defaultBranch main           # New repos start on 'main' not 'master'
git config --global core.editor "code --wait"         # Use VS Code for commit messages
git config --global pull.rebase false                 # 'git pull' merges by default (safe choice)
git config --list                                     # Show all your current settings
```

💡 **Tip:** `--global` = applies to all repos. Drop it to set a value for just the current repo.

---

## 2. Starting a Repository
> Two ways to begin: create fresh, or copy an existing one from GitHub.

```bash
git init                                # Turn the current folder into a Git repo
git clone <url>                         # Download a GitHub repo (full history) to your PC
git clone <url> <folder-name>           # Clone into a specific folder name
git clone --depth 1 <url>               # Shallow clone (latest snapshot only, faster)
```

💡 **Hint:** After `git init`, connect it to GitHub with the commands in [Section 7](#7-working-with-remotes-github).

---

## 3. Daily Workflow (The Core Loop)
> **The 3 steps you'll repeat 100× a day:** edit → stage → commit.

```bash
git add <file>                          # Stage ONE specific file for the next commit
git add .                               # Stage ALL changed files in current folder & below
git add -A                              # Stage everything (new, modified, AND deleted)
git add -p                              # Stage changes chunk-by-chunk (great for reviewing)

git commit -m "Add login validation"    # Save staged changes with a message
git commit -am "Fix typo"                # Stage tracked files + commit in ONE step
git commit --amend -m "New message"      # Rewrite the LAST commit (before pushing!)
```

### 🔁 The mental model
```
Working Directory  →  Staging Area  →  Repository  →  GitHub
   (your edits)   add    (git add)   commit  (.git)   push
```

💡 **Good commit messages:** short summary line (~50 chars), present tense — *"Add"*, *"Fix"*, *"Update"*.

---

## 4. Checking Status & History

```bash
git status                              # What's changed / staged / untracked (use CONSTANTLY)
git status -s                           # Short, compact version of status
git log                                 # Full commit history (press 'q' to quit)
git log --oneline                       # One line per commit — clean & scannable
git log --oneline --graph --all         # Visual branch/merge tree of everything
git log -p                              # Show the actual code changes in each commit
git log -n 5                            # Show only the last 5 commits
git log --author="Ahmed"                # Filter commits by author
git show <commit-hash>                  # Full details of one specific commit
```

💡 **Tip:** `git log --oneline --graph --all` is the best "where am I?" command.

---

## 5. Branching
> Branches let you work on features without breaking `main`.

```bash
git branch                              # List local branches (* marks current one)
git branch -a                           # List ALL branches (local + remote)
git branch <name>                       # Create a new branch (but stay where you are)
git switch <name>                       # Move to an existing branch  (modern & clear)
git switch -c <name>                    # Create AND move to a new branch in one step
git checkout <name>                     # Older way to switch branches (still works)
git checkout -b <name>                  # Older way to create + switch

git branch -m <old> <new>               # Rename a branch
git branch -d <name>                    # Delete a branch (safe: blocks if unmerged)
git branch -D <name>                    # Force-delete a branch (⚠️ discards work)
```

💡 **Convention:** name branches like `feature/login`, `fix/crash-on-save`, `docs/readme`.

---

## 6. Merging & Rebasing
> Bring changes from one branch into another.

```bash
git merge <branch>                      # Merge <branch> INTO your current branch
git merge --no-ff <branch>              # Always create a merge commit (keeps history clear)
git merge --abort                       # Cancel a merge that hit conflicts

git rebase <branch>                     # Replay your commits on top of <branch> (linear history)
git rebase -i HEAD~3                    # Interactively edit/squash the last 3 commits
git rebase --abort                      # Bail out of a rebase gone wrong
git rebase --continue                   # Resume rebase after fixing conflicts
```

### ⚔️ Resolving merge conflicts
```bash
# 1. Git marks conflicts in files like this:
#    <<<<<<< HEAD
#    your version
#    =======
#    their version
#    >>>>>>> branch-name
# 2. Edit the file, keep what you want, delete the <<< === >>> markers.
git add <resolved-file>                 # Mark conflict as resolved
git commit                              # Finish the merge
```

💡 **Rule of thumb:** `merge` = safe & keeps true history. `rebase` = clean linear history but **never rebase shared/pushed branches.**

---

## 7. Working with Remotes (GitHub)
> A "remote" is your copy on GitHub. Default name is usually `origin`.

```bash
git remote -v                           # List remotes and their URLs
git remote add origin <url>             # Connect local repo to a GitHub repo
git remote set-url origin <new-url>     # Change the remote URL (e.g. HTTPS → SSH)
git remote remove origin                # Disconnect a remote

git push -u origin main                 # First push: send 'main' + remember the link
git push                                # Push commits to the remembered remote
git push origin <branch>                # Push a specific branch
git push --tags                         # Push your tags too

git pull                                # Fetch remote changes + merge into current branch
git pull --rebase                       # Fetch + rebase (keeps history linear)
git fetch                               # Download remote changes WITHOUT merging (safe peek)
git fetch --prune                       # Fetch + delete refs for branches gone from GitHub
```

💡 **`fetch` vs `pull`:** `fetch` just downloads. `pull` = `fetch` + `merge`. Use `fetch` when you want to look before you leap.

---

## 8. Undoing Things (Lifesavers)
> The most-searched Git topic. Bookmark this section. 🔖

```bash
git restore <file>                      # Discard unstaged changes to a file (⚠️ can't undo)
git restore --staged <file>             # Unstage a file (keep the edits)
git restore --source=HEAD~1 <file>      # Restore a file from a previous commit

git reset <file>                        # Unstage a file (older syntax, same idea)
git reset --soft HEAD~1                 # Undo last commit, KEEP changes staged
git reset --mixed HEAD~1                # Undo last commit, keep changes UNstaged (default)
git reset --hard HEAD~1                 # ⚠️ Undo last commit AND delete the changes

git revert <commit-hash>                # Make a NEW commit that undoes an old one (safe for shared history)
git clean -fd                           # ⚠️ Delete untracked files & folders (dry-run: -n)
```

⚠️ **`--hard` and `clean -fd` permanently destroy work.** Add `-n` (dry run) to `clean` first to preview.
💡 **Pushed already?** Use `revert` (safe). **Not pushed yet?** `reset` is fine.

---

## 9. Stashing (Park Your Work)
> Save unfinished changes temporarily so you can switch branches cleanly.

```bash
git stash                               # Shelve all changes, revert to clean working dir
git stash push -m "half-done navbar"    # Stash with a descriptive label
git stash list                          # See all stashes
git stash apply                         # Re-apply the latest stash (keeps it in the list)
git stash pop                           # Re-apply latest stash AND remove it from the list
git stash drop                          # Delete the latest stash
git stash clear                         # Delete ALL stashes
```

💡 **Use case:** "I'm mid-feature but need to quickly fix `main`." → `git stash`, fix, then `git stash pop`.

---

## 10. Tags & Releases
> Tags mark important points — usually version releases.

```bash
git tag                                 # List all tags
git tag v1.0.0                          # Create a lightweight tag on current commit
git tag -a v1.0.0 -m "First release"    # Annotated tag (recommended — has author/date/msg)
git tag -a v1.0.0 <commit-hash>         # Tag a specific past commit
git push origin v1.0.0                  # Push a single tag to GitHub
git push --tags                         # Push all tags
git tag -d v1.0.0                       # Delete a tag locally
git push origin --delete v1.0.0         # Delete a tag on GitHub
```

💡 **Semantic versioning:** `vMAJOR.MINOR.PATCH` → `v2.1.4`.

---

## 11. Inspecting & Comparing

```bash
git diff                                # Unstaged changes vs last commit
git diff --staged                       # Staged changes vs last commit (what you're about to commit)
git diff <branch1> <branch2>            # Compare two branches
git diff <commit1> <commit2>            # Compare two commits
git blame <file>                        # Show who last changed each line (& when)
git show <commit-hash>:<file>           # View a file as it was in a specific commit
```

💡 **Tip:** Run `git diff --staged` right before committing to double-check what's going in.

---

## 12. .gitignore
> A file listing what Git should **never** track (secrets, builds, junk).

```gitignore
# Dependencies
node_modules/
.venv/
__pycache__/

# Environment & secrets  (NEVER commit these!)
.env
*.key

# Build output
dist/
build/
*.log

# OS / editor files
.DS_Store
.vscode/
Thumbs.db
```

```bash
git rm -r --cached <file>               # Stop tracking a file already committed (then commit)
```

💡 **Already committed a secret?** Removing it from `.gitignore` isn't enough — it stays in history. Rotate the secret and consider `git filter-repo`.

---

## 13. Pull Requests (GitHub Flow)
> The standard team workflow — no command memorization needed, mostly done on github.com.

```
1. git switch -c feature/my-change      # Create a feature branch
2. ...edit, git add, git commit...      # Do your work
3. git push -u origin feature/my-change # Push the branch to GitHub
4. Open github.com → click "Compare & pull request"
5. Describe your changes → "Create pull request"
6. Teammate reviews → approves → "Merge pull request"
7. git switch main && git pull          # Update your local main
8. git branch -d feature/my-change      # Clean up the merged branch
```

💡 **Golden rule:** never commit straight to `main` on a team. Branch → PR → review → merge.

---

## 14. GitHub CLI (gh)
> Optional but powerful — do GitHub tasks from the terminal. Install from **cli.github.com**.

```bash
gh auth login                           # Log in to GitHub from the terminal
gh repo create <name> --public          # Create a new GitHub repo
gh repo clone <owner>/<repo>            # Clone a repo
gh repo view --web                      # Open the current repo in your browser

gh pr create --title "..." --body "..." # Open a pull request
gh pr list                              # List open PRs
gh pr checkout <number>                 # Check out someone's PR locally to test it
gh pr merge <number>                    # Merge a PR from the terminal

gh issue create                         # Open a new issue
gh issue list                           # List open issues
```

💡 **Why use it:** create repos & PRs without leaving VS Code's terminal.

---

## 15. Emergency / "Oh No" Cheatsheet
> Panic-button reference. 🚨

| 😱 Situation | ✅ Command |
|---|---|
| Committed to the wrong branch | `git reset HEAD~1` then switch branch & re-commit |
| Need to undo the last commit (not pushed) | `git reset --soft HEAD~1` (keeps changes) |
| Need to undo a **pushed** commit safely | `git revert <hash>` |
| Accidentally `git add`-ed a file | `git restore --staged <file>` |
| Want to throw away ALL local changes | `git restore .` (⚠️ irreversible) |
| Lost a commit / branch | `git reflog` → find hash → `git checkout <hash>` |
| Wrong commit message (not pushed) | `git commit --amend -m "New message"` |
| Merge went wrong | `git merge --abort` |
| Pushed a secret | Rotate the secret NOW, then scrub history |
| "detached HEAD" state | `git switch -c <new-branch>` to save your work |

```bash
git reflog                              # 🦸 Your safety net: a log of EVERY move HEAD made.
                                        #     Recover "lost" commits by their hash from here.
```

💡 **`git reflog` is the single most reassuring command in Git.** Almost nothing is ever truly lost.

---

## 16. Glossary

| Term | Meaning |
|---|---|
| **Repository (repo)** | A project folder tracked by Git, including its full history. |
| **Commit** | A saved snapshot of your changes, with a message + unique hash. |
| **Branch** | A movable pointer to a line of development (e.g. `main`, `feature/x`). |
| **HEAD** | A pointer to your current commit / branch — "where you are now". |
| **Remote / origin** | The copy of your repo hosted on GitHub. `origin` is its default name. |
| **Clone** | A full local copy of a remote repo. |
| **Fork** | Your own GitHub copy of *someone else's* repo. |
| **Staging area (index)** | The "waiting room" for changes before a commit (`git add`). |
| **Pull Request (PR)** | A GitHub request to merge your branch into another, with review. |
| **Merge** | Combining changes from one branch into another. |
| **Rebase** | Replaying commits onto a new base for a linear history. |
| **Stash** | A temporary shelf for uncommitted changes. |
| **Tag** | A named marker for a specific commit, usually a version release. |

---

### ⚡ The 90% Workflow (memorize just this)
```bash
git status                   # See what changed
git add .                    # Stage everything
git commit -m "message"      # Save a snapshot
git pull                     # Get teammates' latest
git push                     # Share your work
```

> 🎯 Master these 5 lines and you can handle almost every day. Everything else is for the special cases above.

---
*Made for Ahmed — happy committing! 🚀*
