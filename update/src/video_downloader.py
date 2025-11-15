#!/usr/bin/env python3
"""
Video Downloader Module for CapCut Automation

Downloads exported videos from CapCut My Cloud.
Runs in the same browser session after export completes.
"""

import time
from pathlib import Path
from typing import Optional
from playwright.sync_api import Page, BrowserContext


class VideoDownloader:
    """
    Handles downloading exported videos from CapCut My Cloud.
    Uses existing browser session from main automation.
    """
    
    # CapCut My Cloud URL
    MY_CLOUD_URL = "https://www.capcut.com/my-cloud/7528656611502751805?tab=all&enter_from=page_header"
    
    def __init__(self, download_dir: Optional[Path] = None):
        """
        Initialize video downloader.
        
        Args:
            download_dir: Directory to save downloaded videos (default: project_root/downloads)
        """
        self.project_root = Path(__file__).parent.parent
        self.download_dir = download_dir or (self.project_root / "downloads")
        self.download_dir.mkdir(exist_ok=True)
        
        print(f"📁 Download directory: {self.download_dir}")
    
    def download_latest_video(self, page: Page, context: BrowserContext, delete_after_download: bool = True) -> Optional[Path]:
        """
        Download the latest exported video from CapCut My Cloud.
        
        Args:
            page: Playwright page object (from existing session)
            context: Playwright browser context (from existing session)
            delete_after_download: If True, delete videos from cloud after successful download
            
        Returns:
            Path to downloaded video file, or None if failed
        """
        try:
            print("\n" + "=" * 60)
            print("📥 Starting Video Download Process")
            print("=" * 60)
            
            # Step 1: Navigate to My Cloud
            if not self._navigate_to_my_cloud(page):
                return None
            
            # Step 2: Scroll to exported videos section
            if not self._scroll_to_exported_videos(page):
                return None
            
            # Step 3: Click first exported video
            video_page = self._click_first_video(page, context)
            if not video_page:
                return None
            
            # Step 4: Download the video
            downloaded_file = self._download_video(video_page, context)
            
            # Close the video detail page
            video_page.close()
            
            # Step 5: Delete videos from cloud if download was successful
            if downloaded_file and delete_after_download:
                print("\n" + "=" * 60)
                print("🗑️ Deleting Videos from CapCut Cloud")
                print("=" * 60)
                self._delete_videos_from_cloud(page)
            
            return downloaded_file
            
        except Exception as e:
            print(f"❌ Download process failed: {e}")
            return None
    
    def _navigate_to_my_cloud(self, page: Page) -> bool:
        """Navigate to CapCut My Cloud page."""
        try:
            print(f"\n🚀 Navigating to My Cloud...")
            print(f"URL: {self.MY_CLOUD_URL}")
            
            page.goto(self.MY_CLOUD_URL, timeout=60000)
            
            # Wait for page to load
            print("⏳ Waiting for page to load...")
            time.sleep(5)
            
            # Close any popups that might appear
            self._close_popups(page)
            
            # Verify we're on the correct page
            current_url = page.url
            if "my-cloud" in current_url.lower():
                print("✅ Successfully navigated to My Cloud")
                return True
            else:
                print(f"❌ Unexpected URL: {current_url}")
                return False
                
        except Exception as e:
            print(f"❌ Navigation failed: {e}")
            return False
    
    def _close_popups(self, page: Page) -> None:
        """Close any popups, modals, or dialogs that might be blocking the page."""
        try:
            print("\n🚫 Checking for popups...")
            
            # Common popup close button selectors
            close_selectors = [
                "button[aria-label*='close' i]",
                "button[aria-label*='dismiss' i]",
                "button:has-text('×')",
                "button:has-text('✕')",
                "button:has-text('Close')",
                "[class*='close-button']",
                "[class*='modal-close']",
                "[data-testid*='close']",
                "button[class*='close']",
                ".modal button",
                "[role='dialog'] button"
            ]
            
            popups_closed = 0
            for selector in close_selectors:
                try:
                    elements = page.locator(selector)
                    count = elements.count()
                    
                    if count > 0:
                        # Try to close all visible popups
                        for i in range(count):
                            try:
                                element = elements.nth(i)
                                if element.is_visible():
                                    element.click(timeout=2000)
                                    popups_closed += 1
                                    print(f"   ✅ Closed popup {popups_closed}")
                                    time.sleep(1)
                            except Exception:
                                continue
                except Exception:
                    continue
            
            # Also try pressing Escape key
            try:
                page.keyboard.press("Escape")
                time.sleep(1)
                print("   ✅ Pressed Escape key")
            except Exception:
                pass
            
            if popups_closed > 0:
                print(f"✅ Closed {popups_closed} popup(s)")
            else:
                print("✅ No popups found")
                
        except Exception as e:
            print(f"⚠️ Popup closing failed: {e}")
    
    def _scroll_to_exported_videos(self, page: Page) -> bool:
        """Scroll down to the 'Exported videos' section."""
        try:
            print("\n📜 Scrolling to 'Exported videos' section...")
            
            # Wait for page to fully load
            time.sleep(3)
            
            # Look for the "Exported videos" heading (case-insensitive)
            exported_videos_selectors = [
                "text=/Exported videos/i",
                "h2:has-text('Exported videos')",
                "h3:has-text('Exported videos')",
                "div:has-text('Exported videos')",
                "*:has-text('Exported videos')"
            ]
            
            section_found = False
            for selector in exported_videos_selectors:
                try:
                    print(f"   Trying: {selector}")
                    elements = page.locator(selector)
                    count = elements.count()
                    print(f"   Found {count} elements")
                    
                    if count > 0:
                        element = elements.first
                        if element.is_visible():
                            print(f"   ✅ Found 'Exported videos' section")
                            
                            # Scroll to the section
                            element.scroll_into_view_if_needed()
                            time.sleep(2)
                            
                            # Scroll a bit more to see the videos
                            page.evaluate("window.scrollBy(0, 200)")
                            time.sleep(2)
                            
                            section_found = True
                            break
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
                    continue
            
            if not section_found:
                print("⚠️ Could not find 'Exported videos' heading, scrolling down page...")
                # Fallback: Scroll down in steps
                for i in range(3):
                    page.evaluate(f"window.scrollTo(0, {(i+1) * 500})")
                    time.sleep(1)
                    print(f"   Scrolled to position {(i+1) * 500}px")
            
            print("✅ Scrolled to exported videos section")
            return True
            
        except Exception as e:
            print(f"❌ Scrolling failed: {e}")
            return False
    
    def _click_first_video(self, page: Page, context: BrowserContext) -> Optional[Page]:
        """
        Click the first video in the exported videos section.
        Returns the new page that opens.
        """
        try:
            print("\n🎬 Looking for first exported video...")
            
            # Wait a bit for videos to load
            time.sleep(2)
            
            # Take screenshot for debugging
            try:
                screenshot_path = self.download_dir / "debug_before_click.png"
                page.screenshot(path=str(screenshot_path))
                print(f"   📸 Screenshot saved: {screenshot_path}")
            except Exception:
                pass
            
            # First, try to find elements specifically under "Exported videos" section
            print("   🔍 Looking for videos in 'Exported videos' section...")
            
            # Try to find the parent container of exported videos
            exported_section_found = False
            try:
                # Find the "Exported videos" heading and get its parent container
                heading = page.locator("text=/Exported videos/i").first
                if heading.is_visible():
                    print("   ✅ Found 'Exported videos' heading")
                    exported_section_found = True
            except Exception:
                pass
            
            # Selectors for video thumbnails - based on actual CapCut structure
            video_selectors = [
                # Look for the video title text (Environmental Pollution Video.mp4)
                "text=/Environmental Pollution Video/i",
                "text=/.mp4/",
                # Look for images with video thumbnails (after the Exported videos section)
                "img[src*='cloudfront']",
                "img[src*='capcut']",
                # Look for video preview elements
                "video[poster]",
                # Look for clickable containers with video info
                "div:has-text('01:1')",  # Duration format
                "div:has-text('Exported on')",
                # Look for clickable links
                "a[href*='/view/']",
                # Fallback: any clickable element
                "div[class*='card']",
                "div[class*='item']"
            ]
            
            video_clicked = False
            new_page = None
            
            # Use Playwright's context manager to wait for new page
            print("   📊 Setting up page listener...")
            
            for selector in video_selectors:
                try:
                    print(f"   Trying: {selector}")
                    videos = page.locator(selector)
                    count = videos.count()
                    print(f"   Found {count} elements")
                    
                    if count > 0:
                        # Try to click each element until one works
                        for i in range(min(count, 5)):  # Try first 5 elements
                            try:
                                element = videos.nth(i)
                                if element.is_visible():
                                    print(f"   🎯 Trying element {i+1}...")
                                    
                                    # Use expect_page to catch the new page
                                    with context.expect_page(timeout=20000) as page_info:
                                        element.click()
                                        print(f"   ✅ Clicked element {i+1}!")
                                    
                                    # Get the new page
                                    new_page = page_info.value
                                    video_clicked = True
                                    print(f"   ✅ New page captured: {new_page.url}")
                                    break
                                    
                            except Exception as e:
                                print(f"   ⚠️ Element {i+1} failed: {e}")
                                continue
                        
                        if video_clicked:
                            break
                            
                except Exception as e:
                    print(f"   ❌ Selector failed: {e}")
                    continue
            
            if not video_clicked or not new_page:
                print("❌ Could not find or click first video")
                print("   💡 Try checking the screenshot in downloads/debug_before_click.png")
                return None
            
            # Wait for the new page to fully load (up to 45 seconds)
            print("   ⏳ Waiting for video detail page to fully load...")
            
            # Wait for Download button to appear (dynamic wait up to 45 seconds)
            download_ready = False
            for attempt in range(45):
                try:
                    # Check if Download button is visible
                    download_btn = new_page.locator("button:has-text('Download')").first
                    if download_btn.is_visible():
                        print(f"   ✅ Page loaded after {attempt + 1} seconds!")
                        download_ready = True
                        break
                except:
                    pass
                
                time.sleep(1)
                
                # Show progress every 5 seconds
                if (attempt + 1) % 5 == 0:
                    print(f"   ⏳ Still loading... ({attempt + 1}s)")
            
            if not download_ready:
                print("   ⚠️ Download button not found after 45 seconds, but continuing...")
            
            print(f"   ✅ Video detail page ready!")
            print(f"   📄 URL: {new_page.url}")
            return new_page
                
        except Exception as e:
            print(f"❌ Failed to click video: {e}")
            return None
    
    def _download_video(self, page: Page, context: BrowserContext) -> Optional[Path]:
        """
        Click the Download button and wait for download to complete.
        Uses Playwright's proper download handling with expect_download().
        """
        try:
            print("\n⬇️ Starting download...")
            
            # Wait for page to fully load
            time.sleep(3)
            
            # Get proper filename from page title
            try:
                page_title = page.title()
                print(f"   📄 Page title: {page_title}")
                
                # Extract just the video name (before " | " or " - ")
                if page_title:
                    # Remove common suffixes
                    for separator in [" | ", " - ", " All-in-one video editor"]:
                        if separator in page_title:
                            page_title = page_title.split(separator)[0].strip()
                    
                    # Remove .mp4 if present
                    page_title = page_title.replace(".mp4", "").strip()
                    
                    # Clean the filename - remove invalid characters
                    filename = "".join(c for c in page_title if c.isalnum() or c in (' ', '-', '_'))
                    filename = filename.strip() + ".mp4"
                else:
                    filename = f"capcut_video_{int(time.time())}.mp4"
            except:
                filename = f"capcut_video_{int(time.time())}.mp4"
            
            print(f"   💾 Will save as: {filename}")
            
            # Look for the Download button
            download_selectors = [
                "button:has-text('Download')",
                "a:has-text('Download')",
                "[aria-label*='Download' i]",
                "button[class*='download']",
                ".download-btn"
            ]
            
            download_path = None
            
            # Try to find Download button
            download_button = None
            for selector in download_selectors:
                try:
                    print(f"   🔍 Trying: {selector}")
                    button = page.locator(selector).first
                    
                    if button.is_visible():
                        print(f"   ✅ Found Download button")
                        download_button = button
                        break
                except Exception as e:
                    print(f"   ❌ Selector failed: {e}")
                    continue
            
            if not download_button:
                print("❌ Could not find Download button")
                return None
            
            # PROPER WAY: Use expect_download() BEFORE clicking
            print("   📥 Setting up download listener...")
            with page.expect_download() as download_info:
                download_button.click()
                print("   ✅ Clicked Download button!")
            
            # Get the download object
            download = download_info.value
            print(f"   📦 Download captured!")
            print(f"   📝 Suggested filename: {download.suggested_filename}")
            
            # Save to our download directory with proper name
            download_path = self.download_dir / filename
            download.save_as(str(download_path))
            
            print(f"   ✅ Download saved successfully!")
            print(f"   📁 Full path: {download_path}")
            
            if download_path and download_path.exists():
                file_size = download_path.stat().st_size / (1024 * 1024)  # MB
                print(f"\n✅ Video downloaded successfully!")
                print(f"   📁 Location: {download_path}")
                print(f"   📂 Folder: {self.download_dir}")
                print(f"   📊 Size: {file_size:.2f} MB")
                print(f"\n💡 Open folder: {self.download_dir.absolute()}")
                return download_path
            else:
                print("❌ Download path not found or file doesn't exist")
                print(f"   Expected location: {self.download_dir}")
                
                # List what's in the download directory
                try:
                    files = list(self.download_dir.glob("*"))
                    if files:
                        print(f"   Files in download directory:")
                        for f in files:
                            print(f"     - {f.name}")
                    else:
                        print(f"   Download directory is empty")
                except Exception as e:
                    print(f"   Could not list directory: {e}")
                
                return None
                
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return None
    
    def _delete_videos_from_cloud(self, page: Page) -> bool:
        """
        Delete all exported videos from CapCut cloud after successful download.
        Selects all videos in the 'Exported videos' section and moves them to trash.
        
        Args:
            page: Playwright page object (should be on My Cloud page)
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            print("\n🗑️ Starting cloud cleanup process...")
            
            # Make sure we're on the My Cloud page
            if "my-cloud" not in page.url.lower():
                print("⚠️ Not on My Cloud page, navigating...")
                if not self._navigate_to_my_cloud(page):
                    return False
            
            # Scroll to exported videos section
            print("\n📜 Scrolling to 'Exported videos' section...")
            if not self._scroll_to_exported_videos(page):
                print("⚠️ Could not find exported videos section")
                return False
            
            time.sleep(2)
            
            # Step 1: Hover over first video to reveal checkbox, then click it
            print("\n☑️ Selecting first video to reveal 'Select All' button...")
            
            # Find video thumbnails/cards in the exported videos section
            video_card_selectors = [
                "div[class*='card']",
                "div[class*='item']",
                "div[class*='video']",
                "a[href*='/view/']"
            ]
            
            first_video_selected = False
            
            for selector in video_card_selectors:
                try:
                    print(f"   🔍 Looking for video cards: {selector}")
                    video_cards = page.locator(selector)
                    count = video_cards.count()
                    print(f"   Found {count} video cards")
                    
                    if count > 0:
                        # Try to find and click the first video's checkbox
                        for i in range(min(count, 5)):  # Try first 5 cards
                            try:
                                card = video_cards.nth(i)
                                if card.is_visible():
                                    print(f"   🎯 Hovering over video {i+1} to reveal checkbox...")
                                    # Hover over the card to reveal checkbox
                                    card.hover()
                                    time.sleep(1)
                                    
                                    # Now look for checkbox within or near this card
                                    checkbox_selectors = [
                                        "input[type='checkbox']",
                                        "[role='checkbox']",
                                        "div[class*='checkbox']"
                                    ]
                                    
                                    for cb_selector in checkbox_selectors:
                                        try:
                                            # Look for checkbox near the hovered card
                                            checkbox = page.locator(cb_selector).first
                                            if checkbox.is_visible():
                                                print(f"   ✅ Found checkbox, clicking it...")
                                                checkbox.click()
                                                first_video_selected = True
                                                print(f"   ✅ First video selected!")
                                                time.sleep(2)  # Wait for "(1) selected" button to appear
                                                break
                                        except:
                                            continue
                                    
                                    if first_video_selected:
                                        break
                                        
                            except Exception as e:
                                print(f"   ⚠️ Video {i+1} failed: {e}")
                                continue
                        
                        if first_video_selected:
                            break
                            
                except Exception as e:
                    print(f"   ❌ Selector failed: {e}")
                    continue
            
            if not first_video_selected:
                print("❌ Could not select first video")
                return False
            
            # Step 2: Click the "(1) selected" button to select all videos
            print("\n☑️ Clicking 'Select All' button...")
            
            select_all_selectors = [
                "button:has-text('selected')",
                "div:has-text('selected')",
                "[class*='selected']",
                "button:has-text('(1) selected')"
            ]
            
            all_selected = False
            for selector in select_all_selectors:
                try:
                    print(f"   🔍 Looking for: {selector}")
                    button = page.locator(selector).first
                    if button.is_visible():
                        print(f"   ✅ Found 'Select All' button")
                        button.click()
                        print(f"   ✅ Clicked to select all videos!")
                        all_selected = True
                        time.sleep(2)
                        break
                except Exception as e:
                    print(f"   ❌ Failed: {e}")
                    continue
            
            if not all_selected:
                print("   ⚠️ Could not find 'Select All' button, but continuing...")
                # Continue anyway since we have at least one video selected
            
            # Wait for the "Move to Trash" button to appear
            time.sleep(2)
            
            # Step 2: Click "Move to Trash" button
            print("\n🗑️ Looking for 'Move to Trash' button...")
            
            trash_button_selectors = [
                "button:has-text('Move to Trash')",
                "button:has-text('Move to trash')",
                "button:has-text('Trash')",
                "[aria-label*='trash' i]",
                "[aria-label*='delete' i]",
                "button:has-text('Delete')"
            ]
            
            trash_clicked = False
            for selector in trash_button_selectors:
                try:
                    print(f"   🔍 Trying: {selector}")
                    button = page.locator(selector).first
                    
                    if button.is_visible():
                        print(f"   ✅ Found 'Move to Trash' button")
                        button.click()
                        print(f"   ✅ Clicked 'Move to Trash'!")
                        trash_clicked = True
                        break
                        
                except Exception as e:
                    print(f"   ❌ Selector failed: {e}")
                    continue
            
            if not trash_clicked:
                print("❌ Could not find or click 'Move to Trash' button")
                # Take screenshot for debugging
                try:
                    screenshot_path = self.download_dir / "debug_trash_button.png"
                    page.screenshot(path=str(screenshot_path))
                    print(f"   📸 Screenshot saved: {screenshot_path}")
                except Exception:
                    pass
                return False
            
            # Wait for confirmation dialog (if any)
            time.sleep(2)
            
            # Step 3: Confirm deletion if there's a confirmation dialog
            print("\n✅ Checking for confirmation dialog...")
            
            confirm_selectors = [
                "button:has-text('Confirm')",
                "button:has-text('OK')",
                "button:has-text('Yes')",
                "button:has-text('Delete')",
                "[role='dialog'] button:has-text('Move to Trash')"
            ]
            
            for selector in confirm_selectors:
                try:
                    confirm_button = page.locator(selector).first
                    if confirm_button.is_visible(timeout=2000):
                        print(f"   ✅ Found confirmation button")
                        confirm_button.click()
                        print(f"   ✅ Confirmed deletion!")
                        time.sleep(2)
                        break
                except Exception:
                    continue
            
            print("\n✅ Videos moved to trash successfully!")
            print("   💡 Videos have been deleted from CapCut cloud")
            return True
            
        except Exception as e:
            print(f"❌ Cloud cleanup failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Standalone test - creates browser session and downloads video."""
    import sys
    from pathlib import Path
    
    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent))
    
    from proven_browser import ProvenBrowser
    
    print("=" * 60)
    print("🧪 STANDALONE VIDEO DOWNLOADER TEST")
    print("=" * 60)
    
    try:
        # Create browser session
        print("\n1️⃣ Creating browser session...")
        browser_manager = ProvenBrowser()
        context = browser_manager.create_context_with_proven_session(headless=False)
        
        if not context:
            print("❌ Failed to create browser session")
            return
        
        # Create page
        page = context.new_page()
        print("✅ Browser session ready!")
        
        # Create downloader
        print("\n2️⃣ Initializing video downloader...")
        downloader = VideoDownloader()
        
        # Download video
        print("\n3️⃣ Starting download process...")
        downloaded_file = downloader.download_latest_video(page, context)
        
        if downloaded_file:
            print("\n" + "=" * 60)
            print("✅ SUCCESS!")
            print("=" * 60)
            print(f"📁 Video saved to: {downloaded_file}")
        else:
            print("\n" + "=" * 60)
            print("❌ DOWNLOAD FAILED")
            print("=" * 60)
        
        # Keep browser open for inspection
        print("\n⏸️ Browser will stay open for 10 seconds...")
        import time
        time.sleep(10)
        
        # Cleanup
        browser_manager.close()
        print("✅ Browser closed")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
