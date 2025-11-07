#!/usr/bin/env python3
"""
YouTube Uploader - Automated video upload with metadata
Uploads edited videos to YouTube with AI-generated metadata
"""

import os
import json
import argparse
from pathlib import Path
from typing import Optional, Dict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google API libraries not installed")


class YouTubeUploader:
    """Upload videos to YouTube with metadata"""
    
    # YouTube API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/youtube.upload',
        'https://www.googleapis.com/auth/youtube.force-ssl'  # Required for captions
    ]
    
    def __init__(self, credentials_file: str = "youtube_credentials.json"):
        """Initialize YouTube uploader"""
        self.project_root = Path(__file__).parent
        self.credentials_file = self.project_root / credentials_file
        self.token_file = self.project_root / "youtube_token.json"
        self.youtube = None
        
        if not GOOGLE_AVAILABLE:
            raise ImportError("Google API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    
    def authenticate(self) -> bool:
        """Authenticate with YouTube API (supports both local and GitHub Actions)"""
        try:
            creds = None
            
            # Load existing token
            if self.token_file.exists():
                logger.info("Loading existing YouTube credentials...")
                creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
            
            # Refresh or get new credentials
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired credentials...")
                    try:
                        creds.refresh(Request())
                        # Save refreshed token
                        with open(self.token_file, 'w') as token:
                            token.write(creds.to_json())
                        logger.info("Token refreshed and saved")
                    except Exception as e:
                        logger.error(f"Token refresh failed: {e}")
                        logger.info("Need to re-authenticate locally")
                        return False
                else:
                    # Interactive OAuth flow (only works locally, not in GitHub Actions)
                    logger.info("Starting OAuth flow (requires browser)...")
                    if not self.credentials_file.exists():
                        logger.error(f"Credentials file not found: {self.credentials_file}")
                        logger.info("Get credentials from: https://console.cloud.google.com/apis/credentials")
                        return False
                    
                    # Check if running in CI/GitHub Actions
                    if os.getenv('CI') or os.getenv('GITHUB_ACTIONS'):
                        logger.error("Cannot run OAuth flow in GitHub Actions!")
                        logger.error("You must authenticate locally first and commit youtube_token.json")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), 
                        self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                    
                    # Save credentials
                    with open(self.token_file, 'w') as token:
                        token.write(creds.to_json())
                    logger.info("✅ Credentials saved for future use")
                    logger.info("⚠️  IMPORTANT: Add youtube_token.json to GitHub Secrets for Actions")
            
            # Build YouTube service
            self.youtube = build('youtube', 'v3', credentials=creds)
            logger.info("✅ YouTube authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def upload_video(
        self, 
        video_path: str,
        metadata_path: Optional[str] = None,
        subtitle_path: Optional[str] = None,
        privacy: str = "private",
        category: str = "22"  # People & Blogs
    ) -> Optional[str]:
        """
        Upload video to YouTube
        
        Args:
            video_path: Path to video file
            metadata_path: Path to .metadata.json file
            subtitle_path: Path to .srt subtitle file
            privacy: Video privacy (private, unlisted, public)
            category: YouTube category ID
            
        Returns:
            Video ID if successful, None otherwise
        """
        if not self.youtube:
            logger.error("Not authenticated. Call authenticate() first.")
            return None
        
        try:
            # Load metadata
            metadata = self._load_metadata(metadata_path, video_path)
            
            # Add hashtags to description
            description_with_hashtags = metadata['description']
            if 'hashtags' in metadata and metadata['hashtags']:
                hashtags_text = '\n\n' + ' '.join(metadata['hashtags'])
                description_with_hashtags += hashtags_text
            
            # Prepare video metadata
            body = {
                'snippet': {
                    'title': metadata['title'],
                    'description': description_with_hashtags,
                    'tags': metadata['tags'],
                    'categoryId': category
                },
                'status': {
                    'privacyStatus': privacy,
                    'selfDeclaredMadeForKids': False
                }
            }
            
            logger.info("=" * 60)
            logger.info("📤 Uploading to YouTube")
            logger.info("=" * 60)
            logger.info(f"Video: {video_path}")
            logger.info(f"Title: {metadata['title']}")
            logger.info(f"Privacy: {privacy}")
            logger.info(f"Tags: {len(metadata['tags'])} tags")
            
            # Upload video
            media = MediaFileUpload(
                video_path,
                mimetype='video/mp4',
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
            
            request = self.youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            
            # Execute upload with progress
            response = None
            logger.info("Uploading...")
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"Upload progress: {progress}%")
            
            video_id = response['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            logger.info("✅ Upload complete!")
            logger.info(f"Video ID: {video_id}")
            logger.info(f"URL: {video_url}")
            
            # Upload subtitles if available
            if subtitle_path and Path(subtitle_path).exists():
                self._upload_subtitles(video_id, subtitle_path)
            
            return video_id
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _load_metadata(self, metadata_path: Optional[str], video_path: str) -> Dict:
        """Load metadata from JSON or create default"""
        if metadata_path and Path(metadata_path).exists():
            logger.info(f"Loading metadata: {metadata_path}")
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Default metadata from video filename
            video_name = Path(video_path).stem
            logger.warning("No metadata file found, using defaults")
            return {
                'title': video_name[:60],  # Max 60 chars
                'description': f"Video: {video_name}",
                'tags': ['video', 'content'],
                'hashtags': []
            }
    
    def _upload_subtitles(self, video_id: str, subtitle_path: str):
        """Upload subtitles to YouTube video"""
        try:
            logger.info(f"Uploading subtitles: {subtitle_path}")
            
            media = MediaFileUpload(
                subtitle_path,
                mimetype='application/octet-stream',
                resumable=True
            )
            
            self.youtube.captions().insert(
                part='snippet',
                body={
                    'snippet': {
                        'videoId': video_id,
                        'language': 'en',
                        'name': 'English',
                        'isDraft': False
                    }
                },
                media_body=media
            ).execute()
            
            logger.info("✅ Subtitles uploaded successfully")
            
        except Exception as e:
            logger.warning(f"Subtitle upload failed: {e}")


def auto_detect_latest_edited_video(edited_dir: str = "edited") -> Optional[str]:
    """
    Auto-detect the latest edited video in edited folder
    Returns: video path or None if no video found
    """
    edited_path = Path(edited_dir)
    
    if not edited_path.exists():
        logger.error(f"Edited folder not found: {edited_dir}")
        logger.info("Please run the video editor first to create edited videos.")
        return None
    
    # Find all .mp4 files
    mp4_files = list(edited_path.glob("*.mp4"))
    
    if not mp4_files:
        logger.error(f"No MP4 videos found in {edited_dir} folder!")
        logger.info("Please run the video editor first to create edited videos.")
        return None
    
    # Get the most recent file by modification time
    latest_video = max(mp4_files, key=lambda p: p.stat().st_mtime)
    
    logger.info("=" * 60)
    logger.info("AUTO-DETECTED EDITED VIDEO:")
    logger.info(f"  Video: {latest_video}")
    logger.info("=" * 60)
    
    return str(latest_video)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Upload video to YouTube')
    parser.add_argument('--video', help='Path to video file (or AUTO to auto-detect latest)')
    parser.add_argument('--metadata', help='Path to metadata JSON file')
    parser.add_argument('--subtitles', help='Path to SRT subtitle file')
    parser.add_argument('--privacy', default='public', choices=['private', 'unlisted', 'public'],
                        help='Video privacy setting (default: public)')
    parser.add_argument('--category', default='22', help='YouTube category ID (default: 22 = People & Blogs)')
    parser.add_argument('--credentials', default='youtube_credentials.json', 
                        help='Path to YouTube API credentials JSON')
    
    args = parser.parse_args()
    
    # Auto-detect video if not provided or if AUTO specified
    if not args.video or args.video.upper() == 'AUTO':
        logger.info("Auto-detecting latest edited video...")
        args.video = auto_detect_latest_edited_video()
        if not args.video:
            return 1
    
    # Validate video file
    if not Path(args.video).exists():
        logger.error(f"Video file not found: {args.video}")
        return 1
    
    # Auto-detect metadata and subtitles if not provided
    video_path = Path(args.video)
    if not args.metadata:
        metadata_path = video_path.with_suffix('.metadata.json')
        if metadata_path.exists():
            args.metadata = str(metadata_path)
            logger.info(f"Auto-detected metadata: {args.metadata}")
    
    if not args.subtitles:
        subtitle_path = video_path.with_suffix('.srt')
        if subtitle_path.exists():
            args.subtitles = str(subtitle_path)
            logger.info(f"Auto-detected subtitles: {args.subtitles}")
    
    # Upload
    uploader = YouTubeUploader(args.credentials)
    
    if not uploader.authenticate():
        logger.error("Authentication failed")
        return 1
    
    video_id = uploader.upload_video(
        args.video,
        args.metadata,
        args.subtitles,
        args.privacy,
        args.category
    )
    
    if video_id:
        logger.info("=" * 60)
        logger.info("🎉 SUCCESS! Video uploaded to YouTube")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("Upload failed")
        return 1


if __name__ == '__main__':
    exit(main())
