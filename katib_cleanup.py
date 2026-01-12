#!/usr/bin/env python3
"""
Katib MP3 Cleanup Script
Deletes MP3 files that have been transcribed and are older than 14 days.

Criteria for deletion:
1. A corresponding .txt transcript exists in the Transcripts folder
2. The transcript file is at least 14 days old

Can be run standalone or imported by the GUI.
"""

import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Configuration
BASE_DIR = Path.home() / "Documents" / "Katib"
PODCASTS_DIR = BASE_DIR / "podcasts"
TRANSCRIPTS_DIR = BASE_DIR / "Transcripts"
LOGS_DIR = BASE_DIR / "logs"
RETENTION_DAYS = 14

# Setup logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOGS_DIR / f"katib_cleanup_{datetime.now().strftime('%Y-%m-%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_transcript_path(mp3_path):
    """
    Get the corresponding transcript path for an MP3 file.

    MP3: ~/Documents/Katib/podcasts/[Podcast Name]/[Episode].mp3
    TXT: ~/Documents/Katib/Transcripts/[Podcast Name] TXT/[Episode].txt
    """
    podcast_name = mp3_path.parent.name
    episode_name = mp3_path.stem  # filename without extension

    transcript_folder = TRANSCRIPTS_DIR / f"{podcast_name} TXT"
    transcript_file = transcript_folder / f"{episode_name}.txt"

    return transcript_file


def get_transcript_age_days(transcript_path):
    """Get the age of a transcript file in days (based on modification time)."""
    if not transcript_path.exists():
        return None

    mtime = transcript_path.stat().st_mtime
    transcript_date = datetime.fromtimestamp(mtime)
    age = datetime.now() - transcript_date
    return age.days


def find_deletable_mp3s(dry_run=True):
    """
    Find all MP3 files that can be deleted.

    Returns list of tuples: (mp3_path, transcript_path, age_days)
    """
    deletable = []

    if not PODCASTS_DIR.exists():
        logger.warning(f"Podcasts directory not found: {PODCASTS_DIR}")
        return deletable

    # Scan all podcast folders
    for podcast_folder in PODCASTS_DIR.iterdir():
        if not podcast_folder.is_dir():
            continue

        # Find all MP3 files in this podcast folder
        for mp3_file in podcast_folder.glob("*.mp3"):
            transcript_path = get_transcript_path(mp3_file)

            # Check if transcript exists
            if not transcript_path.exists():
                continue

            # Check transcript age
            age_days = get_transcript_age_days(transcript_path)
            if age_days is not None and age_days >= RETENTION_DAYS:
                deletable.append((mp3_file, transcript_path, age_days))

    return deletable


def cleanup_mp3s(dry_run=False):
    """
    Delete MP3 files that meet the cleanup criteria.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting.

    Returns:
        Tuple of (deleted_count, total_size_bytes, errors)
    """
    logger.info(f"Starting MP3 cleanup (dry_run={dry_run})")
    logger.info(f"Retention period: {RETENTION_DAYS} days after transcription")

    deletable = find_deletable_mp3s()

    if not deletable:
        logger.info("No files eligible for deletion")
        return 0, 0, []

    logger.info(f"Found {len(deletable)} files eligible for deletion")

    deleted_count = 0
    total_size = 0
    errors = []

    for mp3_path, transcript_path, age_days in deletable:
        try:
            file_size = mp3_path.stat().st_size

            if dry_run:
                logger.info(f"[DRY RUN] Would delete: {mp3_path.name} "
                           f"(transcript age: {age_days} days, size: {file_size / 1024 / 1024:.1f} MB)")
            else:
                mp3_path.unlink()
                logger.info(f"Deleted: {mp3_path.name} "
                           f"(transcript age: {age_days} days, size: {file_size / 1024 / 1024:.1f} MB)")

            deleted_count += 1
            total_size += file_size

        except Exception as e:
            error_msg = f"Error deleting {mp3_path}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    size_mb = total_size / 1024 / 1024
    action = "Would delete" if dry_run else "Deleted"
    logger.info(f"{action} {deleted_count} files, freeing {size_mb:.1f} MB")

    return deleted_count, total_size, errors


def get_cleanup_stats():
    """
    Get statistics about files eligible for cleanup without deleting.

    Returns dict with:
        - eligible_count: Number of files that can be deleted
        - eligible_size_mb: Total size in MB
        - pending_count: Files with transcripts but not yet 14 days old
        - no_transcript_count: Files without transcripts
    """
    stats = {
        'eligible_count': 0,
        'eligible_size_bytes': 0,
        'pending_count': 0,
        'pending_files': [],
        'no_transcript_count': 0,
    }

    if not PODCASTS_DIR.exists():
        return stats

    for podcast_folder in PODCASTS_DIR.iterdir():
        if not podcast_folder.is_dir():
            continue

        for mp3_file in podcast_folder.glob("*.mp3"):
            transcript_path = get_transcript_path(mp3_file)

            if not transcript_path.exists():
                stats['no_transcript_count'] += 1
                continue

            age_days = get_transcript_age_days(transcript_path)

            if age_days is not None and age_days >= RETENTION_DAYS:
                stats['eligible_count'] += 1
                stats['eligible_size_bytes'] += mp3_file.stat().st_size
            else:
                stats['pending_count'] += 1
                if age_days is not None:
                    days_remaining = RETENTION_DAYS - age_days
                    stats['pending_files'].append({
                        'name': mp3_file.name,
                        'days_remaining': days_remaining
                    })

    return stats


def send_notification(title, message):
    """Send macOS notification."""
    try:
        subprocess.run(
            ['osascript', '-e', f'display notification "{message}" with title "{title}"'],
            capture_output=True
        )
    except Exception:
        pass


def main():
    """Main entry point for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description='Clean up old transcribed MP3 files')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be deleted without actually deleting')
    parser.add_argument('--stats', action='store_true',
                        help='Show cleanup statistics only')
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress notification')

    args = parser.parse_args()

    if args.stats:
        stats = get_cleanup_stats()
        print(f"\nCleanup Statistics:")
        print(f"  Ready for deletion: {stats['eligible_count']} files "
              f"({stats['eligible_size_bytes'] / 1024 / 1024:.1f} MB)")
        print(f"  Pending (< 14 days): {stats['pending_count']} files")
        print(f"  No transcript yet: {stats['no_transcript_count']} files")
        return

    deleted, size, errors = cleanup_mp3s(dry_run=args.dry_run)

    if not args.quiet and not args.dry_run and deleted > 0:
        send_notification(
            "Katib Cleanup",
            f"Deleted {deleted} old MP3s, freed {size / 1024 / 1024:.1f} MB"
        )


if __name__ == '__main__':
    main()
