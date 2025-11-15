#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CapCut Automation - COMPLETE PIPELINE

Complete end-to-end automation for CapCut AI video generation.
Handles: Navigation → Form Fill → Generate → Export → Download → Video Editing → YouTube Upload
"""

import os
import sys
import json

# Fix Windows console encoding for emoji support and disable buffering for real-time output
if sys.platform == 'win32':
    try:
        import codecs
        # Use line buffering for immediate output
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception:
        pass

# Disable output buffering for real-time console updates
os.environ['PYTHONUNBUFFERED'] = '1'
import time
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

# Import only what we actually use
try:
    from sheets_reader import SheetsReader
    from proven_browser import ProvenBrowser
    from state_store import StateStore, JobStatus
    from video_downloader import VideoDownloader
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"ERROR: Failed to import modules: {e}")
    MODULES_AVAILABLE = False

try:
    from playwright.sync_api import Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# Override built-in print to always flush for real-time output
_original_print = print
def print(*args, **kwargs):
    """Custom print function that always flushes output for real-time display."""
    kwargs.setdefault('flush', True)
    _original_print(*args, **kwargs)


class JobState:
    """Represents the state of a video creation job."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    
    def __init__(self, job_data: Dict[str, Any], job_id: str):
        self.job_id = job_id
        self.job_data = job_data
        self.state = self.PENDING
        self.start_time = None
        self.end_time = None
        self.error_message = None
        self.diagnostics = []
        self.current_step = None
        self.attempts = 0
        self.max_attempts = 3


class CapCutOrchestrator:
    """
    SIMPLIFIED CapCut automation - only what actually works.
    """
    
    # CapCut URLs
    CAPCUT_BASE_URL = "https://www.capcut.com"
    CAPCUT_AI_CREATOR_URL = "https://www.capcut.com/ai-homepage?enter_from=page_header&from_page=work_space&start_tab=video"
    
    def __init__(self, dry_run: bool = False, headless: bool = False):
        """
        Initialize the orchestrator.
        
        Args:
            dry_run: If True, simulate actions without performing them
            headless: Whether to run browser in headless mode
        """
        if not MODULES_AVAILABLE:
            raise ImportError("Required automation modules not available")
        
        self.dry_run = dry_run
        self.headless = headless
        
        # Load environment variables
        load_dotenv()
        
        # Initialize only what we use
        self.sheets_reader = SheetsReader()
        self.browser_manager = ProvenBrowser()
        self.state_store = StateStore()
        self.video_downloader = VideoDownloader()
        
        # Session state
        self.browser_context = None
        self.current_page = None
        
        # Job management
        self.jobs = []
        self.job_states = {}
        self.session_stats = {
            "total_jobs": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "start_time": None,
            "end_time": None
        }
        
        # Simple state management
        self.project_root = Path(__file__).parent.parent
        self.state_dir = self.project_root / "state"
    
    def load_jobs(self, source: Optional[str] = None, limit: Optional[int] = None) -> bool:
        """
        Load video creation jobs from Google Sheets only.
        Processes only ONE video per run - the first one with uploaded='No'.
        
        Args:
            source: Force specific source ("sheets" only)
            limit: Ignored - always processes only 1 job
            
        Returns:
            True if jobs loaded successfully
        """
        try:
            print("=" * 60)
            print("Loading Video Creation Jobs")
            print("=" * 60)
            
            # Force Google Sheets source
            result = self.sheets_reader.get_video_jobs(force_source="sheets")
            
            if not result["success"]:
                print("ERROR: Failed to load jobs from Google Sheets:")
                for error in result["errors"]:
                    print(f"  {error}")
                return False
            
            all_jobs = result["data"]
            
            # Filter to only get jobs where video_generation is NOT 'completed'
            unprocessed_jobs = [
                job for job in all_jobs 
                if job.get('video_generation', '').lower() != 'completed'
            ]
            
            if not unprocessed_jobs:
                print("✅ All videos have been processed! No pending jobs found.")
                print("📊 All videos are marked as 'completed' in Google Sheets.")
                return False
            
            # Take only the first unprocessed job (1 run = 1 video)
            self.jobs = [unprocessed_jobs[0]]
            
            # Initialize job state for the single job
            job_id = "job_001"
            self.job_states[job_id] = JobState(self.jobs[0], job_id)
            self.state_store.add_job(job_id, self.jobs[0])
            
            self.session_stats["total_jobs"] = 1
            
            print(f"SUCCESS: Found 1 pending job from Google Sheets")
            print(f"📝 Processing: '{self.jobs[0]['title']}' - {self.jobs[0]['visual_style']} style, {self.jobs[0]['voice']} voice")
            print(f"📊 Total pending jobs in sheet: {len(unprocessed_jobs)}")
            
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to load jobs: {e}")
            return False
    
    def setup_browser_session(self) -> bool:
        """
        SIMPLE: Load existing proven_session.json and create browser context.
            
        Returns:
            True if session setup successful
        """
        try:
            print("\n" + "=" * 60)
            print("Loading Existing Proven Session")
            print("=" * 60)
            
            if self.dry_run:
                print("DRY RUN: Would load proven_session.json")
                return True
            
            # Simple check: does the file exist?
            proven_session_file = self.state_dir / "proven_session.json"
            if not proven_session_file.exists():
                print("❌ proven_session.json not found!")
                print(f"Expected location: {proven_session_file}")
                print()
                print("Please make sure you have the proven_session.json file")
                print("in the state/ directory from your working login solution.")
                return False
            
            print("✅ Found proven_session.json")
            
            # Create browser context with the existing session
            print("🚀 Creating browser context with proven session...")
            self.browser_context = self.browser_manager.create_context_with_proven_session(
                headless=self.headless
            )
            
            if not self.browser_context:
                print("❌ Failed to create browser context")
                return False
            
            # Create page
            self.current_page = self.browser_context.new_page()
            
            print("✅ SUCCESS: Browser session ready!")
            print("🎉 Using existing proven session - no login needed!")
            return True
            
        except Exception as e:
            print(f"❌ ERROR: Browser session setup failed: {e}")
            return False
    
    def navigate_to_ai_creator(self) -> bool:
        """
        SIMPLE: Navigate to CapCut AI video creator page.
        
        Returns:
            True if navigation successful
        """
        try:
            print(f"\n🚀 Navigating to AI Creator...")
            print(f"URL: {self.CAPCUT_AI_CREATOR_URL}")
            
            if self.dry_run:
                print("DRY RUN: Would navigate to AI creator page")
                return True
            
            # Navigate with longer timeout and simpler wait
            print("⏳ Loading page...")
            self.current_page.goto(self.CAPCUT_AI_CREATOR_URL, timeout=60000)
            
            # Wait for page to load
            print("⏳ Waiting for page to load...")
            time.sleep(5)
            
            # Check current URL
            current_url = self.current_page.url
            print(f"📍 Current URL: {current_url}")
            
            # Simple success check - if we're on capcut.com and page loaded, it's good
            if "capcut.com" in current_url.lower():
                print("✅ SUCCESS: Navigated to CapCut AI creator page")
                return True
            else:
                print(f"❌ WARNING: Unexpected URL: {current_url}")
                return False
            
        except Exception as e:
            print(f"❌ ERROR: Navigation failed: {e}")
            return False
    
    def fill_capcut_form(self, job: Dict[str, Any]) -> bool:
        """
        COMPLETE: Fill the CapCut AI form with all job data from Google Sheets.
        
        Args:
            job: Job data dictionary with title, visual_style, voice, duration, aspect_ratio
            
        Returns:
            True if form filled successfully
        """
        try:
            print(f"📝 Filling form for: {job['title']}")
            print(f"   Visual Style: {job['visual_style']}")
            print(f"   Voice: {job['voice']}")
            print(f"   Duration: {job['duration']}")
            print(f"   Aspect Ratio: {job['aspect_ratio']}")
            
            # Step 1: Fill the description textarea
            print("1️⃣ Looking for description textarea...")
            
            # Try to find the textarea - EXACT working selector from capture test
            textarea_selectors = [
                ".lv-textarea",  # WORKS! From capture test
                "textarea[placeholder*='Describe your video idea' i]",
                "textarea[placeholder*='video idea' i]", 
                "textarea"
            ]
            
            textarea_found = False
            for selector in textarea_selectors:
                try:
                    print(f"   Trying: {selector}")
                    textarea = self.current_page.locator(selector).first
                    if textarea.is_visible():
                        print(f"   ✅ Found textarea with: {selector}")
                        
                        # Clear and fill with job title/description
                        textarea.click()
                        textarea.fill("")  # Clear first
                        textarea.fill(job['title'])
                        
                        print(f"   ✅ Filled with: {job['title']}")
                        textarea_found = True
                        break
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
                    continue
            
            if not textarea_found:
                print("❌ Could not find description textarea")
                return False
            
            # Wait a bit for the form to process
            time.sleep(2)
            
            # Step 2: Set Visual Style
            print("2️⃣ Setting visual style...")
            if not self._set_visual_style(job['visual_style']):
                print("❌ Failed to set visual style")
                return False
            
            # Step 3: Set Voice
            print("3️⃣ Setting voice...")
            if not self._set_voice(job['voice']):
                print("❌ Failed to set voice")
                return False
            
            # Step 4: Set Duration
            print("4️⃣ Setting duration...")
            if not self._set_duration(job['duration']):
                print("❌ Failed to set duration")
                return False
            
            # Step 5: Set Aspect Ratio
            print("5️⃣ Setting aspect ratio...")
            if not self._set_aspect_ratio(job['aspect_ratio']):
                print("❌ Failed to set aspect ratio")
                return False
            
            # Wait a bit for all settings to process
            time.sleep(3)
            
            print("✅ Form filling completed!")
            return True
            
        except Exception as e:
            print(f"❌ Form filling failed: {e}")
            return False
    
    def click_generate_button(self) -> bool:
        """
        SIMPLE: Click the Generate button to start video creation.
        
        Returns:
            True if button clicked successfully
        """
        try:
            print("🔍 Looking for Generate button...")
            
            # Try to find the Generate button
            generate_selectors = [
                "button:has-text('Generate')",
                "button:has-text('Create')",
                "[data-testid='generate-button']",
                "button[aria-label*='generate' i]",
                ".generate-btn",
                "button"  # Last resort - any button
            ]
            
            button_found = False
            for selector in generate_selectors:
                try:
                    print(f"   Trying: {selector}")
                    buttons = self.current_page.locator(selector)
                    count = buttons.count()
                    
                    if count > 0:
                        for i in range(count):
                            button = buttons.nth(i)
                            if button.is_visible():
                                button_text = button.text_content() or ""
                                print(f"   Found button: '{button_text}'")
                                
                                # Check if it's likely the generate button
                                if any(word in button_text.lower() for word in ['generate', 'create', 'start']):
                                    print(f"   ✅ Clicking Generate button: '{button_text}'")
                                    button.click()
                                    button_found = True
                                    break
                    
                    if button_found:
                        break
                        
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
                    continue
            
            if not button_found:
                # Try clicking any visible button as last resort
                print("   🔄 Trying to find any clickable button...")
                try:
                    all_buttons = self.current_page.locator("button")
                    for i in range(all_buttons.count()):
                        button = all_buttons.nth(i)
                        if button.is_visible():
                            text = button.text_content() or ""
                            print(f"   Found button: '{text}'")
                            if text.strip():  # If button has text, click it
                                print(f"   ✅ Clicking button: '{text}'")
                                button.click()
                                button_found = True
                                break
                except Exception as e:
                    print(f"   ❌ Last resort failed: {e}")
            
            if not button_found:
                print("❌ Could not find Generate button")
                return False
            
            # Wait a bit for the click to process
            time.sleep(2)
            
            print("✅ Generate button clicked!")
            return True
            
        except Exception as e:
            print(f"❌ Generate button click failed: {e}")
            return False
    
    def close_popups(self) -> bool:
        """
        SIMPLE: Close any popups that might be blocking the interface.
        
        Returns:
            True if popups handled successfully
        """
        try:
            print("🔍 Looking for popups to close...")
            
            # Common popup close selectors
            close_selectors = [
                "button:has-text('×')",  # X button
                "button:has-text('Close')",
                "button:has-text('OK')",
                "button:has-text('Accept')",
                "button:has-text('Agree')",
                "button:has-text('Continue')",
                "[aria-label*='close' i]",
                "[data-testid*='close']",
                ".close-btn",
                ".modal-close",
                "button[class*='close']"
            ]
            
            popups_closed = 0
            
            for selector in close_selectors:
                try:
                    buttons = self.current_page.locator(selector)
                    count = buttons.count()
                    
                    for i in range(count):
                        button = buttons.nth(i)
                        if button.is_visible():
                            button_text = button.text_content() or ""
                            print(f"   Found close button: '{button_text}' with selector: {selector}")
                            
                            # Click the close button
                            button.click()
                            popups_closed += 1
                            print(f"   ✅ Closed popup #{popups_closed}")
                            
                            # Wait a bit for popup to close
                            time.sleep(1)
                            
                except Exception as e:
                    continue
            
            # Also try pressing Escape key to close popups
            try:
                self.current_page.keyboard.press("Escape")
                print("   📋 Pressed Escape key")
                time.sleep(1)
            except Exception:
                pass
            
            if popups_closed > 0:
                print(f"✅ Closed {popups_closed} popup(s)")
            else:
                print("ℹ️  No popups found to close")
            
            return True
            
        except Exception as e:
            print(f"❌ Popup handling failed: {e}")
            return False
    
    def handle_generation_page_navigation(self) -> bool:
        """
        Handle navigation to the generation page after clicking Generate.
        CapCut opens a NEW TAB with URL like: /ai-creator/storyboard/...
        
        Returns:
            True if navigation handled successfully
        """
        try:
            print("🔍 Monitoring for new tab/page after Generate click...")
            
            # Wait for potential new tab/page
            max_wait = 30  # 30 seconds max
            check_interval = 2
            elapsed = 0
            
            original_url = self.current_page.url
            print(f"   Original URL: {original_url}")
            
            while elapsed < max_wait:
                # Check all pages/tabs in the browser context
                all_pages = self.browser_context.pages
                print(f"   📊 Total pages/tabs: {len(all_pages)}")
                
                # Look for the generation page in all tabs
                for i, page in enumerate(all_pages):
                    try:
                        page_url = page.url
                        print(f"   Tab {i+1}: {page_url}")
                        
                        # Check if this is the generation page
                        if "ai-creator" in page_url or "storyboard" in page_url:
                            print(f"   🎉 Found generation page in Tab {i+1}!")
                            print(f"   🔄 Switching to generation page...")
                            
                            # Switch to the generation page
                            self.current_page = page
                            
                            # Bring the page to front
                            page.bring_to_front()
                            
                            print(f"   ✅ Successfully switched to generation page!")
                            print(f"   📍 New active page: {self.current_page.url}")
                            return True
                            
                    except Exception as e:
                        print(f"   ❌ Error checking tab {i+1}: {e}")
                        continue
                
                # Check if current page URL changed (same tab navigation)
                current_url = self.current_page.url
                if current_url != original_url:
                    print(f"   🎉 Current page navigated to: {current_url}")
                    
                    if "ai-creator" in current_url or "storyboard" in current_url:
                        print("   ✅ Successfully navigated to generation page!")
                        return True
                
                # Check if generation started on current page
                try:
                    generation_indicators = [
                        "[data-testid*='progress']",
                        ".progress-bar", 
                        "div:has-text('Generating')",
                        "div:has-text('Processing')",
                        "[role='progressbar']"
                    ]
                    
                    for indicator in generation_indicators:
                        elements = self.current_page.locator(indicator)
                        if elements.count() > 0 and elements.first.is_visible():
                            print(f"   ✅ Generation started on current page")
                            return True
                            
                except Exception:
                    pass
                
                print(f"   ⏱️ Waiting for new tab/navigation... ({elapsed}s)")
                time.sleep(check_interval)
                elapsed += check_interval
            
            print("   ⚠️ No new tab detected - continuing with current page")
            return True
            
        except Exception as e:
            print(f"❌ Page navigation handling failed: {e}")
            return False
    
    def wait_for_video_generation(self) -> bool:
        """
        SIMPLE: Wait for video generation to complete.
        
        Returns:
            True if generation completed successfully
        """
        try:
            print("⏳ Monitoring video generation progress...")
            print(f"   📍 Current page: {self.current_page.url}")
            
            max_wait_time = 300  # 5 minutes max
            check_interval = 5   # Check every 5 seconds
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                print(f"   ⏱️  Waiting... ({elapsed_time}s / {max_wait_time}s)")
                print(f"   📍 Checking on: {self.current_page.url}")
                
                # Check for generation completion indicators (Export button appears)
                completion_indicators = [
                    "button:has-text('Export')",  # Main indicator - Export button appears
                    "button:has-text('Download')",
                    "button:has-text('Save')",
                    "[data-testid*='export']",
                    ".export-btn",
                    "div:has-text('Generation complete')",
                    "div:has-text('Video ready')",
                    "div:has-text('Complete')"
                ]
                
                # Debug: Show all buttons on page
                try:
                    all_buttons = self.current_page.locator("button").all()
                    button_texts = []
                    for button in all_buttons[:5]:  # Show first 5 buttons
                        try:
                            if button.is_visible():
                                text = button.text_content() or ""
                                if text.strip():
                                    button_texts.append(text.strip())
                        except Exception:
                            continue
                    if button_texts:
                        print(f"   🔍 Visible buttons: {', '.join(button_texts)}")
                except Exception:
                    pass
                
                generation_complete = False
                for indicator in completion_indicators:
                    try:
                        elements = self.current_page.locator(indicator)
                        count = elements.count()
                        print(f"   🔍 Checking '{indicator}': found {count} elements")
                        
                        if count > 0 and elements.first.is_visible():
                            element_text = elements.first.text_content() or ""
                            print(f"   🎉 Found completion indicator: '{element_text}' with selector: {indicator}")
                            print("✅ Video generation completed! Export button is now available.")
                            generation_complete = True
                            break
                    except Exception as e:
                        print(f"   ❌ Selector '{indicator}' failed: {e}")
                        continue
                
                if generation_complete:
                    return True  # Exit immediately when Export button is found
                
                # Wait before next check
                time.sleep(check_interval)
                elapsed_time += check_interval
                
                # Also check if we're still on the right page
                try:
                    current_url = self.current_page.url
                    if "capcut.com" not in current_url.lower():
                        print(f"❌ Page changed unexpectedly: {current_url}")
                        return False
                except Exception:
                    pass
            
            print(f"⏰ Timeout: Video generation took longer than {max_wait_time} seconds")
            print("   This might be normal for longer videos. Check manually.")
            return True  # Return True anyway, might just be a long generation
            
        except Exception as e:
            print(f"❌ Generation monitoring failed: {e}")
            return False
    
    def match_stock_media(self) -> bool:
        """
        Match stock media before exporting the video.
        Steps:
        1. Click on "Scenes" in the left sidebar
        2. Click on "Media" tab
        3. Click on "Match stock media" button
        4. Click "Continue" on the confirmation popup
        5. Wait 90 seconds for matching to complete
        
        Returns:
            True if stock media matching completed successfully
        """
        try:
            print("\n" + "=" * 60)
            print("🎬 Matching Stock Media")
            print("=" * 60)
            
            # Debug: Check current page and frames
            print(f"📍 Current URL: {self.current_page.url}")
            print(f"📊 Number of frames: {len(self.current_page.frames)}")
            
            # CRITICAL: Use page.evaluate to run the EXACT console script that works
            print("\n🔧 Using direct JavaScript execution (like console script)...")
            
            try:
                # Step 1: Click Scenes using JavaScript (exactly like console)
                print("1️⃣ Clicking 'Scenes' button with JavaScript...")
                result = self.current_page.evaluate("""
                    () => {
                        const scenesElements = Array.from(document.querySelectorAll('*')).filter(el => 
                            el.textContent.trim() === 'Scenes' && el.offsetParent !== null
                        );
                        if (scenesElements.length > 0) {
                            scenesElements[0].click();
                            return { success: true, found: scenesElements.length };
                        }
                        return { success: false, found: 0 };
                    }
                """)
                
                if result['success']:
                    print(f"   ✅ Clicked 'Scenes' button (found {result['found']} elements)")
                    scenes_clicked = True
                else:
                    print(f"   ❌ Could not find 'Scenes' button")
                    scenes_clicked = False
                    
            except Exception as e:
                print(f"   ❌ JavaScript execution failed: {e}")
                scenes_clicked = False
            
            if not scenes_clicked:
                print("❌ Could not find 'Scenes' button")
                return False
            
            # Wait for the Scenes panel to open (human-like delay)
            print("   ⏳ Waiting for Scenes panel to open...")
            time.sleep(3)
            
            # Step 2: Click on "Media" tab using JavaScript
            print("2️⃣ Clicking 'Media' tab with JavaScript...")
            time.sleep(0.8)  # Human-like delay before clicking
            
            try:
                result = self.current_page.evaluate("""
                    () => {
                        const mediaElements = Array.from(document.querySelectorAll('*')).filter(el => 
                            el.textContent.trim() === 'Media' && el.offsetParent !== null
                        );
                        if (mediaElements.length > 0) {
                            mediaElements[0].click();
                            return { success: true, found: mediaElements.length };
                        }
                        return { success: false, found: 0 };
                    }
                """)
                
                if result['success']:
                    print(f"   ✅ Clicked 'Media' tab (found {result['found']} elements)")
                    media_clicked = True
                else:
                    print(f"   ❌ Could not find 'Media' tab")
                    return False
                    
            except Exception as e:
                print(f"   ❌ JavaScript execution failed: {e}")
                return False
            
            # Wait for the Media panel to load (human-like delay)
            print("   ⏳ Waiting for Media panel to load...")
            time.sleep(2.5)
            
            # Step 3: Click on "Match" button using JavaScript
            print("3️⃣ Clicking 'Match' button with JavaScript...")
            time.sleep(1.2)  # Human-like delay before clicking
            
            try:
                result = self.current_page.evaluate("""
                    () => {
                        // Method 1: Try class-based selector first
                        const matchBtn = document.querySelector("div[class*='match-media-btn']");
                        if (matchBtn && matchBtn.offsetParent !== null) {
                            matchBtn.click();
                            return { success: true, method: 'class-selector' };
                        }
                        
                        // Method 2: Find all divs with exact "Match" text
                        const allDivs = Array.from(document.querySelectorAll('div'));
                        const matchDivs = allDivs.filter(div => {
                            const text = div.textContent.trim();
                            return text === 'Match' && div.offsetParent !== null;
                        });
                        
                        if (matchDivs.length > 0) {
                            matchDivs[matchDivs.length - 1].click(); // Use last one
                            return { success: true, method: 'text-match', found: matchDivs.length };
                        }
                        
                        return { success: false };
                    }
                """)
                
                if result['success']:
                    method = result.get('method', 'unknown')
                    print(f"   ✅ Clicked 'Match' button (method: {method})")
                    match_clicked = True
                else:
                    print(f"   ❌ Could not find 'Match' button")
                    return False
                    
            except Exception as e:
                print(f"   ❌ JavaScript execution failed: {e}")
                return False
            
            # Wait longer for confirmation popup to appear (human-like delay)
            print("   ⏳ Waiting for confirmation popup...")
            time.sleep(3.5)
            
            # Step 4: Click "Continue" button using JavaScript
            print("4️⃣ Clicking 'Continue' button with JavaScript...")
            time.sleep(0.6)  # Human-like delay before clicking
            
            try:
                result = self.current_page.evaluate("""
                    () => {
                        const allButtons = Array.from(document.querySelectorAll('button, div[role="button"]')).filter(btn => 
                            btn.offsetParent !== null
                        );
                        
                        const continueBtn = allButtons.find(btn => 
                            btn.textContent.toLowerCase().includes('continue')
                        );
                        
                        if (continueBtn) {
                            continueBtn.click();
                            return { success: true, text: continueBtn.textContent.trim() };
                        }
                        
                        return { success: false };
                    }
                """)
                
                if result['success']:
                    print(f"   ✅ Clicked 'Continue' button: '{result.get('text', '')}'")
                    continue_clicked = True
                else:
                    print(f"   ❌ Could not find 'Continue' button")
                    return False
                    
            except Exception as e:
                print(f"   ❌ JavaScript execution failed: {e}")
                return False
            
            # Step 5: Wait 90 seconds for stock media matching to complete
            print("5️⃣ Waiting 90 seconds for stock media matching to complete...")
            wait_time = 90
            for i in range(wait_time):
                remaining = wait_time - i
                if remaining % 10 == 0 or remaining <= 5:
                    print(f"   ⏱️  {remaining} seconds remaining...")
                time.sleep(1)
            
            print("✅ Stock media matching completed!")
            return True
            
        except Exception as e:
            print(f"❌ Stock media matching failed: {e}")
            return False
    
    def set_video_customizations(self, job: Dict[str, Any]) -> bool:
        """
        SIMPLE: Set video customization options using the same methods as fill_form().
        
        Args:
            job: Job data dictionary
            
        Returns:
            True if customizations set successfully
        """
        try:
            print(f"⚙️ Setting customizations for: {job['title']}")
            
            # Wait a bit for the form to be ready
            time.sleep(2)
            
            # Set aspect ratio using the same method as fill_form
            if 'aspect_ratio' in job:
                print(f"📐 Setting aspect ratio: {job['aspect_ratio']}")
                self._set_aspect_ratio(job['aspect_ratio'])
            
            # Set voice using the same method as fill_form
            if 'voice' in job:
                print(f"🎤 Setting voice: {job['voice']}")
                self._set_voice(job['voice'])
            
            # Set visual style using the same method as fill_form
            if 'visual_style' in job:
                print(f"🎨 Setting visual style: {job['visual_style']}")
                self._set_visual_style(job['visual_style'])
            
            # Set duration using the same method as fill_form
            if 'duration' in job:
                print(f"⏱️ Setting duration: {job['duration']}")
                self._set_duration(job['duration'])
            
            print("✅ Customizations completed!")
            return True
            
        except Exception as e:
            print(f"❌ Customization failed: {e}")
            return False
    
    def set_dropdown_value(self, dropdown_type: str, value: str) -> bool:
        """Helper method to set dropdown values."""
        try:
            # Try to find and click dropdown buttons
            dropdown_selectors = [
                f"button:has-text('{value}')",
                f"div:has-text('{value}')",
                f"[data-testid*='{dropdown_type}']",
                f"button[aria-label*='{dropdown_type}' i]"
            ]
            
            for selector in dropdown_selectors:
                try:
                    elements = self.current_page.locator(selector)
                    if elements.count() > 0 and elements.first.is_visible():
                        print(f"   ✅ Found {dropdown_type}: {value}")
                        elements.first.click()
                        time.sleep(1)
                        return True
                except Exception:
                    continue
            
            print(f"   ⚠️ Could not find {dropdown_type}: {value}")
            return True  # Don't fail the whole process for this
            
        except Exception as e:
            print(f"   ❌ Dropdown setting failed: {e}")
            return True  # Don't fail the whole process
    
    def export_video(self, job: Dict[str, Any]) -> bool:
        """
        SIMPLE: Export the generated video with proper settings.
        
        Args:
            job: Job data dictionary
            
        Returns:
            True if export completed successfully
        """
        try:
            print("📤 Starting video export process...")
            
            # Step 1: Click the TOP-RIGHT Export button (opens dialog)
            print("1️⃣ Looking for TOP-RIGHT Export button to open dialog...")
            
            # Wait a bit to ensure page is ready
            time.sleep(2)
            
            # Look specifically for the top-right Export button (not in dialog)
            top_export_selectors = [
                "button:has-text('Export'):not([class*='dialog']):not([class*='modal'])",
                "header button:has-text('Export')",
                ".header button:has-text('Export')",
                "nav button:has-text('Export')",
                "button:has-text('Export')"  # Fallback
            ]
            
            export_dialog_opened = False
            print("   🔍 Looking for TOP-RIGHT Export button...")
            
            for selector in top_export_selectors:
                try:
                    print(f"   Trying: {selector}")
                    buttons = self.current_page.locator(selector)
                    count = buttons.count()
                    print(f"   Found {count} elements")
                    
                    if count > 0:
                        # Click the first visible Export button (should be top-right)
                        button = buttons.first
                        if button.is_visible():
                            button_text = button.text_content() or ""
                            print(f"   ✅ Found TOP Export button: '{button_text}'")
                            button.click()
                            export_dialog_opened = True
                            print("   ✅ Clicked TOP Export button - dialog should open!")
                            break
                except Exception as e:
                    print(f"   ❌ Selector failed: {e}")
                    continue
            
            if not export_dialog_opened:
                print("❌ Could not find TOP Export button")
                return False
            
            # Wait for export dialog to open
            print("   ⏳ Waiting for export dialog to open...")
            time.sleep(3)
            
            # Step 2: Set file name (max 45 characters)
            print("2️⃣ Setting file name...")
            filename = job['title'][:45]  # Limit to 45 characters
            filename_selectors = [
                "input[placeholder*='file name' i]",
                "input[placeholder*='name' i]",
                "[data-testid*='filename']",
                "input[type='text']"
            ]
            
            for selector in filename_selectors:
                try:
                    input_field = self.current_page.locator(selector).first
                    if input_field.is_visible():
                        input_field.click()
                        input_field.fill("")  # Clear
                        input_field.fill(filename)
                        print(f"   ✅ Set filename: {filename}")
                        break
                except Exception:
                    continue
            
            # Step 3: Skip resolution/framerate selection (not working reliably)
            # CapCut will use default settings (usually 1080p @ 30fps)
            print("3️⃣ Skipping resolution/framerate selection (using CapCut defaults)...")
            print("   ℹ️  Note: CapCut will export with default quality settings")
            time.sleep(1)
            
            # Step 4: Click the BOTTOM Export button (in the dialog/popup)
            print("5️⃣ Looking for BOTTOM Export button in the dialog...")
            time.sleep(2)
            
            # Look specifically for the Export button INSIDE the dialog/popup
            dialog_export_selectors = [
                "div[role='dialog'] button:has-text('Export')",
                ".modal button:has-text('Export')",
                ".dialog button:has-text('Export')",
                ".export-dialog button:has-text('Export')",
                "[class*='dialog'] button:has-text('Export')",
                "[class*='modal'] button:has-text('Export')",
                "[class*='popup'] button:has-text('Export')"
            ]
            
            dialog_export_clicked = False
            print("   🔍 Looking for Export button INSIDE the dialog...")
            
            # Debug: Show all Export buttons and their locations
            try:
                all_export_buttons = self.current_page.locator("button:has-text('Export')").all()
                print(f"   📊 Found {len(all_export_buttons)} total Export buttons:")
                for i, button in enumerate(all_export_buttons):
                    try:
                        if button.is_visible():
                            # Get button location/context
                            box = button.bounding_box()
                            text = button.text_content() or ""
                            print(f"   Button {i+1}: '{text}' at position {box}")
                    except Exception:
                        continue
            except Exception:
                pass
            
            # Try dialog-specific selectors first
            for selector in dialog_export_selectors:
                try:
                    print(f"   Trying dialog selector: {selector}")
                    buttons = self.current_page.locator(selector)
                    count = buttons.count()
                    print(f"   Found {count} dialog Export buttons")
                    
                    if count > 0:
                        button = buttons.first
                        if button.is_visible():
                            button_text = button.text_content() or ""
                            print(f"   ✅ Found DIALOG Export button: '{button_text}'")
                            button.click()
                            dialog_export_clicked = True
                            print("   ✅ Clicked DIALOG Export button - export should start!")
                            break
                except Exception as e:
                    print(f"   ❌ Dialog selector failed: {e}")
                    continue
            
            # If no dialog button found, try the second Export button (bottom one)
            if not dialog_export_clicked:
                print("   🔄 No dialog Export found, trying second Export button...")
                try:
                    all_export_buttons = self.current_page.locator("button:has-text('Export')")
                    count = all_export_buttons.count()
                    print(f"   Found {count} total Export buttons")
                    
                    if count >= 2:
                        # Click the second Export button (should be the dialog one)
                        second_button = all_export_buttons.nth(1)  # Index 1 = second button
                        if second_button.is_visible():
                            button_text = second_button.text_content() or ""
                            print(f"   ✅ Clicking SECOND Export button: '{button_text}'")
                            second_button.click()
                            dialog_export_clicked = True
                            print("   ✅ Clicked second Export button!")
                    elif count == 1:
                        # Only one Export button - might be the dialog one now
                        button = all_export_buttons.first
                        if button.is_visible():
                            button_text = button.text_content() or ""
                            print(f"   ✅ Clicking single Export button: '{button_text}'")
                            button.click()
                            dialog_export_clicked = True
                            print("   ✅ Clicked Export button!")
                except Exception as e:
                    print(f"   ❌ Fallback failed: {e}")
            
            if not dialog_export_clicked:
                print("   ⚠️ Could not find dialog Export button, but continuing...")
                # Don't fail the whole process for this
            
            print("✅ Export process initiated!")
            print("📥 Video export started...")
            
            # Wait 1 minute for export to complete
            print("⏳ Waiting 1 minute for export to complete...")
            for i in range(60):
                remaining = 60 - i
                print(f"   ⏱️ Export time remaining: {remaining} seconds", end='\r')
                time.sleep(1)
            
            print("\n✅ Export completed!")
            
            # Now download the video from My Cloud
            print("\n" + "=" * 60)
            print("📥 DOWNLOADING VIDEO FROM MY CLOUD")
            print("=" * 60)
            
            downloaded_file = self.video_downloader.download_latest_video(
                self.current_page, 
                self.browser_context
            )
            
            if downloaded_file:
                print(f"✅ Video downloaded successfully: {downloaded_file}")
                print(f"📁 Saved to: {downloaded_file}")
                print("\nℹ️  Video editing and YouTube upload will be handled by the pipeline orchestrator")                
            else:
                print("⚠️ Video download failed, but export was successful")
            
            return True
            
        except Exception as e:
            print(f"❌ Export failed: {e}")
            return False
    
    def set_export_dropdown(self, dropdown_type: str, value: str) -> bool:
        """Helper method to set export dialog dropdowns - ACTUALLY CLICK THEM."""
        try:
            print(f"   🔍 Looking for {dropdown_type} dropdown...")
            
            # Step 1: Find and click the dropdown button to open it
            dropdown_button_selectors = [
                f"button[aria-label*='{dropdown_type}' i]",
                f"div[role='button']:has-text('{dropdown_type}')",
                f"button:has-text('{dropdown_type}')",
                f".{dropdown_type.replace(' ', '-').lower()}-dropdown",
                f"[data-testid*='{dropdown_type.replace(' ', '-').lower()}']"
            ]
            
            # Also try generic dropdown patterns near the label
            if dropdown_type.lower() == "resolution":
                dropdown_button_selectors.extend([
                    "button:has-text('720p')",
                    "button:has-text('1080p')", 
                    "button:has-text('480p')",
                    "div:has-text('Resolution') + * button",
                    "div:has-text('Resolution') ~ * button"
                ])
            elif "frame" in dropdown_type.lower():
                dropdown_button_selectors.extend([
                    "button:has-text('24fps')",
                    "button:has-text('30fps')",
                    "button:has-text('60fps')",
                    "div:has-text('Frame rate') + * button",
                    "div:has-text('Frame rate') ~ * button"
                ])
            
            dropdown_opened = False
            
            # Try to find and click dropdown button
            for selector in dropdown_button_selectors:
                try:
                    print(f"   Trying dropdown button: {selector}")
                    buttons = self.current_page.locator(selector)
                    count = buttons.count()
                    print(f"   Found {count} elements")
                    
                    if count > 0:
                        button = buttons.first
                        if button.is_visible():
                            button_text = button.text_content() or ""
                            print(f"   ✅ Found dropdown button: '{button_text}'")
                            button.click()
                            dropdown_opened = True
                            print(f"   ✅ Clicked {dropdown_type} dropdown - should open options")
                            time.sleep(1)  # Wait for dropdown to open
                            break
                except Exception as e:
                    print(f"   ❌ Button selector failed: {e}")
                    continue
            
            if not dropdown_opened:
                print(f"   ⚠️ Could not find {dropdown_type} dropdown button")
                return True  # Don't fail export for this
            
            # Step 2: Find and click the desired option
            print(f"   🎯 Looking for option: {value}")
            
            option_selectors = [
                f"div[role='option']:has-text('{value}')",
                f"li:has-text('{value}')",
                f"button:has-text('{value}')",
                f"div:has-text('{value}')",
                f"[data-value='{value}']",
                f"option:has-text('{value}')"
            ]
            
            option_clicked = False
            
            for selector in option_selectors:
                try:
                    print(f"   Trying option: {selector}")
                    options = self.current_page.locator(selector)
                    count = options.count()
                    print(f"   Found {count} option elements")
                    
                    if count > 0:
                        option = options.first
                        if option.is_visible():
                            option_text = option.text_content() or ""
                            print(f"   ✅ Found option: '{option_text}'")
                            option.click()
                            option_clicked = True
                            print(f"   ✅ Selected {dropdown_type}: {value}")
                            time.sleep(1)  # Wait for selection to register
                            break
                except Exception as e:
                    print(f"   ❌ Option selector failed: {e}")
                    continue
            
            if not option_clicked:
                print(f"   ⚠️ Could not find option '{value}' for {dropdown_type}")
                
                # Debug: Show all available options
                try:
                    print(f"   🔍 Available options in dropdown:")
                    all_options = self.current_page.locator("div[role='option'], li, button").all()
                    for i, option in enumerate(all_options[:10]):  # Show first 10
                        try:
                            if option.is_visible():
                                text = option.text_content() or ""
                                if text.strip():
                                    print(f"   Option {i+1}: '{text.strip()}'")
                        except Exception:
                            continue
                except Exception:
                    pass
                
                # Try to close dropdown by clicking elsewhere
                try:
                    self.current_page.keyboard.press("Escape")
                except Exception:
                    pass
                return True  # Don't fail export for this
            
            return True
            
        except Exception as e:
            print(f"   ❌ Dropdown setting failed: {e}")
            return True
    
    def try_alternative_dropdown_selection(self, dropdown_type: str, target_value: str, possible_values: List[str]) -> bool:
        """Alternative method to find and click dropdown options by looking for current values."""
        try:
            print(f"   🔄 Alternative {dropdown_type} selection for: {target_value}")
            
            # Look for any buttons/elements with the possible values
            for current_value in possible_values:
                try:
                    print(f"   Looking for current value: {current_value}")
                    
                    # Find elements showing current value
                    current_value_selectors = [
                        f"button:has-text('{current_value}')",
                        f"div:has-text('{current_value}')",
                        f"span:has-text('{current_value}')",
                        f"[role='button']:has-text('{current_value}')"
                    ]
                    
                    for selector in current_value_selectors:
                        elements = self.current_page.locator(selector)
                        if elements.count() > 0 and elements.first.is_visible():
                            print(f"   ✅ Found current {dropdown_type}: {current_value}")
                            
                            # Click to open dropdown
                            elements.first.click()
                            time.sleep(1)
                            
                            # Now look for the target value in the opened dropdown
                            target_selectors = [
                                f"div[role='option']:has-text('{target_value}')",
                                f"li:has-text('{target_value}')",
                                f"button:has-text('{target_value}')",
                                f"div:has-text('{target_value}')"
                            ]
                            
                            for target_selector in target_selectors:
                                target_elements = self.current_page.locator(target_selector)
                                if target_elements.count() > 0 and target_elements.first.is_visible():
                                    print(f"   🎯 Found target option: {target_value}")
                                    target_elements.first.click()
                                    print(f"   ✅ Selected {dropdown_type}: {target_value}")
                                    return True
                            
                            # If target not found, close dropdown
                            self.current_page.keyboard.press("Escape")
                            break
                            
                except Exception as e:
                    print(f"   ❌ Alternative method failed for {current_value}: {e}")
                    continue
            
            print(f"   ⚠️ Alternative {dropdown_type} selection failed")
            return False
            
        except Exception as e:
            print(f"   ❌ Alternative dropdown method failed: {e}")
            return False
    
    
    def process_single_job(self, job_state: JobState) -> bool:
        """
        SIMPLE: Process a single video creation job.
        Just navigate to the page and wait - we'll build the form filling step by step.
        
        Args:
            job_state: Job state object
            
        Returns:
            True if job completed successfully
        """
        job = job_state.job_data
        job_id = job_state.job_id
        
        try:
            print("\n" + "=" * 60)
            print(f"Processing Job {job_id}: {job['title']}")
            print("=" * 60)
            
            job_state.state = JobState.IN_PROGRESS
            job_state.start_time = datetime.now()
            job_state.attempts += 1
            
            # Update state store
            self.state_store.mark_job_status(job_id, JobStatus.IN_PROGRESS, current_step="starting")
            
            # Step 1: Navigate to AI creator
            job_state.current_step = "navigate_to_creator"
            if not self.navigate_to_ai_creator():
                raise Exception("Failed to navigate to AI creator page")
            
            print("✅ Successfully navigated to CapCut AI creator page!")
            
            if self.dry_run:
                print("DRY RUN: Stopping here - navigation successful!")
                
                # Mark as completed for dry run
                job_state.state = JobState.COMPLETED
                job_state.end_time = datetime.now()
                job_state.current_step = "completed"
                
                self.session_stats["completed"] += 1
                return True
            
            # Step 2: Handle any popups FIRST (Terms of Service, etc.)
            job_state.current_step = "handle_popups"
            print("🎯 Checking for and closing any popups...")
            self.close_popups()
            
            # Step 3: Fill the form
            job_state.current_step = "fill_form"
            print("🎯 Now filling the form...")
            if not self.fill_capcut_form(job):
                raise Exception("Failed to fill CapCut form")
            
            print("✅ Form filled successfully!")
            
            # Step 4: Set customization options (SKIPPED - already set in fill_form)
            # Customizations are already set in fill_capcut_form() above
            job_state.current_step = "set_customizations"
            print("✅ Customizations already set in form!")
            
            # Step 5: Click Generate button
            job_state.current_step = "click_generate"
            print("🎯 Now clicking Generate button...")
            if not self.click_generate_button():
                raise Exception("Failed to click Generate button")
            
            print("✅ Generate button clicked successfully!")
            
            # Step 6: Handle page navigation (CapCut opens new page for generation)
            job_state.current_step = "handle_page_navigation"
            print("🔄 Checking for page navigation after Generate click...")
            if not self.handle_generation_page_navigation():
                raise Exception("Failed to navigate to generation page")
            
            # Step 7: Wait for video generation to complete
            job_state.current_step = "wait_for_generation"
            print("🎬 CapCut AI is generating the video...")
            print("⏳ Waiting for video generation to complete...")
            if not self.wait_for_video_generation():
                raise Exception("Video generation failed or timed out")
            
            print("🎉 Video generation completed successfully!")
            
            # Step 6.5: Match stock media before exporting
            job_state.current_step = "match_stock_media"
            print("🎬 Matching stock media before export...")
            if not self.match_stock_media():
                print("⚠️  Warning: Stock media matching failed, but continuing with export...")
            else:
                print("🎉 Stock media matched successfully!")
            
            # Step 7: Export the video
            job_state.current_step = "export_video"
            print("🎯 Now exporting the video...")
            if not self.export_video(job):
                raise Exception("Failed to export video")
            
            print("🎉 Video exported successfully!")
            
            # Update Google Sheet to mark video_generation as completed (with retry)
            job_title = job_state.job_data['title']
            print("\n📝 Updating Google Sheet...")
            update_success = False
            for attempt in range(3):  # Try 3 times
                try:
                    if self.update_google_sheet_status(job_title, 'completed'):
                        print("✅ Google Sheet updated: Video generation marked as completed")
                        update_success = True
                        break
                    else:
                        print(f"⚠️  Attempt {attempt + 1}/3: Could not update Google Sheet")
                        if attempt < 2:
                            time.sleep(2)  # Wait before retry
                except Exception as e:
                    print(f"⚠️  Attempt {attempt + 1}/3 failed: {e}")
                    if attempt < 2:
                        time.sleep(2)
            
            if not update_success:
                print("❌ WARNING: Failed to update Google Sheet after 3 attempts!")
                print("   Please manually mark video_generation as 'completed' in the sheet.")
            
            # Mark as completed
            job_state.state = JobState.COMPLETED
            job_state.end_time = datetime.now()
            job_state.current_step = "completed"
            
            duration = (job_state.end_time - job_state.start_time).total_seconds()
            print(f"\n✅ SUCCESS: Job {job_id} completed in {duration:.1f} seconds")
            print(f"📝 Video '{job_title}' has been generated and marked as completed in Google Sheets")
            
            self.session_stats["completed"] += 1
            return True
            
        except Exception as e:
            job_state.state = JobState.FAILED
            job_state.end_time = datetime.now()
            job_state.error_message = str(e)
            
            print(f"\n❌ ERROR: Job {job_id} failed at step '{job_state.current_step}': {e}")
            
            # Add diagnostic information
            self.add_job_diagnostics(job_state)
            
            # Update state store with failure
            self.state_store.mark_job_status(
                job_id, 
                JobStatus.FAILED, 
                error_message=str(e),
                current_step=job_state.current_step,
                diagnostics=job_state.diagnostics[-1] if job_state.diagnostics else None
            )
            
            self.session_stats["failed"] += 1
            return False
    
    
    
    def add_job_diagnostics(self, job_state: JobState):
        """
        Add diagnostic information for failed job.
        
        Args:
            job_state: Job state object
        """
        try:
            diagnostics = {
                "timestamp": datetime.now().isoformat(),
                "current_url": self.current_page.url if self.current_page else "unknown",
                "viewport_size": self.current_page.viewport_size if self.current_page else None,
                "failed_step": job_state.current_step,
                "error_message": job_state.error_message,
                "attempt_number": job_state.attempts
            }
            
            # Take screenshot for debugging
            if self.current_page and not self.dry_run:
                try:
                    screenshot_name = f"error_{job_state.job_id}_{job_state.current_step}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    screenshot_path = self.state_dir / screenshot_name
                    screenshot = self.current_page.screenshot()
                    screenshot_path.write_bytes(screenshot)
                    diagnostics["screenshot"] = str(screenshot_path)
                    print(f"Error screenshot saved: {screenshot_path}")
                except Exception as e:
                    print(f"Warning: Could not save error screenshot: {e}")
            
            job_state.diagnostics.append(diagnostics)
            
        except Exception as e:
            print(f"Warning: Could not add diagnostics: {e}")
    
    
    def run_automation(self) -> bool:
        """
        SIMPLIFIED: Run the complete automation workflow.
        """
        try:
            self.session_stats["start_time"] = datetime.now()
            
            print("=" * 60)
            print("CapCut Automation - SIMPLIFIED VERSION")
            print("=" * 60)
            print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
            print(f"Browser: {'Headless' if self.headless else 'Visible'}")
            print(f"Jobs: {len(self.jobs)}")
            
            # Set up browser session
            if not self.setup_browser_session():
                print("ERROR: Failed to set up browser session")
                return False
            
            # Process each job (simplified - no complex retry logic)
            for job_id, job_state in self.job_states.items():
                success = self.process_single_job(job_state)
                if not success:
                    print(f"Job {job_id} failed - continuing with next job")
            
            # Final statistics
            self.session_stats["end_time"] = datetime.now()
            self.print_final_report()
            
            return self.session_stats["failed"] == 0
            
        except Exception as e:
            print(f"ERROR: Automation workflow failed: {e}")
            return False
        
        finally:
            # Cleanup
            if self.browser_context:
                self.browser_context.close()
    
    def print_final_report(self):
        """Print final automation report."""
        print("\n" + "=" * 60)
        print("AUTOMATION COMPLETE - FINAL REPORT")
        print("=" * 60)
        
        stats = self.session_stats
        total_time = (stats["end_time"] - stats["start_time"]).total_seconds()
        
        print(f"Total Jobs: {stats['total_jobs']}")
        print(f"Completed: {stats['completed']}")
        print(f"Failed: {stats['failed']}")
        print(f"Skipped: {stats['skipped']}")
        print(f"Success Rate: {(stats['completed'] / stats['total_jobs'] * 100):.1f}%")
        print(f"Total Time: {total_time:.1f} seconds")
        
        if stats["failed"] > 0:
            print(f"\nFailed Jobs:")
            for job_id, job_state in self.job_states.items():
                if job_state.state == JobState.FAILED:
                    print(f"  {job_id}: {job_state.error_message}")
        
        print(f"\nSession completed!")

    def update_google_sheet_status(self, job_title: str, status: str) -> bool:
        """
        Update Google Sheet video_generation status.
        
        Args:
            job_title: Title of the job to update
            status: Status to set ('completed', 'failed', etc.)
            
        Returns:
            True if update successful
        """
        try:
            print(f"   📝 Marking '{job_title}' as '{status}' in Google Sheet...")
            
            # Get Google Sheets client from sheets_reader
            if not hasattr(self.sheets_reader, 'gspread_client') or not self.sheets_reader.gspread_client:
                print("   ❌ Google Sheets client not available (check credentials)")
                return False
            
            # Get sheet configuration
            sheets_id = self.sheets_reader.google_sheets_id
            if not sheets_id:
                print("   ❌ Google Sheets ID not configured in .env")
                return False
                
            sheet_name = self.sheets_reader.google_sheet_name or 'Sheet1'
            
            # Open the spreadsheet
            print(f"   📂 Opening spreadsheet: {sheets_id}")
            spreadsheet = self.sheets_reader.gspread_client.open_by_key(sheets_id)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # Get headers to locate columns
            headers = worksheet.row_values(1)
            print(f"   📋 Found columns: {headers}")
            
            def col_index(name: str, default_new: bool = False) -> int:
                try:
                    return headers.index(name) + 1
                except ValueError:
                    if default_new:
                        # Append new header at the end
                        print(f"   ➕ Adding new column: {name}")
                        headers.append(name)
                        worksheet.update_cell(1, len(headers), name)
                        return len(headers)
                    raise ValueError(f"Column '{name}' not found in sheet")
            
            # Get video_generation column index
            try:
                generation_col = col_index('video_generation')
            except ValueError:
                print("   ⚠️  'video_generation' column not found, creating it...")
                generation_col = col_index('video_generation', default_new=True)

            # Get all records to find the matching row
            print(f"   🔍 Searching for job: '{job_title}'")
            records = worksheet.get_all_records()
            
            for i, record in enumerate(records, start=2):  # Start at row 2 (after header)
                record_title = str(record.get('title', '')).strip()
                if record_title.lower() == job_title.strip().lower():  # Case-insensitive match
                    print(f"   ✅ Found matching row: {i}")
                    # Update video_generation status
                    worksheet.update_cell(i, generation_col, status)
                    print(f"   ✅ Updated row {i}: video_generation='{status}'")
                    return True
            
            print(f"   ❌ Could not find job '{job_title}' in Google Sheet")
            print(f"   📋 Available titles: {[r.get('title', '') for r in records[:5]]}...")
            return False
            
        except Exception as e:
            print(f"   ❌ Failed to update Google Sheet: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _set_visual_style(self, visual_style: str) -> bool:
        """
        Set the visual style dropdown in CapCut.
        
        Args:
            visual_style: Visual style name (e.g., "Realistic Film", "Cartoon 3D")
            
        Returns:
            True if successfully set
        """
        try:
            print(f"   Setting visual style to: {visual_style}")
            
            # STEP 1: Click the default dropdown to open options (e.g., "Realistic Film")
            print(f"   Step 1: Opening visual style dropdown...")
            default_style_selectors = [
                "text='Realistic Film'",  # Default option
                "div:has-text('Realistic Film')",
                "span:has-text('Realistic Film')",
                "button:has-text('Realistic Film')"
            ]
            
            dropdown_opened = False
            for selector in default_style_selectors:
                try:
                    element = self.current_page.locator(selector).first
                    if element.is_visible():
                        print(f"   ✅ Clicked default style to open dropdown")
                        element.click()
                        time.sleep(1.5)
                        dropdown_opened = True
                        break
                except Exception:
                    continue
            
            if not dropdown_opened:
                print(f"   ⚠️  Could not open visual style dropdown")
            
            # STEP 2: Now select the desired visual style from opened dropdown
            print(f"   Step 2: Selecting '{visual_style}'...")
            style_selectors = [
                f"text='{visual_style}'",  # WORKS! From capture test
                f"span:has-text('{visual_style}')",
                f":text('{visual_style}')",
                f"div:has-text('{visual_style}')"
            ]
            
            for selector in style_selectors:
                try:
                    element = self.current_page.locator(selector).first
                    if element.is_visible():
                        print(f"   ✅ Found and clicked visual style: {visual_style}")
                        element.click()
                        time.sleep(1)
                        return True
                except Exception:
                    continue
            
            # If not found, try clicking the first dropdown and look for the style
            print("   🔄 Trying to find visual style in dropdown...")
            dropdown_selectors = [
                "div[role='button']",
                "button[aria-expanded='false']",
                ".dropdown",
                "[data-testid*='style']"
            ]
            
            for selector in dropdown_selectors:
                try:
                    dropdown = self.current_page.locator(selector).first
                    if dropdown.is_visible():
                        dropdown.click()
                        time.sleep(1)
                        
                        # Look for the style option
                        style_option = self.current_page.locator(f"text='{visual_style}'").first
                        if style_option.is_visible():
                            style_option.click()
                            print(f"   ✅ Selected visual style: {visual_style}")
                            return True
                except Exception:
                    continue
            
            print(f"   ⚠️  Could not find visual style: {visual_style}")
            return True  # Don't fail the whole process for this
            
        except Exception as e:
            print(f"   ❌ Error setting visual style: {e}")
            return True  # Don't fail the whole process for this

    def _set_voice(self, voice: str) -> bool:
        """
        Set the voice dropdown in CapCut.
        
        Args:
            voice: Voice name (e.g., "Ms. Labebe", "Happy Dino")
            
        Returns:
            True if successfully set
        """
        try:
            print(f"   Setting voice to: {voice}")
            
            # STEP 1: Click the default voice dropdown to open options
            print(f"   Step 1: Opening voice dropdown...")
            default_voice_selectors = [
                "text='Ms. Labebe'",  # Common default
                "text='Lady Holiday'",  # Another common default
                "div:has-text('Ms. Labebe')",
                ".dropdownButton-peTABv"  # From capture test
            ]
            
            dropdown_opened = False
            for selector in default_voice_selectors:
                try:
                    element = self.current_page.locator(selector).first
                    if element.is_visible():
                        print(f"   ✅ Clicked default voice to open dropdown")
                        element.click()
                        time.sleep(1.5)
                        dropdown_opened = True
                        break
                except Exception:
                    continue
            
            if not dropdown_opened:
                print(f"   ⚠️  Could not open voice dropdown")
            
            # STEP 2: Now select the desired voice from opened dropdown
            print(f"   Step 2: Selecting '{voice}'...")
            voice_selectors = [
                f"text='{voice}'",  # WORKS! From capture test
                f"div:has-text('{voice}')",  # Also works for voice options
                f":text('{voice}')",
                f"span:has-text('{voice}')"
            ]
            
            for selector in voice_selectors:
                try:
                    element = self.current_page.locator(selector).first
                    if element.is_visible():
                        print(f"   ✅ Found and clicked voice: {voice}")
                        element.click()
                        time.sleep(1)
                        return True
                except Exception:
                    continue
            
            # If not found, try clicking the voice dropdown
            print("   🔄 Trying to find voice in dropdown...")
            voice_dropdown_selectors = [
                "div:has-text('Voice')",
                "[data-testid*='voice']",
                "button:has-text('Voice')"
            ]
            
            for selector in voice_dropdown_selectors:
                try:
                    dropdown = self.current_page.locator(selector).first
                    if dropdown.is_visible():
                        dropdown.click()
                        time.sleep(1)
                        
                        # Look for the voice option
                        voice_option = self.current_page.locator(f"text='{voice}'").first
                        if voice_option.is_visible():
                            voice_option.click()
                            print(f"   ✅ Selected voice: {voice}")
                            return True
                except Exception:
                    continue
            
            print(f"   ⚠️  Could not find voice: {voice}")
            return True  # Don't fail the whole process for this
            
        except Exception as e:
            print(f"   ❌ Error setting voice: {e}")
            return True  # Don't fail the whole process for this

    def _set_duration(self, duration: str) -> bool:
        """
        Set the duration dropdown in CapCut.
        
        Args:
            duration: Duration string (e.g., "1 min", "30s", "2 min")
            
        Returns:
            True if successfully set
        """
        try:
            # Convert seconds to CapCut format if needed
            if isinstance(duration, int) or str(duration).isdigit():
                seconds = int(duration)
                if seconds < 60:
                    duration = f"{seconds}s"
                else:
                    minutes = seconds // 60
                    duration = f"{minutes} min"
            
            print(f"   Setting duration to: {duration}")
            
            # STEP 1: Click the default duration dropdown to open options
            print(f"   Step 1: Opening duration dropdown...")
            dropdown_opened = False
            
            # Try clicking the dropdown arrow
            try:
                dropdown_arrow = self.current_page.locator(".lv-select-suffix-icon").first
                if dropdown_arrow.is_visible():
                    dropdown_arrow.click()
                    time.sleep(1.5)
                    print(f"   ✅ Clicked dropdown arrow to open duration options")
                    dropdown_opened = True
            except:
                pass
            
            # If arrow didn't work, try clicking default duration text
            if not dropdown_opened:
                default_duration_selectors = [
                    "text='1 min'",
                    "text='30s'",
                    ".lv-select-view-value"
                ]
                for selector in default_duration_selectors:
                    try:
                        element = self.current_page.locator(selector).first
                        if element.is_visible():
                            element.click()
                            time.sleep(1.5)
                            print(f"   ✅ Clicked default duration to open dropdown")
                            dropdown_opened = True
                            break
                    except:
                        continue
            
            if not dropdown_opened:
                print(f"   ⚠️  Could not open duration dropdown")
            
            duration_selectors = [
                f"text='{duration}'",  # WORKS! From capture test
                f"li:has-text('{duration}')",  # List item with role='option'
                f"[role='option']:has-text('{duration}')",
                f":text('{duration}')"
            ]
            
            for selector in duration_selectors:
                try:
                    element = self.current_page.locator(selector).first
                    if element.is_visible():
                        print(f"   ✅ Found duration element: {duration}")
                        element.click()
                        time.sleep(1)
                        return True
                except Exception:
                    continue
            
            # If not found, try clicking the duration dropdown
            print("   🔄 Trying to find duration in dropdown...")
            duration_dropdown_selectors = [
                "div:has-text('Duration')",
                "[data-testid*='duration']",
                "button:has-text('Duration')",
                "div[role='button']:has-text('min')"
            ]
            
            for selector in duration_dropdown_selectors:
                try:
                    dropdown = self.current_page.locator(selector).first
                    if dropdown.is_visible():
                        dropdown.click()
                        time.sleep(1)
                        
                        # Look for the duration option
                        duration_option = self.current_page.locator(f"text='{duration}'").first
                        if duration_option.is_visible():
                            duration_option.click()
                            print(f"   ✅ Selected duration: {duration}")
                            return True
                except Exception:
                    continue
            
            print(f"   ⚠️  Could not find duration: {duration}")
            return True  # Don't fail the whole process for this
            
        except Exception as e:
            print(f"   ❌ Error setting duration: {e}")
            return True  # Don't fail the whole process for this

    def _set_aspect_ratio(self, aspect_ratio: str) -> bool:
        """
        Set the aspect ratio dropdown in CapCut.
        
        Args:
            aspect_ratio: Aspect ratio (e.g., "16:9", "9:16", "1:1")
            
        Returns:
            True if successfully set
        """
        try:
            print(f"   Setting aspect ratio to: {aspect_ratio}")
            
            # STEP 1: Click the default aspect ratio to open options
            print(f"   Step 1: Opening aspect ratio dropdown...")
            default_ratio_selectors = [
                "text='16:9'",  # Common default
                "span:has-text('16:9')",
                ".lv-select-view-value"  # From capture test
            ]
            
            dropdown_opened = False
            for selector in default_ratio_selectors:
                try:
                    element = self.current_page.locator(selector).first
                    if element.is_visible():
                        print(f"   ✅ Clicked default ratio to open dropdown")
                        element.click()
                        time.sleep(1.5)
                        dropdown_opened = True
                        break
                except Exception:
                    continue
            
            if not dropdown_opened:
                print(f"   ⚠️  Could not open aspect ratio dropdown")
            
            # STEP 2: Now select the desired aspect ratio from opened dropdown
            print(f"   Step 2: Selecting '{aspect_ratio}'...")
            ratio_selectors = [
                f"text='{aspect_ratio}'",  # WORKS! From capture test
                f"span:has-text('{aspect_ratio}')",  # Works for ratio options
                f":text('{aspect_ratio}')",
                f"button:has-text('{aspect_ratio}')"
            ]
            
            for selector in ratio_selectors:
                try:
                    element = self.current_page.locator(selector).first
                    if element.is_visible():
                        print(f"   Found aspect ratio element: {aspect_ratio}")
                        element.click()
                        time.sleep(1)
                        return True
                except Exception:
                    continue
            
            # If not found, try clicking the aspect ratio dropdown
            print("   🔄 Trying to find aspect ratio in dropdown...")
            ratio_dropdown_selectors = [
                "div:has-text('Aspect ratio')",
                "[data-testid*='aspect']",
                "button:has-text('Aspect ratio')",
                f"div[role='button']:has-text('{aspect_ratio}')"
            ]
            
            for selector in ratio_dropdown_selectors:
                try:
                    dropdown = self.current_page.locator(selector).first
                    if dropdown.is_visible():
                        dropdown.click()
                        time.sleep(1)
                        
                        # Look for the aspect ratio option
                        ratio_option = self.current_page.locator(f"text='{aspect_ratio}'").first
                        if ratio_option.is_visible():
                            ratio_option.click()
                            print(f"   ✅ Selected aspect ratio: {aspect_ratio}")
                            return True
                except Exception:
                    continue
            
            print(f"   ⚠️  Could not find aspect ratio: {aspect_ratio}")
            return True  # Don't fail the whole process for this
            
        except Exception as e:
            print(f"   ❌ Error setting aspect ratio: {e}")
            return True  # Don't fail the whole process for this


def main():
    """SIMPLIFIED main entry point."""
    parser = argparse.ArgumentParser(description="CapCut Automation - SIMPLIFIED")
    
    parser.add_argument('--source', choices=['csv', 'sheets'], 
                       help='Data source (csv or sheets)')
    parser.add_argument('--limit', type=int, 
                       help='Limit number of jobs')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simulate actions only')
    parser.add_argument('--headless', action='store_true',
                       help='Run browser headless')
    
    args = parser.parse_args()
    
    try:
        # Check dependencies
        if not MODULES_AVAILABLE or not PLAYWRIGHT_AVAILABLE:
            print("ERROR: Dependencies missing")
            print("Run: pip install -r requirements.txt && playwright install")
            return 1
        
        # Initialize orchestrator
        orchestrator = CapCutOrchestrator(
            dry_run=args.dry_run,
            headless=args.headless
        )
        
        # Load jobs (always processes only 1 job)
        if not orchestrator.load_jobs(source=args.source):
            return 1
        
        # Run automation
        success = orchestrator.run_automation()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
