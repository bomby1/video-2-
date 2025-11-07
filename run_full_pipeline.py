#!/usr/bin/env python3
"""
Full Video Pipeline Orchestrator
Runs the complete end-to-end workflow:
1. Video Generation (main.py) - CapCut AI video generation & download
2. Video Editing (auto_edit.py) - Professional editing with AI features
3. YouTube Upload (youtube_uploader.py) - Upload to YouTube with metadata

Usage:
    py run_full_pipeline.py
    py run_full_pipeline.py --privacy unlisted
    py run_full_pipeline.py --skip-generation  # Skip step 1, start from editing
    py run_full_pipeline.py --skip-upload      # Stop after editing
"""

import sys
import os
import subprocess
import logging
from pathlib import Path
import argparse
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates the complete video production pipeline"""
    
    def __init__(self, skip_generation=False, skip_upload=False, privacy='public', continue_on_error=True):
        self.project_root = Path(__file__).parent
        self.skip_generation = skip_generation
        self.skip_upload = skip_upload
        self.privacy = privacy
        self.continue_on_error = continue_on_error
        
        # Pipeline scripts
        self.main_script = self.project_root / "src" / "main.py"
        self.editor_script = self.project_root / "auto_edit.py"
        self.uploader_script = self.project_root / "youtube_uploader.py"
        
        # Configuration files
        self.manifest = self.project_root / "manifest.json"
        
    def print_banner(self, title):
        """Print a formatted banner"""
        logger.info("=" * 70)
        logger.info(f"  {title}")
        logger.info("=" * 70)
    
    def run_command(self, cmd, step_name):
        """Run a command and handle errors"""
        self.print_banner(f"STEP: {step_name}")
        logger.info(f"Command: {' '.join(cmd)}")
        logger.info("")
        
        start_time = time.time()
        
        try:
            # Run the command (don't use check=True to continue on error)
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=False,  # Show output in real-time
                text=True
            )
            
            elapsed = time.time() - start_time
            logger.info("")
            
            # Check exit code
            if result.returncode == 0:
                logger.info(f"✅ {step_name} completed successfully in {elapsed:.1f} seconds")
                logger.info("")
                return True
            else:
                logger.error(f"❌ {step_name} failed with exit code {result.returncode} after {elapsed:.1f} seconds")
                logger.error("")
                
                if self.continue_on_error:
                    logger.warning("⚠️  Continuing to next step despite error...")
                    logger.info("")
                    return True  # Continue anyway
                else:
                    return False
            
        except FileNotFoundError:
            logger.error(f"❌ Script not found: {cmd[0]}")
            logger.error("")
            return False
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"❌ {step_name} failed after {elapsed:.1f} seconds")
            logger.error(f"Error: {e}")
            logger.error("")
            
            if self.continue_on_error:
                logger.warning("⚠️  Continuing to next step despite error...")
                logger.info("")
                return True  # Continue anyway
            else:
                return False
    
    def step1_video_generation(self):
        """Step 1: Generate video using CapCut AI (main.py)"""
        if self.skip_generation:
            logger.info("⏭️  Skipping video generation (--skip-generation flag)")
            logger.info("")
            return True
        
        if not self.main_script.exists():
            logger.error(f"Main script not found: {self.main_script}")
            return False
        
        # Run main.py (video generation & download)
        # Auto-enable headless mode in GitHub Actions
        cmd = ["python", str(self.main_script)]
        
        # Add --headless flag if running in CI/GitHub Actions
        if os.getenv('CI') or os.getenv('GITHUB_ACTIONS'):
            cmd.append("--headless")
            logger.info("🤖 GitHub Actions detected - running in headless mode")
        
        return self.run_command(cmd, "Video Generation & Download (main.py)")
    
    def step2_video_editing(self):
        """Step 2: Edit video with AI features (auto_edit.py)"""
        if not self.editor_script.exists():
            logger.error(f"Editor script not found: {self.editor_script}")
            return False
        
        if not self.manifest.exists():
            logger.error(f"Manifest not found: {self.manifest}")
            logger.info("Please create manifest.json with your editing settings")
            return False
        
        # Clear state file to ensure fresh run (important for GitHub Actions)
        state_file = self.project_root / "work" / "edit_state.json"
        if state_file.exists():
            state_file.unlink()
            logger.info("🔄 Cleared previous editing state for fresh run")
        
        # Run auto_edit.py with auto-detection (no --resume to ensure all steps run)
        cmd = [
            "python", 
            str(self.editor_script),
            "--manifest", str(self.manifest),
            "--work-dir", "work"
        ]
        return self.run_command(cmd, "Video Editing with AI (auto_edit.py)")
    
    def step3_youtube_upload(self):
        """Step 3: Upload to YouTube (youtube_uploader.py)"""
        if self.skip_upload:
            logger.info("⏭️  Skipping YouTube upload (--skip-upload flag)")
            logger.info("")
            return True
        
        if not self.uploader_script.exists():
            logger.error(f"Uploader script not found: {self.uploader_script}")
            return False
        
        # Run youtube_uploader.py with auto-detection
        cmd = [
            "python",
            str(self.uploader_script),
            "--video", "AUTO",
            "--privacy", self.privacy
        ]
        return self.run_command(cmd, f"YouTube Upload ({self.privacy}) (youtube_uploader.py)")
    
    def reset_manifest_to_auto_detect(self):
        """Reset manifest.json to AUTO_DETECT before pipeline runs"""
        try:
            if not self.manifest.exists():
                logger.warning(f"Manifest not found: {self.manifest}")
                return
            
            import json
            with open(self.manifest, 'r') as f:
                manifest_data = json.load(f)
            
            # Reset to AUTO_DETECT
            manifest_data['input_video'] = 'AUTO_DETECT'
            manifest_data['output_video'] = 'AUTO_DETECT'
            
            with open(self.manifest, 'w') as f:
                json.dump(manifest_data, f, indent=2)
            
            logger.info("✅ Reset manifest.json to AUTO_DETECT mode")
            logger.info("")
            
        except Exception as e:
            logger.warning(f"Could not reset manifest: {e}")
            logger.info("")
    
    def run(self):
        """Run the complete pipeline"""
        self.print_banner("🎬 FULL VIDEO PRODUCTION PIPELINE")
        logger.info("Pipeline Steps:")
        logger.info("  1. Video Generation (CapCut AI + Download)")
        logger.info("  2. Video Editing (FFmpeg + Whisper + DeepSeek AI)")
        logger.info("  3. YouTube Upload (with metadata & subtitles)")
        logger.info("")
        
        if self.skip_generation:
            logger.info("⚠️  Video generation will be SKIPPED")
        if self.skip_upload:
            logger.info("⚠️  YouTube upload will be SKIPPED")
        logger.info("")
        
        # Reset manifest to AUTO_DETECT before starting
        self.reset_manifest_to_auto_detect()
        
        pipeline_start = time.time()
        
        # Step 1: Video Generation
        if not self.step1_video_generation():
            logger.error("Pipeline failed at Step 1: Video Generation")
            return False
        
        # Step 2: Video Editing
        if not self.step2_video_editing():
            logger.error("Pipeline failed at Step 2: Video Editing")
            return False
        
        # Step 3: YouTube Upload
        if not self.step3_youtube_upload():
            logger.error("Pipeline failed at Step 3: YouTube Upload")
            return False
        
        # Success!
        total_time = time.time() - pipeline_start
        self.print_banner("🎉 PIPELINE COMPLETED!")
        logger.info(f"Total time: {total_time:.1f} seconds ({total_time/60:.1f} minutes)")
        logger.info("")
        logger.info("Output files:")
        logger.info("  📁 downloads/     - Raw generated video")
        logger.info("  📁 edited/        - Edited video + subtitles + metadata")
        logger.info("  🌐 YouTube        - Published video")
        logger.info("")
        
        # Countdown before exit
        logger.info("Window will close in 30 seconds...")
        for i in range(30, 0, -1):
            print(f"\rClosing in {i} seconds... (Press Ctrl+C to keep open)", end='', flush=True)
            time.sleep(1)
        print("\r" + " " * 60 + "\r", end='', flush=True)  # Clear countdown line
        
        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Full Video Production Pipeline - Generate, Edit, Upload',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline (all 3 steps)
  py run_full_pipeline.py
  
  # Run with unlisted privacy
  py run_full_pipeline.py --privacy unlisted
  
  # Skip video generation (start from editing existing video)
  py run_full_pipeline.py --skip-generation
  
  # Stop after editing (don't upload)
  py run_full_pipeline.py --skip-upload
  
  # Edit only (skip generation and upload)
  py run_full_pipeline.py --skip-generation --skip-upload
        """
    )
    
    parser.add_argument(
        '--skip-generation',
        action='store_true',
        help='Skip video generation step (use existing video in downloads/)'
    )
    
    parser.add_argument(
        '--skip-upload',
        action='store_true',
        help='Skip YouTube upload step (stop after editing)'
    )
    
    parser.add_argument(
        '--privacy',
        default='public',
        choices=['private', 'unlisted', 'public'],
        help='YouTube video privacy setting (default: public)'
    )
    
    args = parser.parse_args()
    
    # Run pipeline (continue_on_error=True to run all steps even if one fails)
    orchestrator = PipelineOrchestrator(
        skip_generation=args.skip_generation,
        skip_upload=args.skip_upload,
        privacy=args.privacy,
        continue_on_error=True
    )
    
    success = orchestrator.run()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
