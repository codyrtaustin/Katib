# README FOR FUTURE AGENTS - KATIB AUTOMATION

## TL;DR - IF IT'S BROKEN

1. Run: `bash ~/Katib/check_automation.sh`
2. If it says "Virtual environment missing" → See QUICK_FIX_PROMPT.md
3. If it says "ModuleNotFoundError" → Recreate venv (see below)
4. If LaunchAgent not running → Reload it (see below)

## WHAT THIS SYSTEM DOES

Downloads podcast episodes automatically every day at 9:00 AM PT by:
1. LaunchAgent triggers bash script
2. Bash script activates Python venv
3. Python script checks RSS feeds and downloads new episodes

## THE PROBLEM WE FIXED

**Date**: Jan 5-8, 2026  
**Error**: `ModuleNotFoundError: No module named 'requests'`  
**Cause**: Dependencies in system Python weren't accessible when launchd ran script  
**Solution**: Created isolated virtual environment with all dependencies

## THE FIX (DO THIS IF IT BREAKS AGAIN)

```bash
# Recreate virtual environment
cd ~/Katib
rm -rf venv
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Verify it works
bash katib_daily_download.sh

# Reload LaunchAgent
launchctl unload ~/Library/LaunchAgents/com.katib.download.plist
launchctl load ~/Library/LaunchAgents/com.katib.download.plist
```

## QUICK DIAGNOSIS

```bash
# Check status
bash ~/Katib/check_automation.sh

# Check for errors
cat ~/Documents/Katib/logs/launchd_download_error.log

# Check if ran today
ls -lh ~/Documents/Katib/logs/katib_downloader_$(date +%Y-%m-%d).log

# Test manually
cd ~/Katib && bash katib_daily_download.sh
```

## KEY FILES

- **Script**: `~/Katib/katib_daily_download.sh` (bash wrapper)
- **Python**: `~/Katib/katib_downloader.py` (main script)
- **Venv**: `~/Katib/venv/bin/python3` (CRITICAL - has all deps)
- **LaunchAgent**: `~/Library/LaunchAgents/com.katib.download.plist`
- **Error log**: `~/Documents/Katib/logs/launchd_download_error.log` (CHECK THIS FIRST)
- **Daily log**: `~/Documents/Katib/logs/katib_downloader_YYYY-MM-DD.log`

## SCHEDULE

- Runs: **EVERY DAY at 9:00 AM PT**
- Config: `StartCalendarInterval` with `Hour=9, Minute=0`
- **IMPORTANT**: Mac is configured to never sleep (`pmset sleep 0`) so LaunchAgents always fire
- If Mac is sleeping, LaunchAgents will NOT wake it - that's why we disable sleep

## WHY VENV IS CRITICAL

launchd runs with minimal environment. System Python dependencies aren't accessible. The venv is self-contained and uses absolute paths, so it works in launchd's minimal environment.

## COMMON ISSUES

1. **ModuleNotFoundError** → Venv broken/missing → Recreate venv
2. **Script not running** → LaunchAgent not loaded → Reload LaunchAgent
3. **No logs created** → Script failing before logging → Check error log
4. **Wrong time** → Plist schedule wrong → Fix plist and reload

## DOCUMENTATION FILES

- `QUICK_FIX_PROMPT.md` - Quick reference for fixes
- `AUTOMATION_TROUBLESHOOTING_GUIDE.md` - Complete troubleshooting guide
- `check_automation.sh` - Diagnostic script (run this first!)

## VERIFICATION COMMAND

```bash
# Full verification
launchctl list com.katib.download && \
test -f ~/Katib/venv/bin/python3 && echo "✓ Venv" || echo "✗ Venv MISSING" && \
~/Katib/venv/bin/python3 -c "import requests, feedparser; print('✓ Dependencies OK')" 2>&1 && \
ls -lh ~/Documents/Katib/logs/katib_downloader_$(date +%Y-%m-%d).log 2>/dev/null && echo "✓ Ran today" || echo "⚠ Not run today"
```

## STATUS AS OF JAN 8, 2026

✅ **FULLY OPERATIONAL**
- Venv created with all dependencies
- Script enhanced with fallbacks
- LaunchAgent loaded and scheduled
- All tests passed (11/11)
- Will run daily at 9 AM PT

---

**Remember**: If you see `ModuleNotFoundError`, the venv is the problem. Recreate it using the commands above.
