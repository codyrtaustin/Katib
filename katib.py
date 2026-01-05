#!/usr/bin/env python3
"""
Katib - Podcast Downloader GUI Application
Main GUI interface for managing podcast subscriptions and downloads.
"""

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime
import subprocess

# Configuration
BASE_DIR = Path.home() / "Documents" / "Katib"
CONFIG_FILE = BASE_DIR / "config" / "katib_config.json"
PODCASTS_DIR = BASE_DIR / "podcasts"
LOGS_DIR = BASE_DIR / "logs"

# Import downloader functions
sys.path.insert(0, str(Path(__file__).parent))
from katib_downloader import (
    load_config, save_config, check_new_episodes,
    process_download_queue, sanitize_filename, parse_rss_feed,
    cleanup_duplicate_queue_items
)


class KatibGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Katib - Podcast Downloader")
        self.root.geometry("1200x800")
        
        # Variables
        self.rss_url_var = tk.StringVar()
        self.podcast_name_var = tk.StringVar()
        self.downloading = False
        self.queue_processing = False
        self.refresh_scheduled = False  # Prevent multiple refresh calls
        self.config_cache = None  # Cache config to reduce file reads
        self.podcasts_display_cache = None  # Cache podcast display strings to avoid unnecessary updates
        
        # Setup UI
        self.setup_ui()
        
        # Load initial data (force reload on startup to get latest counts)
        self.refresh_podcasts(force_reload=True)
        # Clean up duplicates on startup
        self.cleanup_duplicates(silent=True)
        self.refresh_queue_status(force_reload=True)
        self.refresh_failed_downloads()
        
        # Auto-backfill history if empty but files exist
        self.auto_backfill_history()
        
        # Start periodic refresh
        self.periodic_refresh()
    
    def setup_ui(self):
        """Setup the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Add Podcast Section
        add_frame = ttk.LabelFrame(main_frame, text="Add New Podcast", padding="10")
        add_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(add_frame, text="RSS Feed URL:").grid(row=0, column=0, sticky=tk.W, padx=5)
        rss_entry = ttk.Entry(add_frame, textvariable=self.rss_url_var, width=50)
        rss_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Button(add_frame, text="Add Podcast", command=self.add_podcast).grid(row=0, column=2, padx=5)
        
        add_frame.columnconfigure(1, weight=1)
        
        # Podcasts List Section
        podcasts_frame = ttk.LabelFrame(main_frame, text="Subscribed Podcasts", padding="10")
        podcasts_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=(0, 5))
        
        # Podcasts listbox with scrollbar
        podcasts_scroll = ttk.Scrollbar(podcasts_frame)
        podcasts_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.podcasts_listbox = tk.Listbox(podcasts_frame, yscrollcommand=podcasts_scroll.set, height=15)
        self.podcasts_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        podcasts_scroll.config(command=self.podcasts_listbox.yview)
        
        # Podcasts buttons
        podcasts_btn_frame = ttk.Frame(podcasts_frame)
        podcasts_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(podcasts_btn_frame, text="Remove Selected", command=self.remove_podcast).pack(side=tk.LEFT, padx=2)
        ttk.Button(podcasts_btn_frame, text="Check for New Episodes", command=self.check_new_episodes_manual).pack(side=tk.LEFT, padx=2)
        ttk.Button(podcasts_btn_frame, text="View Download History", command=self.show_download_history).pack(side=tk.LEFT, padx=2)
        
        # Queue & Status Section
        status_frame = ttk.LabelFrame(main_frame, text="Download Queue & Status", padding="10")
        status_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5, padx=(5, 0))
        
        # Queue status
        self.queue_status_text = scrolledtext.ScrolledText(status_frame, height=8, width=40)
        self.queue_status_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(status_frame, text="Ready")
        self.progress_label.pack()
        
        # Action buttons
        action_frame = ttk.Frame(status_frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(action_frame, text="Download Now", command=self.download_now).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Clean Duplicates", command=self.cleanup_duplicates).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="View Queue Details", command=self.show_queue_details).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text="Clear Queue", command=self.clear_queue).pack(side=tk.LEFT, padx=2)
        
        # Failed Downloads Section
        failed_frame = ttk.LabelFrame(main_frame, text="Failed Downloads", padding="10")
        failed_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        failed_scroll = ttk.Scrollbar(failed_frame)
        failed_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.failed_listbox = tk.Listbox(failed_frame, yscrollcommand=failed_scroll.set, height=8)
        self.failed_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        failed_scroll.config(command=self.failed_listbox.yview)
        
        ttk.Button(failed_frame, text="Retry Selected", command=self.retry_failed).pack(pady=5)
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
    
    def refresh_podcasts(self, force_reload=False):
        """Refresh the podcasts list."""
        try:
            # Use cache if available and not forcing reload
            if force_reload or self.config_cache is None:
                config = load_config()
                self.config_cache = config
            else:
                config = self.config_cache
            
            podcasts = config.get('podcasts', [])
            displays = []
            for podcast in podcasts:
                name = podcast['name']
                total = podcast.get('total_episodes', 0)
                downloaded = podcast.get('downloaded_count', 0)
                display = f"{name} ({downloaded}/{total} downloaded)"
                displays.append(display)
            
            # Only update if data actually changed (prevents unnecessary listbox refresh)
            if displays == self.podcasts_display_cache:
                return  # No changes, skip update
            
            # Preserve selection and scroll position
            selection = self.podcasts_listbox.curselection()
            selected_index = selection[0] if selection else None
            scroll_pos = self.podcasts_listbox.yview()
            
            # Batch listbox updates
            self.podcasts_listbox.delete(0, tk.END)
            if displays:
                self.podcasts_listbox.insert(0, *displays)
            
            # Restore selection if it was valid
            if selected_index is not None and selected_index < len(displays):
                self.podcasts_listbox.selection_set(selected_index)
                self.podcasts_listbox.see(selected_index)
            # Restore scroll position
            elif scroll_pos[0] > 0:
                self.podcasts_listbox.yview_moveto(scroll_pos[0])
            
            # Update cache
            self.podcasts_display_cache = displays
        except Exception:
            pass  # Silently fail
    
    def refresh_queue_status(self, force_reload=False):
        """Refresh the download queue status display."""
        try:
            # Use cache if available and not forcing reload
            if force_reload or self.config_cache is None:
                config = load_config()
                self.config_cache = config
            else:
                config = self.config_cache
            
            queue = config.get('download_queue', [])
            
            # Count statuses efficiently - only count what we need
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
                    # Show all pending items (or up to 20 for performance)
                    if len(pending_items) < 20:
                        pending_items.append(q)
                elif status == 'failed':
                    status_counts['failed'] += 1
            
            # Update UI efficiently - batch text operations
            text_content = []
            text_content.append("Current Queue Status:\n")
            text_content.append(f"  Pending: {status_counts['pending']}\n")
            text_content.append(f"  Downloading: {status_counts['downloading']}\n")
            text_content.append(f"  Failed: {status_counts['failed']}\n\n")
            
            # Show download history summary (lightweight - just counts)
            history = config.get('download_history', {})
            if history:
                text_content.append("Download History:\n")
                for podcast_name, downloads in list(history.items())[:5]:
                    text_content.append(f"  {podcast_name}: {len(downloads)} total\n")
                text_content.append("\n")
            
            if downloading_items:
                text_content.append("Currently Downloading:\n")
                for item in downloading_items:
                    text_content.append(f"  • {item['podcast_name']}: {item['episode_title'][:50]}...\n")
            
            if pending_items:
                text_content.append(f"\nNext {len(pending_items)} in Queue:\n")
                for item in pending_items:
                    text_content.append(f"  • {item['podcast_name']}: {item['episode_title'][:40]}...\n")
                if status_counts['pending'] > len(pending_items):
                    text_content.append(f"  ... and {status_counts['pending'] - len(pending_items)} more (click 'View Queue Details' to see all)\n")
            elif status_counts['pending'] == 0 and status_counts['downloading'] == 0:
                text_content.append("\nAll downloads complete!\n")
            
            # Update UI in one operation
            self.queue_status_text.delete(1.0, tk.END)
            self.queue_status_text.insert(tk.END, ''.join(text_content))
            
        except Exception as e:
            # Silently fail to avoid blocking UI
            pass
    
    def refresh_failed_downloads(self):
        """Refresh the failed downloads list."""
        try:
            # Use cache if available
            if self.config_cache:
                config = self.config_cache
            else:
                config = load_config()
                self.config_cache = config
            
            failed = config.get('failed_downloads', [])
            
            # Batch listbox updates
            self.failed_listbox.delete(0, tk.END)
            displays = []
            for item in failed:
                display = f"{item['podcast_name']}: {item['episode_title'][:50]}... (Retries: {item.get('retry_count', 0)})"
                displays.append(display)
            
            # Insert all at once
            if displays:
                self.failed_listbox.insert(0, *displays)
        except Exception:
            pass  # Silently fail
    
    def add_podcast(self):
        """Add a new podcast subscription."""
        rss_url = self.rss_url_var.get().strip()
        
        if not rss_url:
            messagebox.showerror("Error", "Please enter an RSS feed URL")
            return
        
        # Disable button during processing
        self.progress_label.config(text="Parsing RSS feed...")
        
        def add_in_thread():
            try:
                # Parse RSS to get podcast name
                episodes, feed_title = parse_rss_feed(rss_url)
                if not feed_title:
                    feed_title = "Unknown Podcast"
                
                podcast_name = feed_title
                
                # Confirm if many episodes (in main thread)
                if len(episodes) > 100:
                    response = []
                    def show_confirm():
                        response.append(messagebox.askyesno(
                            "Confirm Download",
                            f"This podcast has {len(episodes)} episodes. Download all now?\n\n"
                            f"This may take a while and use significant disk space."
                        ))
                    self.root.after(0, show_confirm)
                    # Wait for response
                    import time
                    while not response:
                        time.sleep(0.1)
                    if not response[0]:
                        self.root.after(0, lambda: self.progress_label.config(text="Ready"))
                        return
                
                # Add to config
                config = load_config()
                
                # Check if already exists
                for podcast in config.get('podcasts', []):
                    if podcast['rss_url'] == rss_url:
                        self.root.after(0, lambda: messagebox.showinfo("Info", "This podcast is already subscribed"))
                        self.root.after(0, lambda: self.progress_label.config(text="Ready"))
                        return
                
                new_podcast = {
                    "name": podcast_name,
                    "rss_url": rss_url,
                    "date_added": datetime.now().strftime('%Y-%m-%d'),
                    "total_episodes": len(episodes),
                    "downloaded_count": 0
                }
                
                config.setdefault('podcasts', []).append(new_podcast)
                save_config(config)
                
                # Queue all episodes
                self.root.after(0, lambda: self.progress_label.config(text=f"Adding {len(episodes)} episodes to queue..."))
                
                for episode in episodes:
                    queue_item = {
                        "podcast_name": podcast_name,
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
                self.config_cache = None  # Invalidate cache
                
                # Update UI in main thread
                self.root.after(0, lambda: self.rss_url_var.set(""))
                self.root.after(0, lambda: self.refresh_podcasts(force_reload=True))
                self.root.after(0, lambda: self.refresh_queue_status(force_reload=True))
                self.root.after(0, lambda: messagebox.showinfo("Success", f"Added '{podcast_name}' with {len(episodes)} episodes to download queue"))
                self.root.after(0, lambda: self.progress_label.config(text="Ready"))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to add podcast:\n{str(e)}"))
                self.root.after(0, lambda: self.progress_label.config(text="Error"))
        
        thread = threading.Thread(target=add_in_thread, daemon=True)
        thread.start()
    
    def remove_podcast(self):
        """Remove a podcast subscription."""
        selection = self.podcasts_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a podcast to remove")
            return
        
        index = selection[0]
        config = load_config()
        podcasts = config.get('podcasts', [])
        
        if index >= len(podcasts):
            return
        
        podcast = podcasts[index]
        response = messagebox.askyesno(
            "Confirm Removal",
            f"Remove '{podcast['name']}'?\n\n"
            f"Note: Downloaded files will not be deleted."
        )
        
        if response:
            # Remove from podcasts list
            podcasts.pop(index)
            
            # Remove from queue (but keep failed downloads for reference)
            queue = config.get('download_queue', [])
            config['download_queue'] = [q for q in queue if q['podcast_name'] != podcast['name']]
            
            save_config(config)
            # Schedule UI updates to avoid blocking
            self.config_cache = None
            self.root.after(50, lambda: self.refresh_podcasts(force_reload=True))
            self.root.after(50, lambda: self.refresh_queue_status(force_reload=True))
    
    def check_new_episodes_manual(self):
        """Manually check for new episodes."""
        selection = self.podcasts_listbox.curselection()
        config = load_config()
        podcasts = config.get('podcasts', [])
        
        if selection:
            index = selection[0]
            if index < len(podcasts):
                podcast = podcasts[index]
                self.progress_label.config(text=f"Checking {podcast['name']}...")
                
                try:
                    new_count = check_new_episodes(podcast['name'], podcast['rss_url'])
                    self.config_cache = None
                    self.root.after(50, lambda: self.refresh_queue_status(force_reload=True))
                    self.root.after(50, lambda: self.refresh_podcasts(force_reload=True))
                    messagebox.showinfo("Check Complete", f"Found {new_count} new episodes")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to check for new episodes:\n{str(e)}")
        else:
            # Check all podcasts
            self.progress_label.config(text="Checking all podcasts...")
            
            total_new = 0
            for podcast in podcasts:
                try:
                    new_count = check_new_episodes(podcast['name'], podcast['rss_url'])
                    total_new += new_count
                except Exception as e:
                    print(f"Error checking {podcast['name']}: {e}")
            
            config['last_check'] = datetime.now().isoformat()
            save_config(config)
            self.config_cache = None
            self.root.after(50, lambda: self.refresh_queue_status(force_reload=True))
            self.root.after(50, lambda: self.refresh_podcasts(force_reload=True))
            messagebox.showinfo("Check Complete", f"Found {total_new} new episodes total")
        
        self.progress_label.config(text="Ready")
    
    def download_now(self):
        """Manually trigger download queue processing."""
        if self.queue_processing:
            messagebox.showinfo("Info", "Downloads are already in progress")
            return
        
        def process_in_thread():
            self.queue_processing = True
            self.root.after(0, lambda: self.progress_label.config(text="Processing download queue..."))
            
            try:
                # Check queue status before processing
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
                    self.root.after(100, lambda: messagebox.showinfo("Info", "No downloads to process"))
                    self.queue_processing = False
                    self.progress_label.config(text="Ready")
                    return
                
                completed, failed = process_download_queue()
                
                # Force immediate UI refresh with fresh data (schedule in main thread)
                self.config_cache = None  # Invalidate cache
                self.root.after(0, lambda: self.refresh_queue_status(force_reload=True))
                self.root.after(0, lambda: self.refresh_podcasts(force_reload=True))
                self.root.after(0, self.refresh_failed_downloads)
                
                if completed > 0 or failed > 0:
                    message = f"Downloaded {completed} episode(s)"
                    if failed > 0:
                        message += f". {failed} failed."
                    self.root.after(100, lambda: messagebox.showinfo("Download Complete", message))
                else:
                    # Check if items are still pending (might be processing)
                    config = load_config()
                    queue = config.get('download_queue', [])
                    pending_after = len([q for q in queue if q.get('status') == 'pending'])
                    downloading_after = len([q for q in queue if q.get('status') == 'downloading'])
                    if pending_after > 0 or downloading_after > 0:
                        self.root.after(100, lambda: messagebox.showinfo("Info", f"Queue status: {pending_after} pending, {downloading_after} downloading. Check status panel for details."))
                    else:
                        self.root.after(100, lambda: messagebox.showinfo("Info", "No downloads to process. All items are complete."))
            except Exception as e:
                import traceback
                error_msg = f"Download error:\n{str(e)}\n\n{traceback.format_exc()}"
                self.root.after(100, lambda: messagebox.showerror("Error", error_msg))
            finally:
                self.queue_processing = False
                self.progress_label.config(text="Ready")
        
        thread = threading.Thread(target=process_in_thread, daemon=True)
        thread.start()
    
    def retry_failed(self):
        """Retry a failed download."""
        selection = self.failed_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a failed download to retry")
            return
        
        index = selection[0]
        config = load_config()
        failed = config.get('failed_downloads', [])
        
        if index >= len(failed):
            return
        
        failed_item = failed[index]
        
        # Move back to queue with reset retry count
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
        failed.pop(index)
        save_config(config)
        
        # Schedule UI updates to avoid blocking (invalidate cache first)
        self.config_cache = None
        self.root.after(50, lambda: self.refresh_queue_status(force_reload=True))
        self.root.after(50, self.refresh_failed_downloads)
        messagebox.showinfo("Success", "Failed download moved back to queue")
    
    def cleanup_duplicates(self, silent=False):
        """Remove duplicate items from download queue that are already downloaded."""
        try:
            removed_count = cleanup_duplicate_queue_items()
            if removed_count > 0:
                self.config_cache = None  # Invalidate cache
                self.refresh_queue_status(force_reload=True)
                if not silent:
                    messagebox.showinfo("Cleanup Complete", f"Removed {removed_count} duplicate item(s) from download queue")
            elif not silent:
                messagebox.showinfo("Cleanup Complete", "No duplicates found in download queue")
        except Exception as e:
            if not silent:
                messagebox.showerror("Error", f"Failed to cleanup duplicates:\n{str(e)}")
    
    def clear_queue(self):
        """Clear items from the download queue."""
        config = load_config()
        queue = config.get('download_queue', [])
        
        if not queue:
            messagebox.showinfo("Clear Queue", "Download queue is already empty.")
            return
        
        # Count items by status
        pending_count = len([q for q in queue if q.get('status') == 'pending'])
        downloading_count = len([q for q in queue if q.get('status') == 'downloading'])
        failed_count = len([q for q in queue if q.get('status') == 'failed'])
        
        # Build confirmation message
        status_parts = []
        if pending_count > 0:
            status_parts.append(f"{pending_count} pending")
        if downloading_count > 0:
            status_parts.append(f"{downloading_count} downloading")
        if failed_count > 0:
            status_parts.append(f"{failed_count} failed")
        
        status_msg = ", ".join(status_parts) if status_parts else "0 items"
        
        response = messagebox.askyesno(
            "Clear Download Queue",
            f"Clear all items from the download queue?\n\n"
            f"Current queue: {status_msg}\n"
            f"Total items: {len(queue)}\n\n"
            f"Note: This will not delete downloaded files or history."
        )
        
        if response:
            # Clear the queue
            config['download_queue'] = []
            save_config(config)
            self.config_cache = None  # Invalidate cache
            self.refresh_queue_status(force_reload=True)
            messagebox.showinfo("Queue Cleared", f"Removed {len(queue)} item(s) from download queue.")
    
    def auto_backfill_history(self):
        """Automatically backfill history from existing files if history is empty."""
        try:
            config = load_config()
            history = config.get('download_history', {})
            total_history = sum(len(h) for h in history.values())
            
            # Check if we have podcasts but no history
            podcasts = config.get('podcasts', [])
            if podcasts and total_history == 0:
                # Check if files exist
                from pathlib import Path
                podcasts_dir = Path.home() / "Documents" / "Katib" / "podcasts"
                if podcasts_dir.exists():
                    mp3_count = len(list(podcasts_dir.rglob('*.mp3')))
                    if mp3_count > 0:
                        # Run backfill in background
                        import subprocess
                        import threading
                        def run_backfill():
                            subprocess.run(['python3', str(Path(__file__).parent / 'backfill_history.py')], 
                                         capture_output=True)
                            # Refresh after backfill
                            self.root.after(1000, self.refresh_queue_status)
                        thread = threading.Thread(target=run_backfill, daemon=True)
                        thread.start()
        except Exception as e:
            # Silently fail - not critical
            pass
    
    def show_download_history(self):
        """Show download history window for all podcasts."""
        config = load_config()
        history = config.get('download_history', {})
        
        if not history:
            messagebox.showinfo("Download History", "No download history available yet.")
            return
        
        # Create history window
        history_window = tk.Toplevel(self.root)
        history_window.title("Download History")
        history_window.geometry("800x600")
        
        # Create notebook for tabs per podcast
        notebook = ttk.Notebook(history_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for podcast_name, downloads in sorted(history.items()):
            # Create frame for this podcast
            podcast_frame = ttk.Frame(notebook)
            notebook.add(podcast_frame, text=f"{podcast_name} ({len(downloads)})")
            
            # Create scrollable text widget
            scroll = ttk.Scrollbar(podcast_frame)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            
            history_text = scrolledtext.ScrolledText(podcast_frame, yscrollcommand=scroll.set, wrap=tk.WORD)
            history_text.pack(fill=tk.BOTH, expand=True)
            scroll.config(command=history_text.yview)
            
            # Sort by download date (newest first)
            sorted_downloads = sorted(downloads, key=lambda x: x.get('downloaded_at', ''), reverse=True)
            
            history_text.insert(tk.END, f"Download History for: {podcast_name}\n")
            history_text.insert(tk.END, f"Total Downloads: {len(downloads)}\n")
            history_text.insert(tk.END, "=" * 80 + "\n\n")
            
            for i, download in enumerate(sorted_downloads, 1):
                downloaded_at = download.get('downloaded_at', 'Unknown')
                try:
                    from dateutil import parser as date_parser
                    dt = date_parser.parse(downloaded_at)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = downloaded_at
                
                history_text.insert(tk.END, f"{i}. {download.get('episode_title', 'Unknown')}\n")
                history_text.insert(tk.END, f"   Published: {download.get('published_date', 'Unknown')}\n")
                history_text.insert(tk.END, f"   Downloaded: {date_str}\n")
                history_text.insert(tk.END, f"   File: {download.get('filename', 'Unknown')}\n")
                history_text.insert(tk.END, "\n")
            
            history_text.config(state=tk.DISABLED)  # Make read-only
        
        # Close button
        close_btn = ttk.Button(history_window, text="Close", command=history_window.destroy)
        close_btn.pack(pady=5)
    
    def show_queue_details(self):
        """Show detailed view of all items in the download queue."""
        config = load_config()
        queue = config.get('download_queue', [])
        
        if not queue:
            messagebox.showinfo("Queue Details", "Download queue is empty.")
            return
        
        # Create queue details window
        queue_window = tk.Toplevel(self.root)
        queue_window.title("Download Queue Details")
        queue_window.geometry("900x600")
        
        # Create notebook for tabs by status
        notebook = ttk.Notebook(queue_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Organize items by status
        by_status = {'pending': [], 'downloading': [], 'failed': [], 'completed': []}
        for item in queue:
            status = item.get('status', 'pending')
            by_status.setdefault(status, []).append(item)
        
        # Create tab for each status that has items
        for status in ['pending', 'downloading', 'failed']:
            items = by_status.get(status, [])
            if not items:
                continue
            
            # Create frame for this status
            status_frame = ttk.Frame(notebook)
            notebook.add(status_frame, text=f"{status.capitalize()} ({len(items)})")
            
            # Create scrollable listbox
            scroll = ttk.Scrollbar(status_frame)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)
            
            listbox = tk.Listbox(status_frame, yscrollcommand=scroll.set, font=('Courier', 10))
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scroll.config(command=listbox.yview)
            
            # Add items to listbox
            for item in items:
                podcast_name = item.get('podcast_name', 'Unknown')
                episode_title = item.get('episode_title', 'Unknown')
                published_date = item.get('published_date', 'Unknown')
                retry_count = item.get('retry_count', 0)
                
                # Format display
                if status == 'failed':
                    display = f"{podcast_name} | {episode_title[:60]}... | Retries: {retry_count}"
                else:
                    display = f"{podcast_name} | {published_date} | {episode_title[:60]}..."
                
                listbox.insert(tk.END, display)
        
        # Close button
        close_btn = ttk.Button(queue_window, text="Close", command=queue_window.destroy)
        close_btn.pack(pady=5)
    
    def periodic_refresh(self):
        """Periodically refresh the UI."""
        # Only refresh if not already scheduled and not processing
        if not self.refresh_scheduled and not self.queue_processing:
            self.refresh_scheduled = True
            # Use a longer delay and don't force reload (use cache)
            self.root.after(30000, lambda: self._do_periodic_refresh())  # Refresh every 30 seconds
    
    def _do_periodic_refresh(self):
        """Actually perform the periodic refresh."""
        self.refresh_scheduled = False
        if not self.queue_processing:
            self.refresh_queue_status(force_reload=False)  # Use cache
            self.refresh_podcasts(force_reload=False)  # Use cache for periodic refresh
        self.periodic_refresh()  # Schedule next refresh


def main():
    """Main entry point."""
    try:
        root = tk.Tk()
        
        # macOS-specific: Ensure window is visible
        if sys.platform == 'darwin':
            # Force window to be created and visible
            root.withdraw()  # Hide temporarily
            root.update_idletasks()
            root.deiconify()  # Show it
            root.lift()  # Bring to front
            root.focus_force()  # Force focus
            root.attributes('-topmost', True)
            root.after_idle(lambda: root.attributes('-topmost', False))
            root.update()
        
        app = KatibGUI(root)
        
        # macOS-specific: Final window setup
        if sys.platform == 'darwin':
            root.deiconify()
            root.lift()
            root.focus_force()
            root.update_idletasks()
        
        root.mainloop()
    except Exception as e:
        # Log error and show dialog
        error_msg = f"Error launching Katib: {str(e)}"
        print(error_msg, file=sys.stderr)
        
        # Try to show error dialog on macOS
        if sys.platform == 'darwin':
            try:
                import subprocess
                subprocess.run([
                    'osascript', '-e',
                    f'display dialog "{error_msg}" buttons {{"OK"}} default button "OK" with icon stop'
                ])
            except:
                pass
        
        raise


if __name__ == '__main__':
    main()
