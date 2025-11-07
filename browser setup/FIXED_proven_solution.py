#!/usr/bin/env python3
"""
FIXED PROVEN SOLUTION - Fixes session loading and automation issues
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
    Fixed version that properly handles session saving and loading.
    """
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.state_dir = self.project_root / "state"
        self.state_dir.mkdir(exist_ok=True)
        self.session_file = self.state_dir / "proven_session.json"
    
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
    
    def method1_undetected_chromedriver(self):
        """Method 1: Undetected ChromeDriver - Most popular working solution."""
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
            
            # Go to CapCut
            print("📱 Going to CapCut...")
            driver.get("https://www.capcut.com")
            time.sleep(3)
            
            print("\n" + "=" * 60)
            print("MANUAL LOGIN - GOOGLE WON'T DETECT THIS!")
            print("=" * 60)
            print("1. Click 'Sign In' or 'Log In' in the browser")
            print("2. Click 'Continue with Google'")
            print("3. Login to Google (it should work now!)")
            print("4. Complete CapCut login")
            print("5. Wait for CapCut dashboard")
            input("6. Press ENTER when login is complete: ")
            
            # Test workspace
            print("🧪 Testing CapCut workspace...")
            driver.get("https://www.capcut.com/workspace")
            time.sleep(3)
            
            if "login" not in driver.current_url.lower():
                print("✅ CapCut workspace accessible!")
                
                # Test editor
                driver.get("https://www.capcut.com/editor")
                time.sleep(3)
                
                if "login" not in driver.current_url.lower():
                    print("✅ CapCut editor accessible!")
                    
                    # Save cookies for future use
                    print("💾 Saving session cookies...")
                    cookies = driver.get_cookies()
                    
                    # Get additional browser info
                    user_agent = driver.execute_script("return navigator.userAgent;")
                    current_url = driver.current_url
                    
                    session_data = {
                        'method': 'undetected_chromedriver',
                        'cookies': cookies,
                        'user_agent': user_agent,
                        'last_url': current_url,
                        'timestamp': time.time(),
                        'success': True
                    }
                    
                    # Save with error handling
                    try:
                        with open(self.session_file, 'w') as f:
                            json.dump(session_data, f, indent=2)
                        
                        print(f"✅ Session saved successfully!")
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
                else:
                    print("❌ CapCut editor not accessible")
            else:
                print("❌ CapCut workspace not accessible")
            
            driver.quit()
            return False
            
        except Exception as e:
            print(f"❌ Undetected ChromeDriver method failed: {e}")
            return False
    
    def run_automation_with_session(self):
        """Run automation using saved session - FIXED VERSION."""
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
            print(f"🔧 Session method: {method}")
            
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
                    
                    # Go to CapCut first
                    driver.get("https://www.capcut.com")
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
                    
                    # Test access to editor
                    print("🧪 Testing CapCut editor access...")
                    driver.get("https://www.capcut.com/editor")
                    time.sleep(5)
                    
                    current_url = driver.current_url.lower()
                    print(f"📍 Current URL: {driver.current_url}")
                    
                    if "login" not in current_url and "signin" not in current_url:
                        print("✅ CapCut automation ready!")
                        print("🎬 You can now add your automation logic!")
                        print()
                        print("=" * 50)
                        print("AUTOMATION READY - ADD YOUR TASKS HERE")
                        print("=" * 50)
                        print("The browser is logged in and ready.")
                        print("You can now:")
                        print("- Upload videos")
                        print("- Create projects")
                        print("- Apply effects")
                        print("- Export videos")
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
                        
                        # Go to CapCut and add cookies
                        page.goto("https://www.capcut.com")
                        
                        for cookie in session_data['cookies']:
                            try:
                                context.add_cookies([cookie])
                            except:
                                continue
                    else:
                        context = browser.new_context(storage_state=session_data)
                        page = context.new_page()
                    
                    # Test access
                    page.goto("https://www.capcut.com/editor", timeout=60000)
                    time.sleep(3)
                    
                    if "login" not in page.url.lower():
                        print("✅ CapCut automation ready!")
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
    print("🥷 FIXED PROVEN CAPCUT SOLUTIONS")
    print("=" * 70)
    print("Fixed session saving and loading issues!")
    print()
    
    solution = FixedProvenSolution()
    
    print("Choose a method:")
    print("1. 🥷 Undetected ChromeDriver Login (do this first)")
    print("2. 🚀 Run automation with saved session (FIXED)")
    print("3. 🔍 Check saved session status")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        print("\n🥷 Starting undetected ChromeDriver login...")
        success = solution.method1_undetected_chromedriver()
        if success:
            print("\n🎉 SUCCESS! Login completed and session saved!")
            print("Now you can run option 2 for automation!")
        else:
            print("\n❌ Login failed.")
    
    elif choice == "2":
        print("\n🚀 Starting automation with saved session...")
        success = solution.run_automation_with_session()
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
