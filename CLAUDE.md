# Katib - Project Context for Claude Code

## Overview
Katib is a macOS podcast downloader with a Python GUI. It automates downloading and organizing podcast episodes from RSS feeds.

## Tech Stack
- **Python 3.9+** with PySide6 (Qt) GUI
- **Key libraries**: PySide6, feedparser, requests, python-dateutil
- **Automation**: LaunchD (runs daily at 9 AM PT)
- **Config**: JSON file at `~/Documents/Katib/config/katib_config.json`

## Architecture

```
┌─────────────────────────────────────────────┐
│  katib_qt.py (PySide6 GUI)                  │
│  - KatibWindow class (QMainWindow)          │
│  - QThread workers for async operations     │
│  - QFileSystemWatcher for instant updates   │
│  - 30-second periodic refresh via QTimer    │
└─────────────────────────────────────────────┘
                    │ imports
                    ↓
┌─────────────────────────────────────────────┐
│  katib_downloader.py (Engine - 701 lines)   │
│  - RSS parsing with 4 fallback methods      │
│  - Queue processing (sequential FIFO)       │
│  - Download with retry (max 5 attempts)     │
│  - Triple dedup: ID + URL + title check     │
└─────────────────────────────────────────────┘
                    │ manages
                    ↓
┌─────────────────────────────────────────────┐
│  ~/Documents/Katib/                         │
│  ├── config/katib_config.json               │
│  ├── podcasts/[PodcastName]/*.mp3           │
│  ├── transcripts/ (future)                  │
│  └── logs/                                  │
└─────────────────────────────────────────────┘
```

## Key Files
| File | Purpose |
|------|---------|
| `katib_qt.py` | Main GUI application (PySide6 - fast) |
| `katib.py` | Legacy tkinter GUI (backup) |
| `katib_downloader.py` | Download engine, RSS parsing, config management |
| `backfill_history.py` | Creates history entries for existing downloads |
| `katib_daily_download.sh` | Shell wrapper for LaunchD automation |
| `com.katib.download.plist` | LaunchD config (9 AM PT daily) |
| `katib_cleanup.py` | MP3 cleanup script (deletes transcribed files after 14 days) |
| `katib_daily_cleanup.sh` | Shell wrapper for cleanup automation |
| `com.katib.cleanup.plist` | LaunchD config for cleanup (10 PM PT daily) |

## Config Structure
```json
{
  "podcasts": [{name, rss_url, date_added, total_episodes, downloaded_count}],
  "download_queue": [{podcast_name, episode_title, episode_url, status, retry_count}],
  "failed_downloads": [{..., last_error, last_attempt}],
  "download_history": {"PodcastName": [{episode_title, episode_url, downloaded_at}]},
  "last_check": "timestamp"
}
```

## Key Functions
- `parse_rss_feed(url)` - Extract episodes from RSS (tries enclosures → links → media_content → regex)
- `check_new_episodes(podcast)` - Find new episodes with triple dedup check
- `process_download_queue()` - Sequential FIFO processing with retry logic
- `download_file(url, path)` - HTTP streaming with resume support
- `cleanup_duplicate_queue_items()` - Remove queue items already in history

## Recent Fixes (Jan 2025)
- **Duplicate detection bug**: Now checks `download_history` in addition to queue/failed when detecting new episodes
- **UI performance**: Added display caching and debounced refresh to reduce lag
- **Cleanup utility**: Added `cleanup_duplicates()` to remove already-downloaded items from queue

## Future Features (from README roadmap)
- Transcription integration
- Episode search/filter
- Pause/resume downloads
- Download speed limiting
- Episode deletion management

---

## Session Progress Log

### Session 1 - 2026-01-12
- Cloned repo into Claude Code workspace
- Created this CLAUDE.md file for context persistence
- **GUI Rewrite: tkinter → PySide6**
  - Created `katib_qt.py` with PySide6 for faster, snappier GUI
  - Added PySide6 to requirements.txt
  - Updated Katib.app launch script to prefer katib_qt.py
  - Key improvements:
    - QThread workers for non-blocking async operations
    - QFileSystemWatcher for instant config change detection
    - Native Qt event loop (C++ performance)
    - Efficient QListWidget with signal blocking during batch updates
  - Old tkinter version (`katib.py`) kept as backup
- **MP3 Cleanup Feature**
  - Created `katib_cleanup.py` to delete MP3s after transcription + 14 days
  - Added "Cleanup Old MP3s" button to GUI
  - Created LaunchD plist for daily automated cleanup at 10 PM PT
  - Fixed `total_episodes` count to update when checking for new episodes

---

## Notes & Decisions

### GUI Framework Choice (2026-01-12)
Chose PySide6 (Qt) over alternatives:
- **Dear PyGui**: Fastest but different look/feel
- **Flet**: Good but newer/less mature
- **Textual**: Terminal-only

PySide6 provides native macOS look, mature ecosystem, and excellent performance via signal/slot architecture.

