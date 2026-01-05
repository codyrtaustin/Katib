# Katib - Podcast Downloader System

A local podcast management system for macOS that automatically downloads and organizes podcast episodes from RSS feeds.

## Features

- **GUI Application**: Easy-to-use interface for managing podcast subscriptions
- **Automatic Downloads**: Queue-based system that processes downloads sequentially
- **RSS Feed Support**: Add podcasts by pasting their RSS feed URL
- **Persistent Queue**: Downloads continue even after closing the app
- **Retry Logic**: Automatic retry of failed downloads (up to 5 attempts)
- **macOS Integration**: Native notifications and launchd scheduling
- **Background Processing**: Downloads continue in the background
- **Progress Tracking**: Real-time download progress and queue status

## Directory Structure

```
~/Documents/Katib/
├── podcasts/
│   └── [Podcast Name]/
│       └── [Podcast Name] - YYYY-MM-DD - [Episode Title].mp3
├── transcripts/
│   └── [Podcast Name]/
│       └── [Podcast Name] - YYYY-MM-DD - [Episode Title].txt
├── config/
│   └── katib_config.json
└── logs/
    └── katib_downloader_YYYY-MM-DD.log
```

## Installation

### Prerequisites

- macOS (tested on macOS 10.14+)
- Python 3.9 or higher
- pip (Python package manager)

### Step 1: Install Python Dependencies

```bash
cd ~/Katib
pip3 install -r requirements.txt
```

Or if you prefer using a virtual environment:

```bash
cd ~/Katib
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Verify Installation

Test the downloader script:

```bash
python3 katib_downloader.py --help
```

### Step 3: Run the GUI Application

```bash
python3 katib.py
```

Or make it executable and run directly:

```bash
chmod +x katib.py
./katib.py
```

## Usage

### Adding a Podcast

1. Launch the GUI application: `python3 katib.py`
2. Paste the RSS feed URL in the "RSS Feed URL" field
3. Click "Add Podcast"
4. The system will:
   - Parse the RSS feed to get the podcast name
   - Queue all available episodes for download
   - If there are 100+ episodes, you'll be asked to confirm

### Manual Downloads

- **Download Now**: Click to process the download queue immediately
- **Check for New Episodes**: Manually check RSS feeds for new episodes
- The queue processes downloads sequentially (one at a time)

### Managing Podcasts

- **Remove Podcast**: Select a podcast from the list and click "Remove Selected"
  - Note: This removes the subscription but does NOT delete downloaded files
- **View Queue Status**: The status panel shows pending, downloading, completed, and failed downloads
- **Retry Failed Downloads**: Select a failed download and click "Retry Selected"

### Automation (Optional)

Set up automatic daily downloads at 9 AM PT:

1. Copy the launchd plist files to `~/Library/LaunchAgents/`:

```bash
cp com.katib.download.plist ~/Library/LaunchAgents/
cp com.katib.transcribe.plist ~/Library/LaunchAgents/
```

2. **Important**: Edit the plist files to update the paths:

```bash
# Edit the plist files to use your actual home directory path
nano ~/Library/LaunchAgents/com.katib.download.plist
# Replace /Users/codyaustin with your actual username
```

3. Load the launchd agents:

```bash
launchctl load ~/Library/LaunchAgents/com.katib.download.plist
launchctl load ~/Library/LaunchAgents/com.katib.transcribe.plist
```

4. Verify they're loaded:

```bash
launchctl list | grep katib
```

5. To unload (disable automation):

```bash
launchctl unload ~/Library/LaunchAgents/com.katib.download.plist
launchctl unload ~/Library/LaunchAgents/com.katib.transcribe.plist
```

## Command Line Usage

The downloader can also be run from the command line:

```bash
# Check all RSS feeds for new episodes
python3 katib_downloader.py --check-new

# Process the download queue
python3 katib_downloader.py --process-queue

# Do both (check new and process queue)
python3 katib_downloader.py --all
```

## Configuration

Configuration is stored in `~/Documents/Katib/config/katib_config.json`. This file contains:

- **podcasts**: List of subscribed podcasts with metadata
- **download_queue**: Episodes waiting to be downloaded
- **failed_downloads**: Episodes that failed after 5 retry attempts
- **last_check**: Timestamp of last RSS feed check

You can edit this file manually if needed, but it's recommended to use the GUI.

## File Naming Convention

Episodes are saved with the format:
```
[Podcast Name] - YYYY-MM-DD - [Episode Title].mp3
```

- Uses the episode's published date
- Special characters are removed from filenames
- Filenames are limited to 200 characters

## Troubleshooting

### Downloads Not Starting

1. Check the queue status in the GUI
2. Verify you have internet connectivity
3. Check the logs in `~/Documents/Katib/logs/`

### RSS Feed Errors

- Verify the RSS URL is correct and accessible
- Some podcasts may have non-standard RSS formats
- Check the logs for specific error messages

### Disk Space Issues

- The system checks available disk space before downloading
- Free up space if downloads are failing
- Downloaded files are in `~/Documents/Katib/podcasts/`

### Launchd Not Running

1. Check if the plist files are in `~/Library/LaunchAgents/`
2. Verify the paths in the plist files are correct
3. Check launchd logs:
   ```bash
   tail -f ~/Documents/Katib/logs/launchd_download.log
   ```

### Permission Errors

Make sure the scripts are executable:

```bash
chmod +x katib.py katib_downloader.py katib_daily_download.sh katib_daily_transcribe.sh
```

## Logs

Logs are stored in `~/Documents/Katib/logs/`:
- `katib_downloader_YYYY-MM-DD.log` - Daily download logs
- `launchd_download.log` - Launchd output for download automation
- `launchd_transcribe.log` - Launchd output for transcription automation

## Future Features

- **Transcription Integration**: Automatic transcription using MacWhisper (placeholder ready)
- **Search/Filter**: Search and filter podcasts and episodes
- **Pause/Resume**: Pause and resume downloads
- **Download Speed Limits**: Configure maximum download speed
- **Episode Management**: Delete episodes, mark as listened, etc.

## Technical Details

### Dependencies

- **feedparser**: RSS feed parsing
- **requests**: HTTP downloads with streaming support
- **python-dateutil**: Date parsing for various RSS formats
- **tkinter**: GUI framework (included with Python)

### Download Behavior

- Downloads are processed sequentially (one at a time)
- Large files are streamed (not loaded entirely into memory)
- Partial downloads can be resumed
- Network errors trigger automatic retries (up to 5 attempts)
- Failed downloads after 5 retries are moved to the failed list

### Queue Management

- Queue persists across app restarts
- Queue state is saved after each download
- Stuck downloads (status: downloading) are reset to pending on app launch
- Queue processing continues in background threads

## License

This project is provided as-is for personal use.

## Support

For issues or questions:
1. Check the logs in `~/Documents/Katib/logs/`
2. Review the troubleshooting section above
3. Check the configuration file for any issues
