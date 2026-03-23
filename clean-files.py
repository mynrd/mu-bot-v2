import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOLDERS = [
    os.path.join(BASE_DIR, "logs"),
    os.path.join(BASE_DIR, "temp"),
]
MAX_AGE_SECONDS = 24 * 60 * 60  # 24 hours


def clean_folder(folder: str) -> tuple[int, int]:
    deleted = 0
    skipped = 0
    now = time.time()

    for entry in os.scandir(folder):
        if not entry.is_file():
            continue
        age = now - entry.stat().st_mtime
        if age > MAX_AGE_SECONDS:
            os.remove(entry.path)
            print(f"  deleted: {entry.name}")
            deleted += 1
        else:
            skipped += 1

    return deleted, skipped


def main():
    total_deleted = 0
    total_skipped = 0

    for folder in FOLDERS:
        if not os.path.isdir(folder):
            print(f"[skip] folder not found: {folder}")
            continue

        print(f"\n[{os.path.basename(folder)}]")
        deleted, skipped = clean_folder(folder)
        print(f"  deleted: {deleted} | kept: {skipped}")
        total_deleted += deleted
        total_skipped += skipped

    print(f"\ndone — total deleted: {total_deleted} | total kept: {total_skipped}")


if __name__ == "__main__":
    main()
