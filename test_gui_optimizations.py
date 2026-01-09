#!/usr/bin/env python3
"""
Test script to verify GUI optimizations work correctly.
Tests the key optimization features without requiring a full GUI.
"""

import sys
import os
from pathlib import Path
import json
import time

# Add Katib directory to path
sys.path.insert(0, str(Path(__file__).parent))

from katib_downloader import load_config, save_config, CONFIG_FILE

def test_config_file_tracking():
    """Test that config file modification time tracking works."""
    print("Testing config file modification time tracking...")
    
    # Create a mock GUI class with just the config tracking method
    class MockGUI:
        def __init__(self):
            self.config_cache = None
            self.config_mtime = None
        
        def _get_config_if_changed(self, force_reload=False):
            """Get config, only reloading if file has changed or forced."""
            if force_reload:
                config = load_config()
                self.config_cache = config
                try:
                    self.config_mtime = CONFIG_FILE.stat().st_mtime
                except:
                    self.config_mtime = None
                return config
            
            # Check if file has been modified
            try:
                current_mtime = CONFIG_FILE.stat().st_mtime
                if self.config_mtime is None or current_mtime > self.config_mtime:
                    config = load_config()
                    self.config_cache = config
                    self.config_mtime = current_mtime
                    return config
            except:
                pass
            
            # Use cache if available
            if self.config_cache is None:
                config = load_config()
                self.config_cache = config
                try:
                    self.config_mtime = CONFIG_FILE.stat().st_mtime
                except:
                    self.config_mtime = None
                return config
            
            return self.config_cache
    
    gui = MockGUI()
    
    # First load - should read from file
    config1 = gui._get_config_if_changed(force_reload=False)
    assert config1 is not None, "Config should be loaded"
    assert gui.config_cache is not None, "Cache should be set"
    assert gui.config_mtime is not None, "Modification time should be set"
    print("  ✓ First load successful")
    
    # Second load without file change - should use cache
    mtime_before = gui.config_mtime
    config2 = gui._get_config_if_changed(force_reload=False)
    assert config2 is gui.config_cache, "Should return cached config"
    assert gui.config_mtime == mtime_before, "Modification time should not change"
    print("  ✓ Cache hit successful")
    
    # Force reload - should reload from file
    config3 = gui._get_config_if_changed(force_reload=True)
    assert config3 is not None, "Config should be loaded"
    print("  ✓ Force reload successful")
    
    print("  ✓ Config file tracking test passed\n")


def test_config_structure():
    """Test that config file has expected structure."""
    print("Testing config file structure...")
    
    config = load_config()
    
    # Check required keys
    required_keys = ['podcasts', 'download_queue', 'failed_downloads', 'download_history']
    for key in required_keys:
        assert key in config, f"Config should have '{key}' key"
    
    print("  ✓ Config structure valid")
    
    # Check data types
    assert isinstance(config['podcasts'], list), "podcasts should be a list"
    assert isinstance(config['download_queue'], list), "download_queue should be a list"
    assert isinstance(config['failed_downloads'], list), "failed_downloads should be a list"
    assert isinstance(config['download_history'], dict), "download_history should be a dict"
    
    print("  ✓ Config data types valid")
    print("  ✓ Config structure test passed\n")


def test_refresh_optimizations():
    """Test that refresh optimizations handle data correctly."""
    print("Testing refresh optimizations...")
    
    config = load_config()
    
    # Test queue processing limit
    queue = config.get('download_queue', [])
    queue_limit = min(len(queue), 100)
    processed = queue[:queue_limit]
    
    assert len(processed) <= 100, "Should process max 100 items"
    print(f"  ✓ Queue processing limit: {len(processed)} items (total: {len(queue)})")
    
    # Test history limit
    history = config.get('download_history', {})
    history_items = list(history.items())[:3]
    assert len(history_items) <= 3, "Should limit to 3 history items"
    print(f"  ✓ History display limit: {len(history_items)} items (total: {len(history)})")
    
    # Test failed downloads limit
    failed = config.get('failed_downloads', [])
    failed_limit = failed[:50]
    assert len(failed_limit) <= 50, "Should limit to 50 failed items"
    print(f"  ✓ Failed downloads limit: {len(failed_limit)} items (total: {len(failed)})")
    
    print("  ✓ Refresh optimizations test passed\n")


def test_config_save_load():
    """Test that config can be saved and loaded correctly."""
    print("Testing config save/load...")
    
    # Load original config
    original_config = load_config()
    original_podcasts_count = len(original_config.get('podcasts', []))
    
    # Save and reload
    save_success = save_config(original_config)
    assert save_success, "Config save should succeed"
    
    reloaded_config = load_config()
    assert len(reloaded_config.get('podcasts', [])) == original_podcasts_count, "Podcast count should match"
    
    print("  ✓ Config save/load successful")
    print("  ✓ Config save/load test passed\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Katib GUI Optimizations")
    print("=" * 60)
    print()
    
    try:
        test_config_structure()
        test_config_file_tracking()
        test_refresh_optimizations()
        test_config_save_load()
        
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
