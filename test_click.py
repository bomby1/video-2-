"""
Quick test to verify Playwright JavaScript click works
Run this when you're on the CapCut page with Export button visible
"""
from playwright.sync_api import sync_playwright
import time

def test_clicks():
    print("🧪 Testing Playwright JavaScript Clicks")
    print("=" * 60)
    
    # This will connect to your existing browser
    # Make sure you're on the CapCut page with the Export button visible
    
    with sync_playwright() as p:
        # Connect to existing browser (you need to start it with --remote-debugging-port=9222)
        # Or just use this script independently
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to CapCut (replace with your actual URL)
        input("Press Enter when you're on the CapCut page with Media panel visible...")
        
        print("\n1️⃣ Testing Scenes click...")
        try:
            scenes = page.locator("div:has-text('Scenes')").first
            if scenes.is_visible():
                print("   Found Scenes element")
                scenes.evaluate("el => el.click()")
                print("   ✅ Clicked Scenes (JavaScript)")
                time.sleep(3)
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        
        print("\n2️⃣ Testing Media click...")
        try:
            media = page.locator("div:has-text('Media')").first
            if media.is_visible():
                print("   Found Media element")
                media.evaluate("el => el.click()")
                print("   ✅ Clicked Media (JavaScript)")
                time.sleep(2)
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        
        print("\n3️⃣ Testing Match button click...")
        try:
            match_btn = page.locator("div[class*='match-media-btn']").first
            if match_btn.is_visible():
                print("   Found Match button")
                print(f"   Text: {match_btn.text_content()}")
                match_btn.evaluate("el => el.click()")
                print("   ✅ Clicked Match (JavaScript)")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
        
        input("\nPress Enter to close...")
        browser.close()

if __name__ == "__main__":
    test_clicks()
