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
        except:
            data = {"version": "1.0.0"}
            
    v = data.get("version", "1.0.0")
    parts = v.split(".")
    
    # افزاش شماره پچ (Patch)
    parts[-1] = str(int(parts[-1]) + 1)
    new_version = ".".join(parts)
    
    data["version"] = new_version
    data["updated_at"] = datetime.datetime.now().isoformat()
    
    with open(version_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    return new_version

def run_cmd(cmd):
    print(f"> {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def main():
    commit_msg = sys.argv[1] if len(sys.argv) > 1 else "Auto-update version"
    
    print("شروع فرآیند انتشار نسخه جدید...")
    new_version = bump_version()
    print(f"[*] نسخه برنامه به {new_version} ارتقا یافت.")
    
    try:
        run_cmd(["git", "add", "."])
        run_cmd(["git", "commit", "-m", f"{commit_msg} (v{new_version})"])
        run_cmd(["git", "push"])
        print("\n✅ کد با موفقیت در گیت‌هاب پوش شد و نسخه جدید در دسترس است!")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ خطا در هنگام کار با گیت: {e}")
        print("لطفاً مطمئن شوید که تغییراتی برای پوش کردن وجود دارد.")

if __name__ == "__main__":
    main()
