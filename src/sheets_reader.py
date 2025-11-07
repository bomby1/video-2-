#!/usr/bin/env python3
"""
Google Sheets Reader Module for CapCut Automation

This module handles reading video job data from Google Sheets (preferred) 
or CSV fallback for local testing. Includes data validation and CLI interface.
"""

import os
import sys
import csv
import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional, Union
from datetime import datetime
from dotenv import load_dotenv

# Optional Google Sheets integration
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

class SheetsReader:
    """
    Handles reading video job data from Google Sheets or CSV fallback.
    Validates and sanitizes data according to CapCut requirements.
    """
    
    # Valid options for validation (matching CapCut interface)
    VALID_VISUAL_STYLES = [
        "Realistic Film", "Cartoon 3D", "Movie", "Photograph", "Whimsical", 
        "Felt Dolls", "Crayon", "Lov", "Cinematic", "Documentary", "Animation",
        "Urban Sketching"  # Added new style
    ]
    VALID_VOICES = [
        "Ms. Labebe", "Lady Holiday", "Happy Dino", "Wacky Puppet", "Ladies' Man",
        "Sassy Witch", "Nice Witch", "Game Host", "Calm Dubing", "Excited Commentator", "male", "female"
    ]
    VALID_ASPECT_RATIOS = ["16:9", "9:16", "1:1", "4:3"]
    VALID_DURATIONS = ["30s", "1 min", "2 min", "3 min", "5 min", "10 min"]
    # Export settings supported by CapCut export dialog
    VALID_RESOLUTIONS = ["360p", "480p", "720p", "1080p", "2k", "4k"]
    VALID_FRAME_RATES = ["24fps", "25fps", "30fps", "50fps", "60fps"]
    VALID_STATUSES = ["pending", "in_progress", "completed", "failed", "skipped"]
    VALID_VIDEO_GENERATION = ["pending", "completed", "failed", ""]  # Video generation status
    
    def __init__(self, env_file: Optional[str] = None):
        """Initialize SheetsReader with environment variables."""
        # Load environment variables
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        self.google_credentials_path = os.getenv('GOOGLE_CREDENTIALS_JSON_PATH')
        self.google_sheets_id = os.getenv('GOOGLE_SHEETS_ID')
        self.google_sheet_name = os.getenv('GOOGLE_SHEET_NAME', None)  # Use first sheet if not specified
        
        # Initialize Google Sheets client if available
        self.gspread_client = None
        self._init_google_sheets()
        
        # Project root for CSV fallback
        self.project_root = Path(__file__).parent.parent
        self.csv_fallback_path = self.project_root / "sheets" / "sample_input.csv"
    
    def _init_google_sheets(self):
        """Initialize Google Sheets client if credentials are available."""
        if not GSPREAD_AVAILABLE:
            return
        
        if not self.google_credentials_path or not self.google_sheets_id:
            return
        
        try:
            # Resolve credentials path: allow absolute or project-root relative
            cred_path = self.google_credentials_path
            if not os.path.isabs(cred_path):
                project_root = Path(__file__).parent.parent
                cred_path = str((project_root / cred_path).resolve())
            if not os.path.exists(cred_path):
                print(f"Warning: Google credentials file not found at {cred_path}")
                return
            
            # Set up Google Sheets authentication with WRITE permissions
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',  # Full read/write access
                'https://www.googleapis.com/auth/drive'  # Full drive access
            ]
            
            credentials = Credentials.from_service_account_file(
                cred_path, 
                scopes=scope
            )
            self.gspread_client = gspread.authorize(credentials)
            
        except Exception as e:
            print(f"Warning: Failed to initialize Google Sheets client: {e}")
            self.gspread_client = None
    
    def _parse_duration(self, duration_str: str) -> int:
        """
        Parse duration string (e.g., '30s', '1m', '2m30s') to seconds.
        
        Args:
            duration_str: Duration string to parse
            
        Returns:
            Duration in seconds
            
        Raises:
            ValueError: If duration format is invalid
        """
        duration_str = duration_str.strip().lower()
        
        # Pattern to match duration formats: 30s, 1m, 2m30s, etc.
        pattern = r'^(?:(\d+)m)?(?:(\d+)s)?$'
        match = re.match(pattern, duration_str)
        
        if not match:
            raise ValueError(f"Invalid duration format: {duration_str}")
        
        minutes = int(match.group(1)) if match.group(1) else 0
        seconds = int(match.group(2)) if match.group(2) else 0
        
        total_seconds = minutes * 60 + seconds
        
        if total_seconds == 0:
            raise ValueError(f"Duration cannot be zero: {duration_str}")
        
        return total_seconds
    
    def _validate_row(self, row_dict: Dict[str, str]) -> Dict[str, Union[str, int]]:
        """
        Validate and sanitize a single row of video job data.
        
        Args:
            row_dict: Raw row data from CSV or Google Sheets
            
        Returns:
            Validated and sanitized row data
            
        Raises:
            ValueError: If validation fails
        """
        # Required fields for video creation
        required_fields = ['title', 'visual_style', 'voice', 'duration', 'aspect_ratio']
        
        # Check for missing required fields
        missing_fields = [field for field in required_fields if field not in row_dict or not row_dict[field]]
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Sanitize and validate each field
        validated_row = {}
        
        # Title validation
        title = str(row_dict['title']).strip().strip('"\'')
        if len(title) == 0:
            raise ValueError("Title cannot be empty")
        if len(title) > 100:
            raise ValueError(f"Title too long (max 100 chars): {title[:50]}...")
        validated_row['title'] = title
        
        # Visual style - NO VALIDATION (CapCut has many options, user can use any)
        visual_style = str(row_dict['visual_style']).strip().strip('"\'')
        validated_row['visual_style'] = visual_style
        
        # Voice - NO VALIDATION (CapCut has many options, user can use any)
        voice = str(row_dict['voice']).strip().strip('"\'')
        validated_row['voice'] = voice
        
        # Duration validation and conversion
        duration_str = str(row_dict['duration']).strip().strip('"\'')
        try:
            duration_seconds = self._parse_duration(duration_str)
            validated_row['duration'] = duration_seconds
        except ValueError as e:
            raise ValueError(f"Invalid duration: {e}")
        
        # Aspect ratio validation
        aspect_ratio = str(row_dict['aspect_ratio']).strip().strip('"\'')
        if aspect_ratio not in self.VALID_ASPECT_RATIOS:
            raise ValueError(f"Invalid aspect_ratio '{aspect_ratio}'. Valid options: {self.VALID_ASPECT_RATIOS}")
        validated_row['aspect_ratio'] = aspect_ratio
        
        # Video generation status (to track if video is already created)
        video_generation = str(row_dict.get('video_generation', '')).strip().strip('"\'')
        if video_generation not in self.VALID_VIDEO_GENERATION:
            video_generation = ''  # Default to empty (pending)
        validated_row['video_generation'] = video_generation
        
        # Optional export settings (Resolution and Frame rate)
        resolution = str(row_dict.get('resolution', '1080p')).strip().strip('"\'')
        if resolution not in self.VALID_RESOLUTIONS:
            resolution = '1080p'
        validated_row['resolution'] = resolution
        
        frame_rate = str(row_dict.get('frame_rate', '60fps')).strip().strip('"\'')
        if frame_rate not in self.VALID_FRAME_RATES:
            frame_rate = '60fps'
        validated_row['frame_rate'] = frame_rate
        
        # Status field removed - no longer needed
        
        validated_row['created_date'] = str(row_dict.get('created_date', '')).strip().strip('"\'')
        validated_row['notes'] = str(row_dict.get('notes', '')).strip().strip('"\'')
        
        return validated_row
    
    def _read_google_sheets(self) -> List[Dict[str, Union[str, int]]]:
        """
        Read data from Google Sheets.
        
        Returns:
            List of validated video job dictionaries
            
        Raises:
            Exception: If Google Sheets reading fails
        """
        if not self.gspread_client:
            raise Exception("Google Sheets client not initialized")
        
        try:
            # Open the spreadsheet
            spreadsheet = self.gspread_client.open_by_key(self.google_sheets_id)
            
            # Get the specified worksheet or first one
            if self.google_sheet_name:
                worksheet = spreadsheet.worksheet(self.google_sheet_name)
            else:
                worksheet = spreadsheet.get_worksheet(0)
            
            # Get all records as dictionaries
            records = worksheet.get_all_records()
            
            if not records:
                raise Exception("No data found in Google Sheet")
            
            # Validate each row
            validated_data = []
            for i, row in enumerate(records, start=2):  # Start at 2 for header row
                try:
                    validated_row = self._validate_row(row)
                    validated_data.append(validated_row)
                except ValueError as e:
                    raise Exception(f"Row {i} validation error: {e}")
            
            return validated_data
            
        except Exception as e:
            raise Exception(f"Failed to read Google Sheets: {e}")
    
    def _read_csv_fallback(self) -> List[Dict[str, Union[str, int]]]:
        """
        Read data from CSV fallback file.
        
        Returns:
            List of validated video job dictionaries
            
        Raises:
            Exception: If CSV reading fails
        """
        if not self.csv_fallback_path.exists():
            raise Exception(f"CSV fallback file not found: {self.csv_fallback_path}")
        
        try:
            validated_data = []
            
            with open(self.csv_fallback_path, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                if not reader.fieldnames:
                    raise Exception("CSV file has no headers")
                
                for i, row in enumerate(reader, start=2):  # Start at 2 for header row
                    try:
                        validated_row = self._validate_row(row)
                        validated_data.append(validated_row)
                    except ValueError as e:
                        raise Exception(f"Row {i} validation error: {e}")
            
            if not validated_data:
                raise Exception("No valid data found in CSV file")
            
            return validated_data
            
        except Exception as e:
            raise Exception(f"Failed to read CSV file: {e}")
    
    def get_video_jobs(self, force_source: Optional[str] = None) -> Dict[str, Union[bool, str, List, List[str]]]:
        """
        Get video jobs from Google Sheets (preferred) or CSV fallback.
        
        Args:
            force_source: Force specific source ("sheets" or "csv")
            
        Returns:
            Dictionary with success status, data source, job data, and any errors/warnings
        """
        result = {
            "success": False,
            "source": None,
            "data": [],
            "errors": [],
            "warnings": []
        }
        
        # Try Google Sheets first (unless CSV is forced)
        if force_source != "csv" and self.gspread_client and self.google_sheets_id:
            try:
                data = self._read_google_sheets()
                result.update({
                    "success": True,
                    "source": "google_sheets",
                    "data": data
                })
                return result
                
            except Exception as e:
                error_msg = f"Google Sheets failed: {e}"
                result["errors"].append(error_msg)
                result["warnings"].append("Falling back to CSV file")
                
                if force_source == "sheets":
                    return result
        
        # Try CSV fallback
        try:
            data = self._read_csv_fallback()
            result.update({
                "success": True,
                "source": "csv_fallback",
                "data": data
            })
            return result
            
        except Exception as e:
            error_msg = f"CSV fallback failed: {e}"
            result["errors"].append(error_msg)
        
        return result
    
    def test_connection(self, verbose: bool = False) -> bool:
        """
        Test connection to data sources and display sample data.
        
        Args:
            verbose: Show detailed information
            
        Returns:
            True if at least one data source works
        """
        print("=" * 60)
        print("CapCut Automation - Sheets Reader Test")
        print("=" * 60)
        
        if verbose:
            print(f"Google Credentials Path: {self.google_credentials_path}")
            print(f"Google Sheets ID: {self.google_sheets_id}")
            print(f"CSV Fallback Path: {self.csv_fallback_path}")
            print(f"Google Sheets Available: {GSPREAD_AVAILABLE}")
            print(f"Google Client Initialized: {self.gspread_client is not None}")
            print("-" * 60)
        
        # Test both sources
        success = False
        
        # Test Google Sheets
        if self.gspread_client and self.google_sheets_id:
            print("Testing Google Sheets connection...")
            try:
                result = self.get_video_jobs(force_source="sheets")
                if result["success"]:
                    print("SUCCESS: Google Sheets connection successful")
                    print(f"  Found {len(result['data'])} video jobs")
                    if result["data"]:
                        print("  Sample job:", result["data"][0])
                    success = True
                else:
                    print("ERROR: Google Sheets connection failed:")
                    for error in result["errors"]:
                        print(f"    {error}")
            except Exception as e:
                print(f"ERROR: Google Sheets test error: {e}")
        else:
            print("WARNING: Google Sheets not configured (missing credentials or sheet ID)")
        
        print()
        
        # Test CSV fallback
        print("Testing CSV fallback...")
        try:
            result = self.get_video_jobs(force_source="csv")
            if result["success"]:
                print("SUCCESS: CSV fallback successful")
                print(f"  Found {len(result['data'])} video jobs")
                if result["data"]:
                    print("  Sample job:", result["data"][0])
                success = True
            else:
                print("ERROR: CSV fallback failed:")
                for error in result["errors"]:
                    print(f"    {error}")
        except Exception as e:
            print(f"ERROR: CSV test error: {e}")
        
        print("-" * 60)
        
        if success:
            print("SUCCESS: At least one data source is working")
        else:
            print("ERROR: No data sources are working")
            print("\nTroubleshooting:")
            print("1. For Google Sheets:")
            print("   - Check GOOGLE_CREDENTIALS_JSON_PATH in .env")
            print("   - Verify service account has access to the sheet")
            print("   - Ensure Google Sheets API is enabled")
            print("2. For CSV fallback:")
            print("   - Verify sheets/sample_input.csv exists")
            print("   - Check CSV format and headers")
        
        return success


def main():
    """CLI entry point for sheets reader."""
    parser = argparse.ArgumentParser(description="CapCut Automation - Sheets Reader")
    parser.add_argument('--test', action='store_true', help='Test connection and show sample data')
    parser.add_argument('--source', choices=['csv', 'sheets'], help='Force specific data source')
    parser.add_argument('--validate-only', action='store_true', help='Only validate data format')
    parser.add_argument('--verbose', action='store_true', help='Show detailed information')
    
    args = parser.parse_args()
    
    # Initialize reader
    reader = SheetsReader()
    
    if args.test:
        success = reader.test_connection(verbose=args.verbose)
        sys.exit(0 if success else 1)
    
    if args.validate_only:
        print("Validating data sources...")
        result = reader.get_video_jobs(force_source=args.source)
        
        if result["success"]:
            print(f"SUCCESS: Validation successful ({result['source']})")
            print(f"  {len(result['data'])} valid video jobs found")
            
            if args.verbose:
                for i, job in enumerate(result['data'], 1):
                    print(f"  Job {i}: {job}")
        else:
            print("ERROR: Validation failed:")
            for error in result["errors"]:
                print(f"  {error}")
            sys.exit(1)
    
    # Default: get and display video jobs
    result = reader.get_video_jobs(force_source=args.source)
    
    if result["success"]:
        print(f"Successfully loaded {len(result['data'])} video jobs from {result['source']}")
        
        if args.verbose:
            for i, job in enumerate(result['data'], 1):
                print(f"Job {i}: {job}")
    else:
        print("Failed to load video jobs:")
        for error in result["errors"]:
            print(f"  {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
