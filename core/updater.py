import urllib.request
import urllib.error
import logging
import asyncio
from pathlib import Path
import json

logger = logging.getLogger("automation_platform.updater")

GITHUB_OWNER = "alirezamozii"
GITHUB_REPO  = "automation-browsing"
GITHUB_BRANCH = "main"

GITHUB_VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/version.json"
GITHUB_API_COMMITS = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
GITHUB_API_COMPARE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/compare/{{base}}...{{head}}"
GITHUB_RAW_FILE    = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{{path}}"

# ── Files / folders we are allowed to overwrite ──────────────────────────────
# Everything else (user data) is NEVER touched.
ALLOWED_DIRS  = {"api", "browser", "core", "locators", "ui", "storage"}
# workflows/ is allowed BUT workflow_template/ inside it is personal — protected below
ALLOWED_WORKFLOW_SUBDIRS_BLOCKED = {"workflow_template", "archive"}
ALLOWED_FILES = {"main.py", "config.py", "requirements.txt", "version.json"}

# ── User-data paths that must NEVER be deleted or replaced ───────────────────
# These live in APP_DIR (APPDATA/AutomationPlatform), so they won't be touched
# by the file-copy logic anyway, but we list them here for documentation.
PROTECTED_PATTERNS = {"*.db", "*.log", "screenshots/*", "chrome_profile/*"}


def parse_version(v_str: str) -> tuple:
    """'1.2.3' → (1, 2, 3)"""
    try:
        return tuple(map(int, v_str.strip("v").split(".")))
    except Exception:
        return (0, 0, 0)


def _get_base_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_local_version() -> dict:
    """Read version.json from the app directory."""
    version_file = _get_base_dir() / "version.json"
    defaults = {"version": "1.0.0", "commit_sha": None}
    if version_file.exists():
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**defaults, **data}
        except Exception:
            pass
    return defaults


def _fetch_json(url: str) -> dict:
    """Fetch JSON from a URL with a User-Agent header."""
    req = urllib.request.Request(url, headers={"User-Agent": "AutomationPlatform-Updater"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _fetch_bytes(url: str) -> bytes:
    """Fetch raw bytes from a URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "AutomationPlatform-Updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

async def check_for_updates() -> dict:
    """
    Compare local version.json with the remote one.
    Returns a dict with keys:
        update_available (bool)
        latest_version   (str)
        local_version    (str)
        latest_sha       (str | None)
        local_sha        (str | None)
        message          (str)
    """
    try:
        remote_data = await asyncio.to_thread(_fetch_json, GITHUB_VERSION_URL)
        latest_version = remote_data.get("version", "1.0.0")
        latest_sha     = remote_data.get("commit_sha")   # may be None for old releases

        local_data    = _load_local_version()
        local_version = local_data.get("version", "1.0.0")
        local_sha     = local_data.get("commit_sha")

        if parse_version(latest_version) > parse_version(local_version):
            return {
                "update_available": True,
                "latest_version":   latest_version,
                "local_version":    local_version,
                "latest_sha":       latest_sha,
                "local_sha":        local_sha,
                "message": f"نسخه جدید ({latest_version}) موجود است. شما در نسخه {local_version} هستید.",
            }

        return {
            "update_available": False,
            "latest_version":   latest_version,
            "local_version":    local_version,
            "latest_sha":       latest_sha,
            "local_sha":        local_sha,
            "message": f"شما از آخرین نسخه ({local_version}) استفاده می‌کنید.",
        }

    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return {
            "update_available": False,
            "message": f"خطا در بررسی آپدیت: {e}",
        }


async def update_from_github(progress_callback=None) -> tuple[bool, str]:
    """
    Smart incremental update:
      1. Fetch the latest commit SHA from GitHub.
      2. Compare it against the locally stored SHA to get only changed files.
      3. Download and apply only those files (skip user-data paths).
      4. Save the new version + SHA to version.json.

    Falls back to a full file-list download if no local SHA is stored.

    progress_callback(percent: int, status_msg: str) is called periodically.
    """
    logger.info("شروع فرآیند آپدیت هوشمند...")

    async def _progress(pct: int, msg: str):
        if progress_callback is None:
            return
        try:
            result = progress_callback(pct, msg)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            pass

    try:
        base_dir = _get_base_dir()

        # ── Step 1: get latest commit SHA ────────────────────────────────────
        await _progress(5, "دریافت اطلاعات آخرین نسخه...")
        latest_commit_data = await asyncio.to_thread(_fetch_json, GITHUB_API_COMMITS)
        latest_sha = latest_commit_data.get("sha")
        if not latest_sha:
            raise ValueError("نمی‌توان SHA آخرین کامیت را دریافت کرد.")

        logger.info(f"Latest remote SHA: {latest_sha[:8]}")

        # ── Step 2: get remote version.json ─────────────────────────────────
        await _progress(10, "خواندن فایل نسخه از سرور...")
        remote_version_data = await asyncio.to_thread(_fetch_json, GITHUB_VERSION_URL)
        latest_version = remote_version_data.get("version", "1.0.0")

        # ── Step 3: decide which files to download ───────────────────────────
        local_data = _load_local_version()
        local_sha  = local_data.get("commit_sha")

        changed_files: list[str] = []   # repo-relative paths, e.g. "core/updater.py"

        if local_sha and local_sha != latest_sha:
            # Use GitHub Compare API — only files that actually changed
            await _progress(20, "مقایسه تغییرات با نسخه قبلی...")
            compare_url = GITHUB_API_COMPARE.format(base=local_sha, head=latest_sha)
            try:
                compare_data = await asyncio.to_thread(_fetch_json, compare_url)
                for file_info in compare_data.get("files", []):
                    status = file_info.get("status")          # added / modified / removed
                    filename = file_info.get("filename", "")
                    if status == "removed":
                        # optionally delete removed source files
                        _safe_delete(base_dir / filename)
                        continue
                    if _is_allowed_path(filename):
                        changed_files.append(filename)
                logger.info(f"Changed files to update ({len(changed_files)}): {changed_files}")
            except urllib.error.HTTPError as e:
                logger.warning(f"Compare API failed ({e}), falling back to full file list.")
                changed_files = await _get_all_repo_files(latest_sha)
        else:
            # No local SHA recorded → first-time smart update, download all source files
            await _progress(20, "اولین بار آپدیت — دریافت لیست کامل فایل‌ها...")
            changed_files = await _get_all_repo_files(latest_sha)

        if not changed_files:
            logger.info("هیچ فایلی برای بروزرسانی وجود ندارد.")
            # Still update version.json with SHA
            _write_version_json(base_dir, latest_version, latest_sha)
            return True, "برنامه از قبل به‌روز است. هیچ فایلی تغییر نکرده بود."

        # ── Step 4: download & apply changed files ───────────────────────────
        total = len(changed_files)
        for idx, rel_path in enumerate(changed_files):
            pct = 30 + int((idx / total) * 60)
            await _progress(pct, f"دانلود: {rel_path}")
            logger.info(f"  Downloading {rel_path}")

            raw_url  = GITHUB_RAW_FILE.format(path=rel_path)
            content  = await asyncio.to_thread(_fetch_bytes, raw_url)

            dest = base_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

        # ── Step 5: save new version.json ────────────────────────────────────
        await _progress(95, "ذخیره اطلاعات نسخه جدید...")
        _write_version_json(base_dir, latest_version, latest_sha)

        await _progress(100, "آپدیت کامل شد!")
        logger.info(f"آپدیت به نسخه {latest_version} (SHA {latest_sha[:8]}) با موفقیت انجام شد.")
        return True, f"آپدیت به نسخه {latest_version} با موفقیت انجام شد! برنامه را مجدداً راه‌اندازی کنید."

    except Exception as e:
        msg = f"خطا در هنگام آپدیت: {e}"
        logger.error(msg, exc_info=True)
        return False, msg


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_allowed_path(rel_path: str) -> bool:
    """Return True only for source-code paths we are allowed to overwrite."""
    parts = Path(rel_path).parts
    if not parts:
        return False
    # Top-level file (e.g. "main.py")
    if len(parts) == 1:
        return parts[0] in ALLOWED_FILES
    # workflows/workflow_template/** and workflows/archive/** → personal user files, never touch
    if parts[0] == "workflows":
        if len(parts) >= 2 and parts[1] in ALLOWED_WORKFLOW_SUBDIRS_BLOCKED:
            return False
        return True
    # File inside any other allowed directory
    return parts[0] in ALLOWED_DIRS


def _safe_delete(path: Path):
    """Delete a file only if it's in an allowed source path."""
    try:
        base = _get_base_dir()
        rel = path.relative_to(base)
        if _is_allowed_path(str(rel)):
            if path.is_file():
                path.unlink(missing_ok=True)
                logger.info(f"  Deleted removed file: {rel}")
    except Exception as e:
        logger.warning(f"Could not delete {path}: {e}")


async def _get_all_repo_files(sha: str) -> list[str]:
    """
    Use the Git Trees API (recursive) to list every blob in the repo,
    then filter to only allowed source paths.
    """
    tree_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/git/trees/{sha}?recursive=1"
    tree_data = await asyncio.to_thread(_fetch_json, tree_url)
    files = []
    for item in tree_data.get("tree", []):
        if item.get("type") == "blob" and _is_allowed_path(item["path"]):
            files.append(item["path"])
    return files


def _write_version_json(base_dir: Path, version: str, sha: str):
    """Persist version + commit SHA so the next update can diff against it."""
    import datetime
    data = {
        "version":    version,
        "commit_sha": sha,
        "updated_at": datetime.datetime.now().isoformat(),
    }
    with open(base_dir / "version.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
