#!/usr/bin/env python3
"""
Backfill download history from existing downloaded files.
This script scans the podcasts directory and creates history entries for existing files.
"""

import json
import logging
import re
import sys
from pathlib import Path
from datetime import datetime

# Import from katib_downloader
sys.path.insert(0, str(Path(__file__).parent))
from katib_downloader import load_config, save_config, BASE_DIR, PODCASTS_DIR, CONFIG_FILE, LOGS_DIR

# Setup logging
logger = logging.getLogger(__name__)

def extract_episode_info(filename):
    """Extract podcast name, date, and title from filename.
    Format: [Podcast Name] - YYYY-MM-DD - [Episode Title].mp3
    """
    # Remove .mp3 extension
    name = filename.replace('.mp3', '')
    
    # Try to match the pattern: Podcast Name - YYYY-MM-DD - Episode Title
    pattern = r'^(.+?)\s+-\s+(\d{4}-\d{2}-\d{2})\s+-\s+(.+)$'
    match = re.match(pattern, name)
    
    if match:
        podcast_name = match.group(1).strip()
        published_date = match.group(2).strip()
        episode_title = match.group(3).strip()
        return podcast_name, published_date, episode_title
    
    # Fallback: try to extract date
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', name)
    if date_match:
        published_date = date_match.group(1)
        # Try to split on the date
        parts = name.split(published_date)
        if len(parts) >= 2:
            podcast_name = parts[0].strip(' -')
            episode_title = parts[1].strip(' -')
            return podcast_name, published_date, episode_title
    
    # Last resort: use directory name as podcast, filename as title
    return None, None, None

def backfill_history():
    """Scan podcasts directory and create history entries."""
    print("Scanning for existing downloads...")
    
    config = load_config()
    
    if 'download_history' not in config:
        config['download_history'] = {}
    
    # Scan all podcast directories
    if not PODCASTS_DIR.exists():
        print(f"Podcasts directory not found: {PODCASTS_DIR}")
        return
    
    total_found = 0
    total_added = 0
    
    for podcast_dir in PODCASTS_DIR.iterdir():
        if not podcast_dir.is_dir():
            continue
        
        podcast_name = podcast_dir.name
        print(f"\nScanning: {podcast_name}")
        
        if podcast_name not in config['download_history']:
            config['download_history'][podcast_name] = []
        
        existing_filenames = {h.get('filename') for h in config['download_history'][podcast_name]}
        
        # Find all MP3 files
        for mp3_file in podcast_dir.glob('*.mp3'):
            total_found += 1
            filename = mp3_file.name
            
            # Skip if already in history
            if filename in existing_filenames:
                continue
            
            # Extract episode info
            extracted_podcast, published_date, episode_title = extract_episode_info(filename)
            
            # Use directory name if extraction failed
            if not extracted_podcast:
                extracted_podcast = podcast_name
            
            # Use filename as title if extraction failed
            if not episode_title:
                episode_title = filename.replace('.mp3', '')
            
            # Use file modification time as download date
            try:
                mtime = mp3_file.stat().st_mtime
                downloaded_at = datetime.fromtimestamp(mtime).isoformat()
            except OSError as e:
                logger.debug(f"Could not get mtime for {mp3_file.name}: {e}")
                downloaded_at = datetime.now().isoformat()
            
            # Use today's date if extraction failed
            if not published_date:
                published_date = datetime.now().strftime('%Y-%m-%d')
            
            history_entry = {
                "episode_title": episode_title,
                "published_date": published_date,
                "downloaded_at": downloaded_at,
                "filename": filename
            }
            
            config['download_history'][podcast_name].append(history_entry)
            total_added += 1
            print(f"  Added: {episode_title[:50]}...")
    
    # Update podcast download counts
    for podcast in config.get('podcasts', []):
        podcast_name = podcast['name']
        if podcast_name in config['download_history']:
            count = len(config['download_history'][podcast_name])
            podcast['downloaded_count'] = count
            print(f"\nUpdated {podcast_name}: {count} downloads")
    
    save_config(config)
    print(f"\n✓ Backfill complete!")
    print(f"  Found {total_found} files")
    print(f"  Added {total_added} new history entries")
    print(f"  Total history entries: {sum(len(h) for h in config['download_history'].values())}")

if __name__ == '__main__':
    backfill_history()
