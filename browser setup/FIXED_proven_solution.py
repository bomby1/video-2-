#!/usr/bin/env python3
"""
FIXED PROVEN SOLUTION - Universal Browser Session Manager
Store and reuse browser sessions for ANY website (CapCut, YouTube, Instagram, etc.)
"""

import os
import sys
import time
import json
from pathlib import Path

# Install required packages if not available
def install_packages():
    """Install required packages for the proven solution."""
    packages = [
        'undetected-chromedriver',
        'selenium',
        'playwright'
    ]
    
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            os.system(f"{sys.executable} -m pip install {package}")

# Try to install packages
install_packages()

try:
    import undetected_chromedriver as uc
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class FixedProvenSolution:
    """
    Universal browser session manager for any website.
    Properly handles session saving and loading.
    """
    
    def __init__(self, website_name="default"):
        self.project_root = Path(__file__).parent
        self.state_dir = self.project_root / "state"
        self.state_dir.mkdir(exist_ok=True)
        self.website_name = website_name.lower().replace(" ", "_")
        self.session_file = self.state_dir / f"{self.website_name}_session.json"
    
    def check_session_file(self):
        """Check if session file exists and is valid."""
        if not self.session_file.exists():
            print("❌ No session file found!")
            return False
        
        try:
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)
            
            # Check if it has required data
            if 'method' in session_data:
                if session_data['method'] == 'undetected_chromedriver':
                    if 'cookies' in session_data and len(session_data['cookies']) > 0:
                        print(f"✅ Valid undetected ChromeDriver session found!")
                        print(f"   Cookies: {len(session_data['cookies'])} saved")
                        return True
                else:
                    if 'cookies' in session_data or 'origins' in session_data:
                        print(f"✅ Valid Playwright session found!")
                        return True
            
            print("⚠️  Session file exists but may be incomplete")
            return False
            
        except Exception as e:
            print(f"❌ Error reading session file: {e}")
            return False
    
    def method1_undetected_chromedriver(self, website_url, test_urls=None):
        """Method 1: Undetected ChromeDriver - Most popular working solution.
        
        Args:
            website_url: Main URL to visit (e.g., "https://www.capcut.com")
            test_urls: List of URLs to test after login (optional)
        """
        if not SELENIUM_AVAILABLE:
            print("❌ Selenium/undetected-chromedriver not available")
            return False
        
        print("🥷 Method 1: Undetected ChromeDriver")
        print("=" * 50)
        print("This is the most popular method that actually works!")
        print()
        
        try:
            # Create undetected Chrome instance
            print("🚀 Starting undetected Chrome...")
            options = uc.ChromeOptions()
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-default-apps")
            
            # This is the magic - undetected chromedriver
            driver = uc.Chrome(options=options)
            
            print("✅ Undetected Chrome started!")
            
            # Go to website
            print(f"📱 Going to {website_url}...")
            driver.get(website_url)
            time.sleep(3)
            
            print("\n" + "=" * 60)
            print("MANUAL LOGIN - AUTOMATION UNDETECTED!")
            print("=" * 60)
            print("1. Complete the login process in the browser")
            print("2. Navigate to any pages you want to test")
            print("3. Make sure you're fully logged in")
            input("4. Press ENTER when login is complete: ")
            
            # Test URLs if provided
            if test_urls:
                for i, test_url in enumerate(test_urls, 1):
                    print(f"🧪 Testing URL {i}/{len(test_urls)}: {test_url}")
                    driver.get(test_url)
                    time.sleep(3)
                    
                    if "login" not in driver.current_url.lower() and "signin" not in driver.current_url.lower():
                        print(f"✅ URL {i} accessible!")
                    else:
                        print(f"⚠️  URL {i} may require login")
            
            # Always save session regardless of test results
            current_url = driver.current_url
            if "login" not in current_url.lower() and "signin" not in current_url.lower():
                print("✅ Session appears valid!")
                    
            
            # Save cookies for future use
            print("💾 Saving session cookies...")
            cookies = driver.get_cookies()
            
            # Get additional browser info
            user_agent = driver.execute_script("return navigator.userAgent;")
            current_url = driver.current_url
            
            session_data = {
                'method': 'undetected_chromedriver',
                'website_url': website_url,
                'website_name': self.website_name,
                'cookies': cookies,
                'user_agent': user_agent,
                'last_url': current_url,
                'test_urls': test_urls or [],
                'timestamp': time.time(),
                'success': True
            }
            
            # Save with error handling
            try:
                with open(self.session_file, 'w') as f:
                    json.dump(session_data, f, indent=2)
                
                print(f"✅ Session saved successfully!")
                print(f"   Website: {self.website_name}")
                print(f"   File: {self.session_file}")
                print(f"   Cookies saved: {len(cookies)}")
                print(f"   User agent: {user_agent[:50]}...")
                
            except Exception as e:
                print(f"❌ Error saving session: {e}")
                driver.quit()
                return False
            
            print("🎉 SUCCESS with undetected ChromeDriver!")
            
            driver.quit()
            return True
            
        except Exception as e:
            print(f"❌ Undetected ChromeDriver method failed: {e}")
            return False
    
    def run_automation_with_session(self, test_url=None):
        """Run automation using saved session - FIXED VERSION.
        
        Args:
            test_url: Optional URL to test after loading session
        """
        print("🔍 Checking saved session...")
        
        if not self.check_session_file():
            print("❌ No valid session found!")
            print("Please run Method 1 first to login and save session!")
            return False
        
        try:
            print("📂 Loading saved session...")
            
            # Load session
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)
            
            method = session_data.get('method', 'playwright')
            website_url = session_data.get('website_url', 'https://www.google.com')
            website_name = session_data.get('website_name', self.website_name)
            
            print(f"🔧 Session method: {method}")
            print(f"🌐 Website: {website_name}")
            
            if method == 'undetected_chromedriver' and SELENIUM_AVAILABLE:
                print("🥷 Using undetected ChromeDriver for automation...")
                
                try:
                    # Create new undetected Chrome instance
                    options = uc.ChromeOptions()
                    options.add_argument("--no-first-run")
                    options.add_argument("--no-default-browser-check")
                    
                    print("🚀 Starting undetected Chrome for automation...")
                    driver = uc.Chrome(options=options)
                    
                    print("✅ Chrome started! Loading session...")
                    
                    # Go to website first
                    driver.get(website_url)
                    time.sleep(2)
                    
                    # Load saved cookies
                    print("🍪 Loading saved cookies...")
                    cookies_loaded = 0
                    for cookie in session_data.get('cookies', []):
                        try:
                            driver.add_cookie(cookie)
                            cookies_loaded += 1
                        except Exception as e:
                            # Some cookies might fail, that's okay
                            continue
                    
                    print(f"✅ Loaded {cookies_loaded} cookies")
                    
                    # Refresh to apply cookies
                    driver.refresh()
                    time.sleep(3)
                    
                    # Test access to specified URL or saved test URLs
                    if test_url:
                        print(f"🧪 Testing access to: {test_url}")
                        driver.get(test_url)
                        time.sleep(5)
                    elif session_data.get('test_urls'):
                        test_url = session_data['test_urls'][0]
                        print(f"🧪 Testing saved URL: {test_url}")
                        driver.get(test_url)
                        time.sleep(5)
                    
                    current_url = driver.current_url.lower()
                    print(f"📍 Current URL: {driver.current_url}")
                    
                    if "login" not in current_url and "signin" not in current_url:
                        print(f"✅ {website_name} automation ready!")
                        print("🎬 You can now add your automation logic!")
                        print()
                        print("=" * 50)
                        print("AUTOMATION READY - ADD YOUR TASKS HERE")
                        print("=" * 50)
                        print("The browser is logged in and ready.")
                        print("You can now perform automated tasks on this website.")
                        print("=" * 50)
                        
                        input("Press ENTER to close browser: ")
                        driver.quit()
                        return True
                    else:
                        print("❌ Session expired or login required")
                        print("Please run Method 1 again to re-login")
                        driver.quit()
                        return False
                        
                except Exception as e:
                    print(f"❌ Error with undetected ChromeDriver automation: {e}")
                    try:
                        driver.quit()
                    except:
                        pass
                    return False
            
            else:
                print("🥷 Using Playwright for automation...")
                
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False)
                    
                    # Load session data
                    if 'cookies' in session_data:
                        # Convert cookies format for Playwright
                        context = browser.new_context()
                        page = context.new_page()
                        
                        # Go to website and add cookies
                        page.goto(website_url)
                        
                        for cookie in session_data['cookies']:
                            try:
                                context.add_cookies([cookie])
                            except:
                                continue
                    else:
                        context = browser.new_context(storage_state=session_data)
                        page = context.new_page()
                    
                    # Test access
                    test_target = test_url or session_data.get('test_urls', [website_url])[0]
                    page.goto(test_target, timeout=60000)
                    time.sleep(3)
                    
                    if "login" not in page.url.lower():
                        print(f"✅ {website_name} automation ready!")
                        print("🎬 Add your automation logic here...")
                        
                        input("Press ENTER to close browser: ")
                        browser.close()
                        return True
                    else:
                        print("❌ Session expired")
                        browser.close()
                        return False
                        
        except Exception as e:
            print(f"❌ Automation failed: {e}")
            return False


def main():
    """Main function with fixed session handling."""
    print("=" * 70)
    print("🥷 UNIVERSAL BROWSER SESSION MANAGER")
    print("=" * 70)
    print("Store and reuse sessions for ANY website!")
    print()
    
    # Get website information
    print("Enter website information:")
    website_name = input("Website name (e.g., CapCut, YouTube, Instagram): ").strip() or "default"
    
    solution = FixedProvenSolution(website_name)
    
    print(f"\n📁 Session file: {solution.session_file.name}")
    print("\nChoose a method:")
    print("1. 🥷 Undetected ChromeDriver Login (do this first)")
    print("2. 🚀 Run automation with saved session (FIXED)")
    print("3. 🔍 Check saved session status")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        website_url = input("\nEnter website URL (e.g., https://www.capcut.com): ").strip()
        if not website_url.startswith('http'):
            website_url = 'https://' + website_url
        
        # Optional: test URLs
        print("\nOptional: Enter test URLs to verify after login (comma-separated, or press ENTER to skip):")
        test_urls_input = input("Test URLs: ").strip()
        test_urls = [url.strip() for url in test_urls_input.split(',') if url.strip()] if test_urls_input else None
        
        print("\n🥷 Starting undetected ChromeDriver login...")
        success = solution.method1_undetected_chromedriver(website_url, test_urls)
        if success:
            print("\n🎉 SUCCESS! Login completed and session saved!")
            print("Now you can run option 2 for automation!")
        else:
            print("\n❌ Login failed.")
    
    elif choice == "2":
        test_url_input = input("\nOptional: Enter URL to test (or press ENTER to use saved): ").strip()
        test_url = test_url_input if test_url_input else None
        
        print("\n🚀 Starting automation with saved session...")
        success = solution.run_automation_with_session(test_url)
        if success:
            print("\n🎉 Automation completed!")
        else:
            print("\n❌ Automation failed. Try login again (option 1).")
    
    elif choice == "3":
        print("\n🔍 Checking session status...")
        if solution.check_session_file():
            print("✅ Session file is valid and ready for automation!")
        else:
            print("❌ No valid session found. Run option 1 first.")
    
    else:
        print("Invalid choice!")
    
    input("\nPress ENTER to exit...")


if __name__ == "__main__":
    main()
