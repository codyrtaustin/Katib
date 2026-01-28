#!/usr/bin/env python3
"""
Katib - Podcast Downloader GUI Application (PySide6 Version)
Fast, native GUI interface for managing podcast subscriptions and downloads.
"""

import sys
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from dateutil import parser as date_parser
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QListWidget,
    QTextEdit, QProgressBar, QMessageBox, QDialog, QTabWidget,
    QSplitter, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QFileSystemWatcher
from PySide6.QtGui import QFont

# Configuration
BASE_DIR = Path.home() / "Documents" / "Katib"
LOGS_DIR = BASE_DIR / "logs"

# Setup logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)
CONFIG_FILE = BASE_DIR / "config" / "katib_config.json"
PODCASTS_DIR = BASE_DIR / "podcasts"
LOGS_DIR = BASE_DIR / "logs"
AUTOMATION_LOG = LOGS_DIR / "launchd_download.log"

# Import downloader functions
sys.path.insert(0, str(Path(__file__).parent))
from katib_downloader import (
    load_config, save_config, check_new_episodes,
    process_download_queue, sanitize_filename, parse_rss_feed,
    cleanup_duplicate_queue_items
)
from katib_cleanup import cleanup_mp3s, get_cleanup_stats


class AddPodcastWorker(QThread):
    """Worker thread for adding podcasts."""
    finished = Signal(str, int)  # podcast_name, episode_count
    error = Signal(str)
    confirm_needed = Signal(str, int)  # feed_title, episode_count

    def __init__(self, rss_url):
        super().__init__()
        self.rss_url = rss_url
        self.confirmed = False
        self.should_proceed = True

    def run(self):
        try:
            episodes, feed_title = parse_rss_feed(self.rss_url)
            if not feed_title:
                feed_title = "Unknown Podcast"

            # Check if confirmation needed
            if len(episodes) > 100:
                self.confirm_needed.emit(feed_title, len(episodes))
                # Wait for confirmation
                while not self.confirmed and self.should_proceed:
                    self.msleep(100)
                if not self.should_proceed:
                    return

            # Add to config
            config = load_config()

            # Check if already exists
            for podcast in config.get('podcasts', []):
                if podcast['rss_url'] == self.rss_url:
                    self.error.emit("This podcast is already subscribed")
                    return

            new_podcast = {
                "name": feed_title,
                "rss_url": self.rss_url,
                "date_added": datetime.now().strftime('%Y-%m-%d'),
                "total_episodes": len(episodes),
                "downloaded_count": 0
            }

            config.setdefault('podcasts', []).append(new_podcast)

            # Queue all episodes
            for episode in episodes:
                queue_item = {
                    "podcast_name": feed_title,
                    "episode_title": episode['title'],
                    "episode_url": episode['url'],
                    "published_date": episode['published_date'],
                    "episode_id": episode.get('episode_id', episode['url']),
                    "status": "pending",
                    "retry_count": 0,
                    "date_added_to_queue": datetime.now().isoformat()
                }
                config.setdefault('download_queue', []).append(queue_item)

            save_config(config)
            self.finished.emit(feed_title, len(episodes))

        except Exception as e:
            self.error.emit(str(e))


class DownloadWorker(QThread):
    """Worker thread for processing downloads."""
    finished = Signal(int, int)  # completed, failed
    status_update = Signal(str)
    error = Signal(str)

    def run(self):
        try:
            config = load_config()
            queue = config.get('download_queue', [])
            pending_before = len([q for q in queue if q.get('status') == 'pending'])

            if pending_before == 0:
                # Reset any stuck "downloading" items
                for item in queue:
                    if item.get('status') == 'downloading':
                        item['status'] = 'pending'
                save_config(config)
                pending_before = len([q for q in queue if q.get('status') == 'pending'])

            if pending_before == 0:
                self.finished.emit(0, 0)
                return

            self.status_update.emit("Processing download queue...")
            completed, failed = process_download_queue()
            self.finished.emit(completed, failed)

        except Exception as e:
            self.error.emit(str(e))


class CheckEpisodesWorker(QThread):
    """Worker thread for checking new episodes."""
    finished = Signal(int)  # new_count
    error = Signal(str)

    def __init__(self, podcast_name=None, rss_url=None, check_all=False):
        super().__init__()
        self.podcast_name = podcast_name
        self.rss_url = rss_url
        self.check_all = check_all

    def run(self):
        try:
            if self.check_all:
                config = load_config()
                podcasts = config.get('podcasts', [])
                total_new = 0
                for podcast in podcasts:
                    try:
                        new_count = check_new_episodes(podcast['name'], podcast['rss_url'])
                        total_new += new_count
                    except Exception as e:
                        logger.warning(f"Failed to check {podcast['name']}: {e}")
                config['last_check'] = datetime.now().isoformat()
                save_config(config)
                self.finished.emit(total_new)
            else:
                new_count = check_new_episodes(self.podcast_name, self.rss_url)
                self.finished.emit(new_count)
        except Exception as e:
            self.error.emit(str(e))


class HistoryDialog(QDialog):
    """Dialog showing download history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download History")
        self.resize(800, 600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        config = load_config()
        history = config.get('download_history', {})

        if not history:
            layout.addWidget(QLabel("No download history available yet."))
            return

        tabs = QTabWidget()
        layout.addWidget(tabs)

        for podcast_name, downloads in sorted(history.items()):
            text_widget = QTextEdit()
            text_widget.setReadOnly(True)
            text_widget.setFont(QFont("Monaco", 11))

            content = []
            content.append(f"Download History for: {podcast_name}\n")
            content.append(f"Total Downloads: {len(downloads)}\n")
            content.append("=" * 60 + "\n\n")

            sorted_downloads = sorted(downloads, key=lambda x: x.get('downloaded_at', ''), reverse=True)

            for i, download in enumerate(sorted_downloads, 1):
                downloaded_at = download.get('downloaded_at', 'Unknown')
                try:
                    dt = date_parser.parse(downloaded_at)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse date '{downloaded_at}': {e}")
                    date_str = downloaded_at

                content.append(f"{i}. {download.get('episode_title', 'Unknown')}\n")
                content.append(f"   Published: {download.get('published_date', 'Unknown')}\n")
                content.append(f"   Downloaded: {date_str}\n")
                content.append(f"   File: {download.get('filename', 'Unknown')}\n\n")

            text_widget.setPlainText(''.join(content))
            tabs.addTab(text_widget, f"{podcast_name} ({len(downloads)})")

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class LogViewerDialog(QDialog):
    """Dialog showing system logs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Logs")
        self.resize(1000, 700)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel("Logs are stored in ~/Documents/Katib/logs/")
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info_label)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        logs_dir = Path.home() / "Documents" / "Katib" / "logs"
        today = datetime.now().strftime('%Y-%m-%d')

        # Define log categories
        log_types = [
            ("Download", f"download_{today}.log", "Daily download script logs"),
            ("Watchdog", f"watchdog_{today}.log", "Watchdog monitoring logs"),
            ("Cleanup", f"cleanup_{today}.log", "MP3 cleanup logs"),
            ("Cron Backup", "cron_backup.log", "Cron failsafe logs"),
            ("MacWhisper", f"macwhisper_{today}.log", "MacWhisper opener logs"),
            ("Heartbeats", None, "Task completion timestamps"),
        ]

        for tab_name, filename, description in log_types:
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)

            desc_label = QLabel(description)
            desc_label.setStyleSheet("color: gray; font-size: 11px;")
            tab_layout.addWidget(desc_label)

            text_widget = QTextEdit()
            text_widget.setReadOnly(True)
            text_widget.setFont(QFont("Monaco", 10))

            if tab_name == "Heartbeats":
                # Show heartbeat files
                content = self.get_heartbeat_content(logs_dir)
            else:
                content = self.get_log_content(logs_dir, filename)

            text_widget.setPlainText(content)
            tab_layout.addWidget(text_widget)

            tabs.addTab(tab_widget, tab_name)

        # Button row
        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self.refresh_logs(tabs, logs_dir, today))
        btn_layout.addWidget(refresh_btn)

        open_folder_btn = QPushButton("Open Logs Folder")
        open_folder_btn.clicked.connect(lambda: self.open_logs_folder(logs_dir))
        btn_layout.addWidget(open_folder_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def get_log_content(self, logs_dir, filename):
        """Get content of a log file."""
        if not filename:
            return "No log file specified"

        log_path = logs_dir / filename
        if not log_path.exists():
            # Try to find recent log files with similar pattern
            base_name = filename.rsplit('_', 1)[0] if '_' in filename else filename.replace('.log', '')
            recent_logs = sorted(logs_dir.glob(f"{base_name}*.log"), key=lambda p: p.stat().st_mtime, reverse=True)

            if recent_logs:
                log_path = recent_logs[0]
                header = f"[Showing most recent: {log_path.name}]\n\n"
            else:
                return f"No log file found: {filename}\n\nThis log will be created when the task runs."
        else:
            header = ""

        try:
            content = log_path.read_text()
            if not content.strip():
                return f"{header}Log file is empty."
            # Show last 500 lines max
            lines = content.split('\n')
            if len(lines) > 500:
                content = '\n'.join(lines[-500:])
                header = f"[Showing last 500 lines of {len(lines)} total]\n\n" + header
            return header + content
        except Exception as e:
            return f"Error reading log: {e}"

    def get_heartbeat_content(self, logs_dir):
        """Get content of heartbeat files."""
        heartbeat_files = sorted(logs_dir.glob("heartbeat_*.txt"))

        if not heartbeat_files:
            return "No heartbeat files found.\n\nHeartbeat files are created when tasks complete successfully."

        lines = ["Heartbeat Status (last successful run times):", "=" * 50, ""]

        for hb_file in heartbeat_files:
            task_name = hb_file.stem.replace('heartbeat_', '')
            try:
                timestamp = hb_file.read_text().strip()
                lines.append(f"{task_name.capitalize():15} : {timestamp}")
            except:
                lines.append(f"{task_name.capitalize():15} : Error reading file")

        lines.append("")
        lines.append("=" * 50)
        lines.append("")
        lines.append("Today's date: " + datetime.now().strftime('%Y-%m-%d'))
        lines.append("")

        # Check if tasks ran today
        today = datetime.now().strftime('%Y-%m-%d')
        for hb_file in heartbeat_files:
            task_name = hb_file.stem.replace('heartbeat_', '')
            try:
                timestamp = hb_file.read_text().strip()
                if timestamp.startswith(today):
                    lines.append(f"[OK] {task_name} ran today")
                else:
                    lines.append(f"[!!] {task_name} did NOT run today (last: {timestamp.split()[0]})")
            except:
                lines.append(f"[??] {task_name} status unknown")

        return '\n'.join(lines)

    def refresh_logs(self, tabs, logs_dir, today):
        """Refresh all log tabs."""
        log_types = [
            ("Download", f"download_{today}.log"),
            ("Watchdog", f"watchdog_{today}.log"),
            ("Cleanup", f"cleanup_{today}.log"),
            ("Cron Backup", "cron_backup.log"),
            ("MacWhisper", f"macwhisper_{today}.log"),
            ("Heartbeats", None),
        ]

        for i, (tab_name, filename) in enumerate(log_types):
            tab_widget = tabs.widget(i)
            text_widget = tab_widget.findChild(QTextEdit)
            if text_widget:
                if tab_name == "Heartbeats":
                    content = self.get_heartbeat_content(logs_dir)
                else:
                    content = self.get_log_content(logs_dir, filename)
                text_widget.setPlainText(content)

    def open_logs_folder(self, logs_dir):
        """Open the logs folder in Finder."""
        subprocess.run(['open', str(logs_dir)])


class QueueDetailsDialog(QDialog):
    """Dialog showing queue details."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Queue Details")
        self.resize(900, 600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        config = load_config()
        queue = config.get('download_queue', [])

        if not queue:
            layout.addWidget(QLabel("Download queue is empty."))
            return

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Organize items by status
        by_status = {'pending': [], 'downloading': [], 'failed': []}
        for item in queue:
            status = item.get('status', 'pending')
            if status in by_status:
                by_status[status].append(item)

        for status in ['pending', 'downloading', 'failed']:
            items = by_status.get(status, [])
            if not items:
                continue

            list_widget = QListWidget()
            list_widget.setFont(QFont("Monaco", 10))

            for item in items:
                podcast_name = item.get('podcast_name', 'Unknown')
                episode_title = item.get('episode_title', 'Unknown')
                published_date = item.get('published_date', 'Unknown')
                retry_count = item.get('retry_count', 0)

                if status == 'failed':
                    display = f"{podcast_name} | {episode_title[:60]}... | Retries: {retry_count}"
                else:
                    display = f"{podcast_name} | {published_date} | {episode_title[:60]}..."

                list_widget.addItem(display)

            tabs.addTab(list_widget, f"{status.capitalize()} ({len(items)})")

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class KatibWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Katib - Podcast Downloader")
        self.resize(1200, 800)

        # State
        self.queue_processing = False
        self.config_cache = None
        self.config_mtime = None
        self.podcasts_display_cache = None
        self.add_worker = None
        self.download_worker = None
        self.check_worker = None

        # Setup UI
        self.setup_ui()

        # Initial load
        self.refresh_podcasts(force_reload=True)
        self.cleanup_duplicates(silent=True)
        self.refresh_queue_status(force_reload=True)
        self.refresh_failed_downloads()
        self.refresh_logs()
        self.auto_backfill_history()

        # Setup file watcher for config changes
        self.setup_file_watcher()

        # Setup periodic refresh timer (30 seconds)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.periodic_refresh)
        self.refresh_timer.start(30000)

    def setup_ui(self):
        """Setup the user interface."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Add Podcast Section
        add_group = QGroupBox("Add New Podcast")
        add_layout = QHBoxLayout(add_group)

        add_layout.addWidget(QLabel("RSS Feed URL:"))
        self.rss_input = QLineEdit()
        self.rss_input.setPlaceholderText("Enter podcast RSS feed URL...")
        self.rss_input.returnPressed.connect(self.add_podcast)
        add_layout.addWidget(self.rss_input, 1)

        add_btn = QPushButton("Add Podcast")
        add_btn.clicked.connect(self.add_podcast)
        add_layout.addWidget(add_btn)

        main_layout.addWidget(add_group)

        # Middle section with splitter
        splitter = QSplitter(Qt.Horizontal)

        # Podcasts List Section
        podcasts_group = QGroupBox("Subscribed Podcasts")
        podcasts_layout = QVBoxLayout(podcasts_group)

        self.podcasts_list = QListWidget()
        self.podcasts_list.setFont(QFont(".AppleSystemUIFont", 12))
        podcasts_layout.addWidget(self.podcasts_list)

        podcasts_btn_layout = QHBoxLayout()

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_podcast)
        podcasts_btn_layout.addWidget(remove_btn)

        check_btn = QPushButton("Check for New Episodes")
        check_btn.clicked.connect(self.check_new_episodes_manual)
        podcasts_btn_layout.addWidget(check_btn)

        history_btn = QPushButton("View Download History")
        history_btn.clicked.connect(self.show_download_history)
        podcasts_btn_layout.addWidget(history_btn)

        podcasts_layout.addLayout(podcasts_btn_layout)
        splitter.addWidget(podcasts_group)

        # Queue & Status Section
        status_group = QGroupBox("Download Queue & Status")
        status_layout = QVBoxLayout(status_group)

        self.queue_status = QTextEdit()
        self.queue_status.setReadOnly(True)
        self.queue_status.setFont(QFont("Monaco", 11))
        status_layout.addWidget(self.queue_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)

        action_layout = QHBoxLayout()

        download_btn = QPushButton("Download Now")
        download_btn.clicked.connect(self.download_now)
        action_layout.addWidget(download_btn)

        cleanup_btn = QPushButton("Clean Duplicates")
        cleanup_btn.clicked.connect(self.cleanup_duplicates)
        action_layout.addWidget(cleanup_btn)

        details_btn = QPushButton("View Queue Details")
        details_btn.clicked.connect(self.show_queue_details)
        action_layout.addWidget(details_btn)

        clear_btn = QPushButton("Clear Queue")
        clear_btn.clicked.connect(self.clear_queue)
        action_layout.addWidget(clear_btn)

        cleanup_mp3_btn = QPushButton("Cleanup Old MP3s")
        cleanup_mp3_btn.clicked.connect(self.cleanup_old_mp3s)
        action_layout.addWidget(cleanup_mp3_btn)

        logs_btn = QPushButton("View Logs")
        logs_btn.clicked.connect(self.show_logs)
        action_layout.addWidget(logs_btn)

        status_layout.addLayout(action_layout)
        splitter.addWidget(status_group)

        main_layout.addWidget(splitter, 1)

        # Bottom section with tabs for Failed Downloads and Logs
        bottom_tabs = QTabWidget()

        # Failed Downloads Tab
        failed_widget = QWidget()
        failed_layout = QVBoxLayout(failed_widget)
        failed_layout.setContentsMargins(5, 5, 5, 5)

        self.failed_list = QListWidget()
        self.failed_list.setFont(QFont(".AppleSystemUIFont", 11))
        failed_layout.addWidget(self.failed_list)

        retry_btn = QPushButton("Retry Selected")
        retry_btn.clicked.connect(self.retry_failed)
        failed_layout.addWidget(retry_btn)

        bottom_tabs.addTab(failed_widget, "Failed Downloads")

        # Automation Logs Tab
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        logs_layout.setContentsMargins(5, 5, 5, 5)

        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Monaco", 10))
        self.logs_text.setLineWrapMode(QTextEdit.NoWrap)
        logs_layout.addWidget(self.logs_text)

        logs_btn_layout = QHBoxLayout()
        refresh_logs_btn = QPushButton("Refresh Logs")
        refresh_logs_btn.clicked.connect(self.refresh_logs)
        logs_btn_layout.addWidget(refresh_logs_btn)

        clear_logs_btn = QPushButton("Clear Log File")
        clear_logs_btn.clicked.connect(self.clear_logs)
        logs_btn_layout.addWidget(clear_logs_btn)

        logs_btn_layout.addStretch()
        logs_layout.addLayout(logs_btn_layout)

        bottom_tabs.addTab(logs_widget, "Automation Logs")

        main_layout.addWidget(bottom_tabs)

    def setup_file_watcher(self):
        """Setup file system watcher for config and log changes."""
        self.config_watcher = QFileSystemWatcher()
        if CONFIG_FILE.exists():
            self.config_watcher.addPath(str(CONFIG_FILE))
        if AUTOMATION_LOG.exists():
            self.config_watcher.addPath(str(AUTOMATION_LOG))
        # Watch heartbeat files too
        for hb_file in LOGS_DIR.glob("heartbeat_*.txt"):
            self.config_watcher.addPath(str(hb_file))
        self.config_watcher.fileChanged.connect(self.on_file_changed)

    def on_file_changed(self, path):
        """Handle config or log file changes."""
        # Re-add the path (Qt removes it after change)
        if CONFIG_FILE.exists():
            self.config_watcher.addPath(str(CONFIG_FILE))
        if AUTOMATION_LOG.exists():
            self.config_watcher.addPath(str(AUTOMATION_LOG))
        for hb_file in LOGS_DIR.glob("heartbeat_*.txt"):
            self.config_watcher.addPath(str(hb_file))

        # Check which file changed and refresh accordingly
        if path == str(CONFIG_FILE):
            QTimer.singleShot(100, lambda: self.refresh_all(force_reload=True))
        elif path == str(AUTOMATION_LOG) or "heartbeat_" in path:
            QTimer.singleShot(100, self.refresh_logs)

    def get_config(self, force_reload=False):
        """Get config, only reloading if file has changed or forced."""
        if force_reload:
            self.config_cache = load_config()
            try:
                self.config_mtime = CONFIG_FILE.stat().st_mtime
            except OSError as e:
                logger.debug(f"Could not get config mtime: {e}")
                self.config_mtime = None
            return self.config_cache

        try:
            current_mtime = CONFIG_FILE.stat().st_mtime
            if self.config_mtime is None or current_mtime > self.config_mtime:
                self.config_cache = load_config()
                self.config_mtime = current_mtime
                return self.config_cache
        except OSError as e:
            logger.debug(f"Could not check config mtime: {e}")

        if self.config_cache is None:
            self.config_cache = load_config()
            try:
                self.config_mtime = CONFIG_FILE.stat().st_mtime
            except OSError as e:
                logger.debug(f"Could not get config mtime: {e}")
                self.config_mtime = None

        return self.config_cache

    def refresh_all(self, force_reload=False):
        """Refresh all UI elements."""
        self.refresh_podcasts(force_reload)
        self.refresh_queue_status(force_reload)
        self.refresh_failed_downloads()

    def refresh_podcasts(self, force_reload=False):
        """Refresh the podcasts list."""
        try:
            config = self.get_config(force_reload)
            podcasts = config.get('podcasts', [])

            displays = []
            for podcast in podcasts:
                name = podcast['name']
                total = podcast.get('total_episodes', 0)
                downloaded = podcast.get('downloaded_count', 0)
                displays.append(f"{name} ({downloaded}/{total} downloaded)")

            # Skip if unchanged
            if displays == self.podcasts_display_cache:
                return

            # Preserve selection
            current_row = self.podcasts_list.currentRow()

            # Update list efficiently
            self.podcasts_list.blockSignals(True)
            self.podcasts_list.clear()
            self.podcasts_list.addItems(displays)

            # Restore selection
            if current_row >= 0 and current_row < len(displays):
                self.podcasts_list.setCurrentRow(current_row)

            self.podcasts_list.blockSignals(False)
            self.podcasts_display_cache = displays

        except Exception as e:
            logger.warning(f"Failed to refresh podcasts list: {e}")

    def refresh_queue_status(self, force_reload=False):
        """Refresh the download queue status display."""
        try:
            config = self.get_config(force_reload)
            queue = config.get('download_queue', [])

            status_counts = {'pending': 0, 'downloading': 0, 'failed': 0}
            downloading_items = []
            pending_items = []

            for q in queue:
                status = q.get('status', 'pending')
                if status == 'downloading':
                    status_counts['downloading'] += 1
                    if len(downloading_items) < 3:
                        downloading_items.append(q)
                elif status == 'pending':
                    status_counts['pending'] += 1
                    if len(pending_items) < 10:
                        pending_items.append(q)
                elif status == 'failed':
                    status_counts['failed'] += 1

            lines = []
            lines.append("Current Queue Status:")
            lines.append(f"  Pending: {status_counts['pending']}")
            lines.append(f"  Downloading: {status_counts['downloading']}")
            lines.append(f"  Failed: {status_counts['failed']}")
            lines.append("")

            history = config.get('download_history', {})
            if history:
                lines.append("Download History:")
                for podcast_name, downloads in list(history.items())[:3]:
                    lines.append(f"  {podcast_name}: {len(downloads)} total")
                if len(history) > 3:
                    lines.append(f"  ... and {len(history) - 3} more podcasts")
                lines.append("")

            if downloading_items:
                lines.append("Currently Downloading:")
                for item in downloading_items:
                    title = item['episode_title'][:50]
                    lines.append(f"  * {item['podcast_name']}: {title}...")

            if pending_items:
                lines.append(f"\nNext {len(pending_items)} in Queue:")
                for item in pending_items:
                    title = item['episode_title'][:40]
                    lines.append(f"  * {item['podcast_name']}: {title}...")
                if status_counts['pending'] > len(pending_items):
                    lines.append(f"  ... and {status_counts['pending'] - len(pending_items)} more")
            elif status_counts['pending'] == 0 and status_counts['downloading'] == 0:
                lines.append("\nAll downloads complete!")

            self.queue_status.setPlainText('\n'.join(lines))

        except Exception as e:
            logger.warning(f"Failed to refresh queue status: {e}")

    def refresh_failed_downloads(self):
        """Refresh the failed downloads list."""
        try:
            config = self.get_config(force_reload=False)
            failed = config.get('failed_downloads', [])

            self.failed_list.clear()
            for item in failed[:50]:
                title = item['episode_title'][:50]
                display = f"{item['podcast_name']}: {title}... (Retries: {item.get('retry_count', 0)})"
                self.failed_list.addItem(display)

            if len(failed) > 50:
                self.failed_list.addItem(f"... and {len(failed) - 50} more")

        except Exception as e:
            logger.warning(f"Failed to refresh failed downloads list: {e}")

    def refresh_logs(self):
        """Refresh the automation logs display."""
        try:
            content_parts = []

            # Show heartbeat status at the top
            heartbeat_download = LOGS_DIR / "heartbeat_download.txt"
            heartbeat_macwhisper = LOGS_DIR / "heartbeat_macwhisper.txt"

            content_parts.append("=== Automation Heartbeats ===")
            if heartbeat_download.exists():
                ts = heartbeat_download.read_text().strip()
                content_parts.append(f"Last Download Run: {ts}")
            else:
                content_parts.append("Last Download Run: Never")

            if heartbeat_macwhisper.exists():
                ts = heartbeat_macwhisper.read_text().strip()
                content_parts.append(f"Last MacWhisper Open: {ts}")
            else:
                content_parts.append("Last MacWhisper Open: Never")

            content_parts.append("")
            content_parts.append("=== Automation Logs ===")
            content_parts.append("")

            # Show main automation log
            if AUTOMATION_LOG.exists():
                log_content = AUTOMATION_LOG.read_text(encoding='utf-8', errors='replace')
                # Show last 500 lines to avoid memory issues with large logs
                lines = log_content.splitlines()
                if len(lines) > 500:
                    lines = lines[-500:]
                    content_parts.append("[... showing last 500 lines ...]")
                    content_parts.append("")
                content_parts.extend(lines)
            else:
                content_parts.append("No automation logs found yet.")
                content_parts.append("")
                content_parts.append("Logs will appear here after the daily download runs at 9 AM.")

            self.logs_text.setPlainText('\n'.join(content_parts))
            # Scroll to bottom to show latest logs
            scrollbar = self.logs_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            self.logs_text.setPlainText(f"Error reading logs: {e}")

    def clear_logs(self):
        """Clear the automation log file."""
        if not AUTOMATION_LOG.exists():
            QMessageBox.information(self, "Clear Logs", "No log file to clear.")
            return

        reply = QMessageBox.question(
            self,
            "Clear Logs",
            "Clear all automation logs?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                AUTOMATION_LOG.write_text("")
                self.refresh_logs()
                QMessageBox.information(self, "Logs Cleared", "Automation logs have been cleared.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear logs:\n{e}")

    def add_podcast(self):
        """Add a new podcast subscription."""
        rss_url = self.rss_input.text().strip()

        if not rss_url:
            QMessageBox.warning(self, "Error", "Please enter an RSS feed URL")
            return

        # Validate URL format (moderate validation)
        parsed = urlparse(rss_url)
        if parsed.scheme not in ('http', 'https'):
            QMessageBox.warning(self, "Invalid URL", "URL must start with http:// or https://")
            return
        if not parsed.netloc or '.' not in parsed.netloc:
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid URL with a domain (e.g., https://example.com/feed)")
            return

        self.status_label.setText("Parsing RSS feed...")

        self.add_worker = AddPodcastWorker(rss_url)
        self.add_worker.finished.connect(self.on_add_finished)
        self.add_worker.error.connect(self.on_add_error)
        self.add_worker.confirm_needed.connect(self.on_add_confirm_needed)
        self.add_worker.start()

    def on_add_confirm_needed(self, feed_title, episode_count):
        """Handle confirmation for large podcasts."""
        reply = QMessageBox.question(
            self,
            "Confirm Download",
            f"This podcast has {episode_count} episodes. Download all now?\n\n"
            f"This may take a while and use significant disk space.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.add_worker.confirmed = True
        else:
            self.add_worker.should_proceed = False

    def on_add_finished(self, podcast_name, episode_count):
        """Handle successful podcast addition."""
        self.rss_input.clear()
        self.config_cache = None
        self.config_mtime = None
        self.refresh_all(force_reload=True)
        self.status_label.setText("Ready")
        QMessageBox.information(
            self,
            "Success",
            f"Added '{podcast_name}' with {episode_count} episodes to download queue"
        )

    def on_add_error(self, error_msg):
        """Handle podcast addition error."""
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Error", f"Failed to add podcast:\n{error_msg}")

    def remove_podcast(self):
        """Remove a podcast subscription."""
        current_row = self.podcasts_list.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a podcast to remove")
            return

        config = load_config()
        podcasts = config.get('podcasts', [])

        if current_row >= len(podcasts):
            return

        podcast = podcasts[current_row]

        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove '{podcast['name']}'?\n\nNote: Downloaded files will not be deleted.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            podcasts.pop(current_row)
            queue = config.get('download_queue', [])
            config['download_queue'] = [q for q in queue if q['podcast_name'] != podcast['name']]
            save_config(config)
            self.config_cache = None
            self.config_mtime = None
            self.refresh_all(force_reload=True)

    def check_new_episodes_manual(self):
        """Manually check for new episodes."""
        current_row = self.podcasts_list.currentRow()
        config = load_config()
        podcasts = config.get('podcasts', [])

        if current_row >= 0 and current_row < len(podcasts):
            podcast = podcasts[current_row]
            self.status_label.setText(f"Checking {podcast['name']}...")
            self.check_worker = CheckEpisodesWorker(
                podcast_name=podcast['name'],
                rss_url=podcast['rss_url']
            )
        else:
            self.status_label.setText("Checking all podcasts...")
            self.check_worker = CheckEpisodesWorker(check_all=True)

        self.check_worker.finished.connect(self.on_check_finished)
        self.check_worker.error.connect(self.on_check_error)
        self.check_worker.start()

    def on_check_finished(self, new_count):
        """Handle check completion."""
        self.config_cache = None
        self.config_mtime = None
        self.refresh_all(force_reload=True)
        self.status_label.setText("Ready")
        QMessageBox.information(self, "Check Complete", f"Found {new_count} new episodes")

    def on_check_error(self, error_msg):
        """Handle check error."""
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Error", f"Failed to check for new episodes:\n{error_msg}")

    def download_now(self):
        """Manually trigger download queue processing."""
        if self.queue_processing:
            QMessageBox.information(self, "Info", "Downloads are already in progress")
            return

        self.queue_processing = True
        self.status_label.setText("Processing download queue...")

        self.download_worker = DownloadWorker()
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.status_update.connect(self.on_download_status)
        self.download_worker.error.connect(self.on_download_error)
        self.download_worker.start()

    def on_download_status(self, status):
        """Handle download status update."""
        self.status_label.setText(status)

    def on_download_finished(self, completed, failed):
        """Handle download completion."""
        self.queue_processing = False
        self.config_cache = None
        self.config_mtime = None
        self.refresh_all(force_reload=True)
        self.status_label.setText("Ready")

        if completed > 0 or failed > 0:
            message = f"Downloaded {completed} episode(s)"
            if failed > 0:
                message += f". {failed} failed."
            QMessageBox.information(self, "Download Complete", message)
        else:
            QMessageBox.information(self, "Info", "No downloads to process")

    def on_download_error(self, error_msg):
        """Handle download error."""
        self.queue_processing = False
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Error", f"Download error:\n{error_msg}")

    def retry_failed(self):
        """Retry a failed download."""
        current_row = self.failed_list.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Warning", "Please select a failed download to retry")
            return

        config = load_config()
        failed = config.get('failed_downloads', [])

        if current_row >= len(failed):
            return

        failed_item = failed[current_row]

        queue_item = {
            "podcast_name": failed_item['podcast_name'],
            "episode_title": failed_item['episode_title'],
            "episode_url": failed_item['episode_url'],
            "published_date": failed_item.get('published_date', datetime.now().strftime('%Y-%m-%d')),
            "episode_id": failed_item.get('episode_id', ''),
            "status": "pending",
            "retry_count": 0,
            "date_added_to_queue": datetime.now().isoformat()
        }

        config.setdefault('download_queue', []).append(queue_item)
        failed.pop(current_row)
        save_config(config)

        self.config_cache = None
        self.config_mtime = None
        self.refresh_all(force_reload=True)
        QMessageBox.information(self, "Success", "Failed download moved back to queue")

    def cleanup_duplicates(self, silent=False):
        """Remove duplicate items from download queue that are already downloaded."""
        try:
            removed_count = cleanup_duplicate_queue_items()
            if removed_count > 0:
                self.config_cache = None
                self.config_mtime = None
                self.refresh_all(force_reload=True)
                if not silent:
                    QMessageBox.information(
                        self,
                        "Cleanup Complete",
                        f"Removed {removed_count} duplicate item(s) from download queue"
                    )
            elif not silent:
                QMessageBox.information(self, "Cleanup Complete", "No duplicates found")
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, "Error", f"Failed to cleanup:\n{str(e)}")

    def clear_queue(self):
        """Clear items from the download queue."""
        config = load_config()
        queue = config.get('download_queue', [])

        if not queue:
            QMessageBox.information(self, "Clear Queue", "Download queue is already empty.")
            return

        pending_count = len([q for q in queue if q.get('status') == 'pending'])
        downloading_count = len([q for q in queue if q.get('status') == 'downloading'])

        reply = QMessageBox.question(
            self,
            "Clear Download Queue",
            f"Clear all items from the download queue?\n\n"
            f"Pending: {pending_count}\n"
            f"Downloading: {downloading_count}\n"
            f"Total: {len(queue)}\n\n"
            f"Note: This will not delete downloaded files or history.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            config['download_queue'] = []
            save_config(config)
            self.config_cache = None
            self.config_mtime = None
            self.refresh_all(force_reload=True)
            QMessageBox.information(self, "Queue Cleared", f"Removed {len(queue)} item(s)")

    def cleanup_old_mp3s(self):
        """Clean up old MP3 files that have been transcribed for 14+ days."""
        # Get stats first
        stats = get_cleanup_stats()

        if stats['eligible_count'] == 0:
            QMessageBox.information(
                self,
                "MP3 Cleanup",
                f"No files ready for cleanup.\n\n"
                f"Pending (< 14 days): {stats['pending_count']} files\n"
                f"No transcript yet: {stats['no_transcript_count']} files"
            )
            return

        size_mb = stats['eligible_size_bytes'] / 1024 / 1024

        reply = QMessageBox.question(
            self,
            "Cleanup Old MP3s",
            f"Delete {stats['eligible_count']} MP3 files that have been transcribed for 14+ days?\n\n"
            f"This will free up {size_mb:.1f} MB of disk space.\n\n"
            f"Pending (< 14 days): {stats['pending_count']} files\n"
            f"No transcript yet: {stats['no_transcript_count']} files",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.status_label.setText("Cleaning up old MP3s...")
            deleted, size, errors = cleanup_mp3s(dry_run=False)

            if errors:
                QMessageBox.warning(
                    self,
                    "Cleanup Complete",
                    f"Deleted {deleted} files, freed {size / 1024 / 1024:.1f} MB.\n\n"
                    f"Errors: {len(errors)}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Cleanup Complete",
                    f"Deleted {deleted} files, freed {size / 1024 / 1024:.1f} MB."
                )

            self.status_label.setText("Ready")

    def show_download_history(self):
        """Show download history window."""
        dialog = HistoryDialog(self)
        dialog.exec()

    def show_queue_details(self):
        """Show detailed queue view."""
        dialog = QueueDetailsDialog(self)
        dialog.exec()

    def show_logs(self):
        """Show system logs viewer."""
        dialog = LogViewerDialog(self)
        dialog.exec()

    def auto_backfill_history(self):
        """Automatically backfill history from existing files if history is empty."""
        try:
            config = load_config()
            history = config.get('download_history', {})
            total_history = sum(len(h) for h in history.values())

            podcasts = config.get('podcasts', [])
            if podcasts and total_history == 0:
                podcasts_dir = Path.home() / "Documents" / "Katib" / "podcasts"
                if podcasts_dir.exists():
                    mp3_count = len(list(podcasts_dir.rglob('*.mp3')))
                    if mp3_count > 0:
                        backfill_script = Path(__file__).parent / 'backfill_history.py'
                        # Fire-and-forget: backfill runs in background, UI refreshes via timer
                        # This only runs once when history is empty (first launch or reset)
                        subprocess.Popen(
                            ['python3', str(backfill_script)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        QTimer.singleShot(2000, lambda: self.refresh_queue_status(force_reload=True))
        except Exception as e:
            logger.warning(f"Failed to auto-backfill history: {e}")

    def periodic_refresh(self):
        """Periodic UI refresh."""
        if not self.queue_processing:
            self.refresh_queue_status(force_reload=False)
            self.refresh_podcasts(force_reload=False)


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern cross-platform style

    # macOS specific
    if sys.platform == 'darwin':
        app.setApplicationName("Katib")

    window = KatibWindow()
    window.show()
    window.raise_()
    window.activateWindow()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
