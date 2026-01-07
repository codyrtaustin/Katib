#!/usr/bin/env python3
"""
Katib Download Worker
Handles RSS feed checking, download queue processing, and file downloads.
Can run independently of the GUI for automation.
"""

import json
import os
import sys
import time
import logging
import requests
import feedparser
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import argparse

# Configuration
BASE_DIR = Path.home() / "Documents" / "Katib"
CONFIG_FILE = BASE_DIR / "config" / "katib_config.json"
PODCASTS_DIR = BASE_DIR / "podcasts"
LOGS_DIR = BASE_DIR / "logs"
MAX_RETRIES = 5
CHUNK_SIZE = 8192  # 8KB chunks for streaming

# Setup logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOGS_DIR / f"katib_downloader_{datetime.now().strftime('%Y-%m-%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def sanitize_filename(name, max_length=200):
    """Remove special characters and limit filename length."""
    # Remove or replace problematic characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '')
    # Remove leading/trailing spaces and dots
    name = name.strip(' .')
    # Limit length
    if len(name) > max_length:
        name = name[:max_length]
    return name


def create_safe_filepath(podcast_name, episode_title, published_date, base_dir=PODCASTS_DIR):
    """Create a safe filepath that fits within filesystem limits.
    
    On macOS: max path length is 1024 chars, max filename is 255 chars.
    We'll ensure the full path stays under 1024 chars and filename under 255.
    """
    # Sanitize podcast name (directory name)
    safe_podcast = sanitize_filename(podcast_name, max_length=100)
    podcast_dir = base_dir / safe_podcast
    
    # Calculate available space for filename
    # Format: "{podcast} - {date} - {title}.mp3"
    # Reserve space for: " - " (3) + date (10) + " - " (3) + ".mp3" (4) = 20 chars
    date_part = published_date  # YYYY-MM-DD = 10 chars
    prefix = f"{safe_podcast} - {date_part} - "
    suffix = ".mp3"
    
    # Calculate max filename length (255 chars for filename, but we need to account for full path)
    # Full path = base_dir + "/" + safe_podcast + "/" + filename
    base_path_len = len(str(podcast_dir)) + 1  # +1 for the "/" separator
    max_path_len = 1024  # macOS max path length
    max_filename_len = min(255, max_path_len - base_path_len - 1)  # -1 for safety
    
    # Calculate available space for title
    available_for_title = max_filename_len - len(prefix) - len(suffix)
    
    # Ensure we have at least some space for title (minimum 20 chars)
    if available_for_title < 20:
        # If path is too long, truncate podcast name more aggressively
        safe_podcast = sanitize_filename(podcast_name, max_length=50)
        podcast_dir = base_dir / safe_podcast
        prefix = f"{safe_podcast} - {date_part} - "
        base_path_len = len(str(podcast_dir)) + 1
        available_for_title = min(255, max_path_len - base_path_len - 1) - len(prefix) - len(suffix)
    
    # Sanitize and truncate title to fit
    safe_title = sanitize_filename(episode_title, max_length=max(20, available_for_title))
    
    # Build filename
    filename = f"{safe_podcast} - {date_part} - {safe_title}.mp3"
    
    # Final safety check - truncate if still too long
    if len(filename) > 255:
        # Truncate title more aggressively
        excess = len(filename) - 255
        safe_title = safe_title[:len(safe_title) - excess - 3] + "..."
        filename = f"{safe_podcast} - {date_part} - {safe_title}.mp3"
    
    filepath = podcast_dir / filename
    
    # Final path length check
    full_path = str(filepath)
    if len(full_path) > 1024:
        # Emergency truncation - use a hash for very long paths
        import hashlib
        title_hash = hashlib.md5(episode_title.encode()).hexdigest()[:8]
        safe_title = f"{safe_title[:50]}...{title_hash}" if len(safe_title) > 50 else safe_title
        filename = f"{safe_podcast} - {date_part} - {safe_title}.mp3"
        filepath = podcast_dir / filename
    
    return filepath, filename


def load_config():
    """Load configuration from JSON file."""
    if not CONFIG_FILE.exists():
        return {
            "podcasts": [],
            "download_queue": [],
            "failed_downloads": [],
            "download_history": {},  # Track downloads per podcast: {podcast_name: [list of downloads]}
            "last_check": None
        }
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Ensure download_history exists
            if 'download_history' not in config:
                config['download_history'] = {}
            return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {
            "podcasts": [],
            "download_queue": [],
            "failed_downloads": [],
            "download_history": {},
            "last_check": None
        }


def save_config(config):
    """Save configuration to JSON file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False


def parse_rss_feed(rss_url):
    """Parse RSS feed and return list of episodes."""
    try:
        feed = feedparser.parse(rss_url)
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"RSS feed parsing warning: {feed.bozo_exception}")
        
        episodes = []
        for entry in feed.entries:
            # Find audio enclosure - prioritize enclosures as they contain direct audio URLs
            audio_url = None
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enc in entry.enclosures:
                    enc_type = enc.get('type', '')
                    enc_href = enc.get('href', '')
                    # Check if it's an audio type
                    if enc_type.startswith('audio/'):
                        audio_url = enc_href
                        break
                    # Also check if href looks like an audio file (common extensions)
                    if any(enc_href.lower().endswith(ext) for ext in ['.mp3', '.m4a', '.mp4', '.ogg', '.wav']):
                        audio_url = enc_href
                        break
            
            # Try alternative methods to find audio URL
            if not audio_url:
                if hasattr(entry, 'links') and entry.links:
                    for link in entry.links:
                        link_type = link.get('type', '')
                        link_href = link.get('href', '')
                        if link_type.startswith('audio/'):
                            audio_url = link_href
                            break
                        # Check if href looks like an audio file
                        if any(link_href.lower().endswith(ext) for ext in ['.mp3', '.m4a', '.mp4', '.ogg', '.wav']):
                            audio_url = link_href
                            break
            
            # For Buzzsprout specifically, check if we have a media_content or media_thumbnail
            if not audio_url:
                # Check media_content (used by some feeds)
                if hasattr(entry, 'media_content'):
                    for media in entry.media_content:
                        if media.get('type', '').startswith('audio/'):
                            audio_url = media.get('url', '')
                            break
            
            # Last resort: check if entry has a direct audio link in summary/description
            if not audio_url:
                # Some feeds put audio URLs in the content/summary
                content = getattr(entry, 'content', [{}])[0].get('value', '') if hasattr(entry, 'content') else ''
                summary = getattr(entry, 'summary', '')
                import re
                # Look for audio file URLs in content
                for text in [content, summary]:
                    if text:
                        # Match URLs ending in audio extensions
                        matches = re.findall(r'https?://[^\s<>"]+\.(?:mp3|m4a|mp4|ogg|wav)', text, re.IGNORECASE)
                        if matches:
                            audio_url = matches[0]
                            break
            
            if not audio_url:
                logger.warning(f"No audio URL found for episode: {entry.get('title', 'Unknown')}")
                continue
            
            # Parse published date
            published_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    published_date = datetime(*entry.published_parsed[:6]).strftime('%Y-%m-%d')
                except:
                    pass
            
            if not published_date and hasattr(entry, 'published'):
                try:
                    # Try parsing the published string
                    from dateutil import parser as date_parser
                    dt = date_parser.parse(entry.published)
                    published_date = dt.strftime('%Y-%m-%d')
                except:
                    published_date = datetime.now().strftime('%Y-%m-%d')
            
            if not published_date:
                published_date = datetime.now().strftime('%Y-%m-%d')
            
            # Get episode title
            title = entry.get('title', 'Untitled Episode')
            
            # Get unique identifier
            episode_id = entry.get('id', entry.get('link', audio_url))
            
            episodes.append({
                'title': title,
                'url': audio_url,
                'published_date': published_date,
                'episode_id': episode_id,
                'description': entry.get('summary', '')
            })
        
        return episodes, feed.feed.get('title', 'Unknown Podcast')
    except Exception as e:
        logger.error(f"Error parsing RSS feed {rss_url}: {e}")
        return [], None


def check_disk_space(required_bytes):
    """Check if there's enough disk space."""
    try:
        stat = os.statvfs(BASE_DIR)
        free_bytes = stat.f_bavail * stat.f_frsize
        return free_bytes >= required_bytes
    except:
        return True  # Assume OK if we can't check


def download_file(url, filepath, progress_callback=None):
    """Download a file with progress tracking and resume support."""
    try:
        # Set up headers to avoid 403 errors (especially for Buzzsprout)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': url if 'buzzsprout.com' in url else None
        }
        # Remove None values
        headers = {k: v for k, v in headers.items() if v is not None}
        
        # Check if file already exists and is complete
        try:
            if filepath.exists():
                # Try to get file size from server
                head_response = requests.head(url, headers=headers, allow_redirects=True, timeout=10)
                if head_response.status_code == 200:
                    content_length = head_response.headers.get('content-length')
                    if content_length:
                        existing_size = filepath.stat().st_size
                        if existing_size == int(content_length):
                            logger.info(f"File already exists and is complete: {filepath.name}")
                            return True
        except OSError as e:
            if "File name too long" in str(e) or e.errno == 63:
                # Path is too long, can't check if exists, proceed with download
                logger.warning(f"Path too long to check existence, proceeding with download: {e}")
            else:
                raise
        
        # Start download
        response = requests.get(url, headers=headers, stream=True, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        # Check disk space
        if total_size > 0 and not check_disk_space(total_size * 1.1):  # 10% buffer
            raise Exception("Insufficient disk space")
        
        # Create directory if needed
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Download with progress
        downloaded = 0
        mode = 'wb'
        if filepath.exists():
            # Try to resume
            downloaded = filepath.stat().st_size
            if total_size > 0 and downloaded < total_size:
                resume_headers = headers.copy()
                resume_headers['Range'] = f'bytes={downloaded}-'
                response = requests.get(url, headers=resume_headers, stream=True, timeout=30, allow_redirects=True)
                response.raise_for_status()
                mode = 'ab'
                logger.info(f"Resuming download from byte {downloaded}")
        
        with open(filepath, mode) as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded, total_size)
        
        # Verify file size if we know the expected size
        if total_size > 0:
            actual_size = filepath.stat().st_size
            if actual_size != total_size:
                logger.warning(f"File size mismatch: expected {total_size}, got {actual_size}")
                # Don't fail, might be OK
        
        logger.info(f"Downloaded: {filepath.name} ({downloaded} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"Download error for {url}: {e}")
        if filepath.exists():
            # Remove incomplete file
            try:
                filepath.unlink()
            except:
                pass
        raise


def check_new_episodes(podcast_name, rss_url):
    """Check RSS feed for new episodes and add to queue."""
    logger.info(f"Checking for new episodes: {podcast_name}")
    episodes, feed_title = parse_rss_feed(rss_url)
    
    if not episodes:
        logger.warning(f"No episodes found in feed: {rss_url}")
        return 0
    
    config = load_config()
    
    # Get existing episode IDs for this podcast
    existing_ids = set()
    existing_urls = set()
    existing_titles = set()
    
    # Check download queue
    for item in config.get('download_queue', []):
        if item.get('podcast_name') == podcast_name:
            existing_ids.add(item.get('episode_id', ''))
            existing_urls.add(item.get('episode_url', ''))
            existing_titles.add(item.get('episode_title', ''))
    
    # Check failed downloads
    for item in config.get('failed_downloads', []):
        if item.get('podcast_name') == podcast_name:
            existing_ids.add(item.get('episode_id', ''))
            existing_urls.add(item.get('episode_url', ''))
            existing_titles.add(item.get('episode_title', ''))
    
    # Check download history (this is the key fix - previously missing!)
    history = config.get('download_history', {}).get(podcast_name, [])
    for entry in history:
        existing_ids.add(entry.get('episode_id', ''))
        existing_urls.add(entry.get('episode_url', ''))
        existing_titles.add(entry.get('episode_title', ''))
    
    # Check if episodes are already downloaded (by checking if expected file exists)
    podcast_dir = PODCASTS_DIR / sanitize_filename(podcast_name)
    existing_files = set()
    if podcast_dir.exists():
        for file in podcast_dir.glob('*.mp3'):
            existing_files.add(file.name.lower())  # Store lowercase for case-insensitive comparison
    
    # Add new episodes to queue
    new_count = 0
    for episode in episodes:
        episode_id = episode.get('episode_id', episode.get('url', ''))
        episode_url = episode.get('url', '')
        episode_title = episode.get('title', '')
        
        # Check if file already exists by trying to create the expected filepath
        file_exists = False
        try:
            filepath, filename = create_safe_filepath(podcast_name, episode_title, episode['published_date'])
            if filepath.exists() or filename.lower() in existing_files:
                file_exists = True
        except Exception as e:
            # If we can't create the filepath, check by title match in existing files
            safe_title = sanitize_filename(episode_title, max_length=100)
            for existing_file in existing_files:
                if safe_title.lower() in existing_file.lower():
                    file_exists = True
                    break
        
        # Check if already exists by ID, URL, title, or file existence
        if (episode_id not in existing_ids and 
            episode_url not in existing_urls and 
            episode_title not in existing_titles and
            not file_exists):
            queue_item = {
                "podcast_name": podcast_name,
                "episode_title": episode['title'],
                "episode_url": episode['url'],
                "published_date": episode['published_date'],
                "episode_id": episode_id,
                "status": "pending",
                "retry_count": 0,
                "date_added_to_queue": datetime.now().isoformat()
            }
            config.setdefault('download_queue', []).append(queue_item)
            new_count += 1
    
    save_config(config)
    logger.info(f"Added {new_count} new episodes to queue for {podcast_name}")
    return new_count


def cleanup_duplicate_queue_items():
    """Remove items from download queue that are already in download_history."""
    config = load_config()
    queue = config.get('download_queue', [])
    history = config.get('download_history', {})
    
    if not queue:
        return 0
    
    # Build sets of already-downloaded episodes per podcast
    downloaded_by_podcast = {}
    for podcast_name, downloads in history.items():
        downloaded_by_podcast[podcast_name] = {
            'ids': set(),
            'urls': set(),
            'titles': set()
        }
        for entry in downloads:
            downloaded_by_podcast[podcast_name]['ids'].add(entry.get('episode_id', ''))
            downloaded_by_podcast[podcast_name]['urls'].add(entry.get('episode_url', ''))
            downloaded_by_podcast[podcast_name]['titles'].add(entry.get('episode_title', ''))
    
    # Remove duplicates from queue
    removed_count = 0
    items_to_remove = []
    
    for item in queue:
        podcast_name = item.get('podcast_name', '')
        if podcast_name in downloaded_by_podcast:
            episode_id = item.get('episode_id', '')
            episode_url = item.get('episode_url', '')
            episode_title = item.get('episode_title', '')
            
            downloaded = downloaded_by_podcast[podcast_name]
            # Check if already downloaded by ID, URL, or title
            if (episode_id in downloaded['ids'] or 
                episode_url in downloaded['urls'] or 
                episode_title in downloaded['titles']):
                items_to_remove.append(item)
                removed_count += 1
    
    # Remove duplicates
    for item in items_to_remove:
        if item in config['download_queue']:
            config['download_queue'].remove(item)
    
    if removed_count > 0:
        save_config(config)
        logger.info(f"Removed {removed_count} duplicate items from download queue")
    
    return removed_count


def process_download_queue():
    """Process the download queue sequentially."""
    config = load_config()
    queue = config.get('download_queue', [])
    
    if not queue:
        logger.info("Download queue is empty")
        return 0, 0
    
    completed = 0
    failed = 0
    
    # Process pending items
    for item in queue[:]:  # Copy list to iterate safely
        if item['status'] == 'completed':
            continue
        
        if item['status'] == 'downloading':
            # Reset stuck downloads
            item['status'] = 'pending'
        
        if item['status'] != 'pending':
            continue
        
        podcast_name = item['podcast_name']
        episode_title = item['episode_title']
        episode_url = item['episode_url']
        published_date = item['published_date']
        
        # Create safe filepath that fits within filesystem limits
        try:
            filepath, filename = create_safe_filepath(podcast_name, episode_title, published_date)
        except Exception as e:
            logger.error(f"Error creating safe filepath: {e}")
            # Fallback to old method with aggressive truncation
            safe_podcast = sanitize_filename(podcast_name, max_length=50)
            safe_title = sanitize_filename(episode_title, max_length=100)
            filename = f"{safe_podcast} - {published_date} - {safe_title}.mp3"
            filepath = PODCASTS_DIR / safe_podcast / filename
        
        # Skip if already exists (use try/except to handle path length errors)
        try:
            if filepath.exists():
                logger.info(f"File already exists, marking as completed: {filename}")
                item['status'] = 'completed'
                save_config(config)
                completed += 1
                continue
        except OSError as e:
            if "File name too long" in str(e) or e.errno == 63:
                # Path is too long, need to use shorter filename
                logger.warning(f"Path too long, using shorter filename: {e}")
                # Use hash-based filename as fallback
                import hashlib
                title_hash = hashlib.md5(episode_title.encode()).hexdigest()[:12]
                safe_podcast = sanitize_filename(podcast_name, max_length=50)
                filename = f"{safe_podcast} - {published_date} - {title_hash}.mp3"
                filepath = PODCASTS_DIR / safe_podcast / filename
            else:
                raise
        
        # Mark as downloading
        item['status'] = 'downloading'
        save_config(config)
        
        # Attempt download
        try:
            download_file(episode_url, filepath)
            item['status'] = 'completed'
            completed += 1
            
            # Record in download history
            if podcast_name not in config.get('download_history', {}):
                config['download_history'][podcast_name] = []
            
            history_entry = {
                "episode_title": episode_title,
                "episode_url": episode_url,
                "episode_id": item.get('episode_id', ''),
                "published_date": published_date,
                "downloaded_at": datetime.now().isoformat(),
                "filename": filename
            }
            config['download_history'][podcast_name].append(history_entry)
            
            # Update podcast stats
            for podcast in config.get('podcasts', []):
                if podcast['name'] == podcast_name:
                    podcast['downloaded_count'] = podcast.get('downloaded_count', 0) + 1
                    break
            
            logger.info(f"Successfully downloaded: {filename}")
            
        except Exception as e:
            error_msg = str(e)
            item['retry_count'] = item.get('retry_count', 0) + 1
            
            if item['retry_count'] >= MAX_RETRIES:
                # Move to failed downloads
                item['status'] = 'failed'
                failed_item = {
                    "podcast_name": podcast_name,
                    "episode_title": episode_title,
                    "episode_url": episode_url,
                    "published_date": published_date,
                    "episode_id": item.get('episode_id', ''),
                    "retry_count": item['retry_count'],
                    "last_error": error_msg,
                    "last_attempt": datetime.now().isoformat()
                }
                config.setdefault('failed_downloads', []).append(failed_item)
                config['download_queue'].remove(item)
                failed += 1
                logger.error(f"Failed after {MAX_RETRIES} retries: {filename}")
            else:
                item['status'] = 'pending'
                logger.warning(f"Download failed (attempt {item['retry_count']}/{MAX_RETRIES}): {filename}")
            
        finally:
            save_config(config)
            # Small delay between downloads
            time.sleep(1)
    
    # Clean up completed items from queue (keep only pending/downloading/failed)
    # This keeps the queue clean and shows only active items
    config = load_config()
    queue = config.get('download_queue', [])
    original_count = len(queue)
    config['download_queue'] = [q for q in queue if q.get('status') not in ['completed']]
    if len(config['download_queue']) < original_count:
        save_config(config)
        logger.info(f"Cleaned {original_count - len(config['download_queue'])} completed items from queue")
    
    return completed, failed


def send_notification(title, message):
    """Send macOS notification."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        os.system(f'osascript -e \'{script}\'')
    except Exception as e:
        logger.warning(f"Could not send notification: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Katib Download Worker')
    parser.add_argument('--check-new', action='store_true', help='Check all RSS feeds for new episodes')
    parser.add_argument('--process-queue', action='store_true', help='Process download queue')
    parser.add_argument('--all', action='store_true', help='Check new and process queue')
    
    args = parser.parse_args()
    
    if not args.check_new and not args.process_queue and not args.all:
        args.all = True  # Default behavior
    
    config = load_config()
    
    if args.check_new or args.all:
        logger.info("Checking RSS feeds for new episodes...")
        total_new = 0
        for podcast in config.get('podcasts', []):
            try:
                new_count = check_new_episodes(podcast['name'], podcast['rss_url'])
                total_new += new_count
            except Exception as e:
                logger.error(f"Error checking {podcast['name']}: {e}")
        
        config['last_check'] = datetime.now().isoformat()
        save_config(config)
        
        if total_new > 0:
            podcast_count = len([p for p in config.get('podcasts', []) if p])
            send_notification(
                "Katib",
                f"Found {total_new} new episodes from {podcast_count} podcast(s)"
            )
        else:
            send_notification("Katib", "No new episodes found")
    
    if args.process_queue or args.all:
        logger.info("Processing download queue...")
        completed, failed = process_download_queue()
        
        if completed > 0 or failed > 0:
            if failed > 0:
                message = f"Downloaded {completed} episode(s). {failed} failed (check app for details)"
            else:
                message = f"Downloaded {completed} new episode(s)"
            send_notification("Katib", message)
        else:
            logger.info("No downloads processed")


if __name__ == '__main__':
    main()
