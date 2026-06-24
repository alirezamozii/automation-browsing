import json
import subprocess
import sys
from pathlib import Path
import datetime

def bump_version():
    version_file = Path("version.json")
    if not version_file.exists():
        data = {"version": "1.0.0"}
    else:
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"version": "1.0.0"}

    v = data.get("version", "1.0.0")
    parts = v.split(".")

    # افزایش شماره پچ (Patch)
    parts[-1] = str(int(parts[-1]) + 1)
    new_version = ".".join(parts)

    data["version"] = new_version
    data["updated_at"] = datetime.datetime.now().isoformat()
    # commit_sha will be filled AFTER the push (see save_commit_sha)

    with open(version_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    return new_version


def save_commit_sha():
    """
    After a successful push, read the HEAD SHA and store it in version.json.
    This lets the updater do smart diff-based downloads on the client side.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        sha = result.stdout.strip()

        version_file = Path("version.json")
        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["commit_sha"] = sha

        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        print(f"[*] SHA کامیت ({sha[:8]}...) در version.json ذخیره شد.")
        return sha
    except Exception as e:
        print(f"⚠️  نمی‌توان SHA کامیت را ذخیره کرد: {e}")
        return None


def run_cmd(cmd):
    print(f"> {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def is_git_repo():
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True
        )
        return res.returncode == 0
    except Exception:
        return False


def main():
    commit_msg = sys.argv[1] if len(sys.argv) > 1 else "Auto-update version"

    print("شروع فرآیند انتشار نسخه جدید...")
    new_version = bump_version()
    print(f"[*] نسخه برنامه به {new_version} ارتقا یافت.")

    if not is_git_repo():
        print("\n⚠️ هشدار: این پوشه یک مخزن گیت (Git repository) نیست.")
        print("فایل نسخه (version.json) بروزرسانی شد، اما تغییرات در گیت commit یا push نشدند.")
        return

    try:
        run_cmd(["git", "add", "."])
        run_cmd(["git", "commit", "-m", f"{commit_msg} (v{new_version})"])
        run_cmd(["git", "push"])

        # ── After a successful push, record the exact SHA ──────────────────
        sha = save_commit_sha()

        # Amend the commit to include the updated version.json with SHA
        if sha:
            run_cmd(["git", "add", "version.json"])
            # Check if there's anything to amend
            status = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                capture_output=True
            )
            if status.returncode != 0:
                # There are staged changes — amend the last commit
                subprocess.run(
                    ["git", "commit", "--amend", "--no-edit"],
                    check=True
                )
                run_cmd(["git", "push", "--force-with-lease"])
                # Update SHA again after amend
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True, text=True, check=True
                )
                final_sha = result.stdout.strip()
                version_file = Path("version.json")
                with open(version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["commit_sha"] = final_sha
                with open(version_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                print(f"[*] SHA نهایی ({final_sha[:8]}...) ذخیره شد.")

        print("\n✅ کد با موفقیت در گیت‌هاب پوش شد و نسخه جدید در دسترس است!")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ خطا در هنگام کار با گیت: {e}")
        print("لطفاً مطمئن شوید که تغییراتی برای پوش کردن وجود دارد.")


if __name__ == "__main__":
    main()
