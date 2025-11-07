#!/usr/bin/env python3
"""
Extract Secrets for GitHub Actions
Helps you copy the content of credential files to create GitHub Secrets
"""

import json
from pathlib import Path

def print_separator():
    print("=" * 70)

def print_secret(name, file_path, description):
    """Print secret information"""
    print_separator()
    print(f"SECRET NAME: {name}")
    print(f"Description: {description}")
    print_separator()
    
    file = Path(file_path)
    
    if not file.exists():
        print(f"❌ File not found: {file_path}")
        print("⚠️  You need to create this file first")
        print()
        return False
    
    try:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Validate JSON
        if file.suffix == '.json':
            json.loads(content)  # Will raise error if invalid
        
        print("✅ File found and valid")
        print()
        print("📋 COPY THIS VALUE TO GITHUB SECRET:")
        print("-" * 70)
        print(content)
        print("-" * 70)
        print()
        print(f"📝 Steps:")
        print(f"  1. Go to GitHub repo → Settings → Secrets and variables → Actions")
        print(f"  2. Click 'New repository secret'")
        print(f"  3. Name: {name}")
        print(f"  4. Value: Copy the content above (between the dashes)")
        print(f"  5. Click 'Add secret'")
        print()
        return True
        
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {file_path}")
        print("⚠️  Please fix the JSON format first")
        print()
        return False
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        print()
        return False

def main():
    print()
    print("🔐 GitHub Actions Secrets Extractor")
    print("=" * 70)
    print()
    print("This script will help you extract the content of credential files")
    print("to create GitHub Secrets for your Actions workflow.")
    print()
    print("⚠️  IMPORTANT: Never commit these files to GitHub!")
    print("   They should only be stored as GitHub Secrets.")
    print()
    
    secrets = [
        {
            "name": "PROVEN_SESSION",
            "file": "state/proven_session.json",
            "description": "CapCut session cookies (login credentials)"
        },
        {
            "name": "YOUTUBE_CREDENTIALS",
            "file": "youtube_credentials.json",
            "description": "YouTube OAuth 2.0 credentials from Google Cloud Console"
        },
        {
            "name": "YOUTUBE_TOKEN",
            "file": "youtube_token.json",
            "description": "YouTube access token (generated after first upload)"
        },
        {
            "name": "GOOGLE_CREDENTIALS",
            "file": "google_credentials.json",
            "description": "Google Sheets API credentials"
        }
    ]
    
    # Check OpenRouter API key from manifest
    manifest_file = Path("manifest.json")
    if manifest_file.exists():
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            
            api_key = manifest.get('openrouter_api_key', '')
            if api_key and api_key.startswith('sk-or-v1-'):
                print_separator()
                print(f"SECRET NAME: OPENROUTER_API_KEY")
                print(f"Description: OpenRouter API key for DeepSeek AI")
                print_separator()
                print("✅ Found in manifest.json")
                print()
                print("📋 COPY THIS VALUE TO GITHUB SECRET:")
                print("-" * 70)
                print(api_key)
                print("-" * 70)
                print()
                print(f"📝 Steps:")
                print(f"  1. Go to GitHub repo → Settings → Secrets and variables → Actions")
                print(f"  2. Click 'New repository secret'")
                print(f"  3. Name: OPENROUTER_API_KEY")
                print(f"  4. Value: {api_key}")
                print(f"  5. Click 'Add secret'")
                print()
        except:
            pass
    
    # Process each secret
    for secret in secrets:
        print_secret(secret["name"], secret["file"], secret["description"])
        input("Press Enter to continue to next secret...")
        print()
    
    print_separator()
    print("✅ All secrets extracted!")
    print_separator()
    print()
    print("📝 Next Steps:")
    print("  1. Create all 5 secrets in GitHub")
    print("  2. Push your code to GitHub (without credential files!)")
    print("  3. Go to Actions tab and run the workflow")
    print()
    print("📚 For detailed setup instructions, see:")
    print("   GITHUB_ACTIONS_SETUP.md")
    print()

if __name__ == '__main__':
    main()
