#!/usr/bin/env python3
"""
Proven Browser Manager - SIMPLIFIED

Simple session loading for CapCut automation.
Loads proven_session.json and creates Playwright context.
"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from playwright.sync_api import sync_playwright, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class ProvenBrowser:
    """
    SIMPLIFIED browser manager - just loads proven_session.json
    """
    
    def __init__(self):
        """Initialize with simple paths."""
        self.project_root = Path(__file__).parent.parent
        self.state_dir = self.project_root / "state"
        self.proven_session_file = self.state_dir / "proven_session.json"
        
        # Browser instances
        self.playwright = None
        self.browser = None
        self.context = None
    
    
    def create_context_with_proven_session(self, headless: bool = False) -> Optional[BrowserContext]:
        """
        SIMPLE: Load proven_session.json and create Playwright context.
        """
        if not self.proven_session_file.exists():
            print(f"[ERROR] proven_session.json not found: {self.proven_session_file}")
            return None
        
        try:
            print("Loading proven session...")
            
            with open(self.proven_session_file, 'r') as f:
                session_data = json.load(f)
            
            return self._create_playwright_context(session_data, headless)
                
        except Exception as e:
            print(f"[ERROR] Failed to load session: {e}")
            return None
    
    def _create_playwright_context(self, session_data: Dict[str, Any], headless: bool = False) -> Optional[BrowserContext]:
        """
        Create Playwright context and load cookies.
        """
        try:
            if not PLAYWRIGHT_AVAILABLE:
                print("[ERROR] Playwright not available")
                return None
            
            # Start Playwright
            self.playwright = sync_playwright().start()
            
            # Launch browser
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            # Create context
            self.context = self.browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )
            
            # Load cookies
            if 'cookies' in session_data:
                print("Loading cookies...")
                
                page = self.context.new_page()
                page.goto("https://www.capcut.com")
                time.sleep(2)
                
                # Add cookies
                cookies_added = 0
                for cookie in session_data['cookies']:
                    try:
                        pw_cookie = {
                            'name': cookie['name'],
                            'value': cookie['value'],
                            'domain': cookie.get('domain', '.capcut.com'),
                            'path': cookie.get('path', '/'),
                            'httpOnly': cookie.get('httpOnly', False),
                            'secure': cookie.get('secure', False)
                        }
                        
                        if 'expiry' in cookie:
                            pw_cookie['expires'] = cookie['expiry']
                        
                        self.context.add_cookies([pw_cookie])
                        cookies_added += 1
                        
                    except Exception:
                        continue
                
                print(f"[OK] Loaded {len(session_data['cookies'])} cookies")
                page.reload()
                time.sleep(2)
                page.close()
            
            print("[OK] Context ready!")
            return self.context
            
        except Exception as e:
            print(f"[ERROR] Failed to create Playwright context: {e}")
            return None
    
    def close(self):
        """Clean up browser instances."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                    self.playwright.stop()
        except Exception:
            pass


def main():
    """Test the browser manager."""
    print("Testing ProvenBrowser...")
    
    browser = ProvenBrowser()
    context = browser.create_context_with_proven_session(headless=False)
    
    if context:
        print("[OK] Playwright context created successfully")
        browser.close()
    else:
        print("[ERROR] Failed to create context")


if __name__ == "__main__":
    main()
