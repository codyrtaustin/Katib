# Quick Check Prompt for Katib Automation

Use this prompt to check if the Katib automation script ran today:

```
Check if the Katib automation script ran today. Run: bash ~/Katib/check_automation.sh

If that doesn't work, check these log files:
1. ~/Documents/Katib/logs/launchd_download.log (LaunchAgent stdout)
2. ~/Documents/Katib/logs/launchd_download_error.log (LaunchAgent errors)
3. ~/Documents/Katib/logs/katib_downloader_$(date +%Y-%m-%d).log (today's Python log)

Look for entries from around 9 AM PT. The script should log "Katib Daily Download Script Started" and "Checking RSS feeds for new episodes".
```
