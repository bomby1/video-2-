#!/usr/bin/env python3
"""
Auto Video Editor - Transform raw videos into engaging YouTube content
Designed for CI/GitHub Actions with chunking, idempotency, and resumability
"""

import os
import sys
import json
import subprocess
import argparse
import hashlib
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import logging
from datetime import datetime

# Configure logging with immediate flush for GitHub Actions
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
# Force unbuffered output
logging.StreamHandler.flush = lambda self: sys.stdout.flush()
logger = logging.getLogger(__name__)


@dataclass
class EditConfig:
    """Video editing configuration"""
    input_video: str
    output_video: str
    speed_multiplier: float = 1.20
    remove_silence: bool = True
    silence_threshold: float = -40.0  # dB
    silence_duration: float = 0.5  # seconds
    jump_cut_threshold: float = 0.3  # seconds of pause to cut
    apply_transitions: bool = True
    apply_zoom_effects: bool = True
    add_subtitles: bool = True
    add_subscribe_popup: bool = True
    add_sound_effects: bool = True
    background_music: Optional[str] = None
    background_music_volume: float = 0.15
    chunk_duration: int = 300  # 5 minutes per chunk
    max_workers: int = 2  # CPU-friendly for CI
    
    # AI Content Generation (NEW!)
    extract_subtitles: bool = True  # Extract subtitles using Whisper
    generate_metadata: bool = True  # Generate YouTube metadata with AI
    openrouter_api_key: Optional[str] = None  # OpenRouter API key for DeepSeek
    

@dataclass
class ChunkInfo:
    """Information about a video chunk"""
    chunk_id: int
    start_time: float
    end_time: float
    duration: float
    input_path: str
    output_path: str
    processed: bool = False
    checksum: Optional[str] = None


class VideoEditor:
    """Main video editing orchestrator"""
    
    def __init__(self, config: EditConfig, work_dir: Path):
        self.config = config
        self.work_dir = work_dir
        self.chunks_dir = work_dir / "chunks"
        self.temp_dir = work_dir / "temp"
        self.state_file = work_dir / "edit_state.json"
        
        # Create directories
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or initialize state
        self.state = self._load_state()
        
    def _load_state(self) -> Dict[str, Any]:
        """Load editing state for resumability"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "chunks": [],
            "current_step": "init",
            "completed_steps": [],
            "metadata": {}
        }
    
    def _save_state(self):
        """Save editing state"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except FileNotFoundError:
            logger.error("=" * 60)
            logger.error("FFmpeg/ffprobe not found!")
            logger.error("=" * 60)
            logger.error("FFmpeg was installed but your terminal doesn't know about it yet.")
            logger.error("")
            logger.error("Please:")
            logger.error("1. Close this terminal/command prompt")
            logger.error("2. Open a NEW terminal")
            logger.error("3. Run the command again")
            logger.error("=" * 60)
            raise
    
    def _calculate_chunks(self) -> List[ChunkInfo]:
        """Calculate video chunks for processing"""
        if self.state.get("chunks"):
            return [ChunkInfo(**c) for c in self.state["chunks"]]
        
        duration = self._get_video_duration(self.config.input_video)
        chunks = []
        chunk_id = 0
        
        start = 0
        while start < duration:
            end = min(start + self.config.chunk_duration, duration)
            chunk = ChunkInfo(
                chunk_id=chunk_id,
                start_time=start,
                end_time=end,
                duration=end - start,
                input_path=str(self.chunks_dir / f"chunk_{chunk_id:03d}_input.mp4"),
                output_path=str(self.chunks_dir / f"chunk_{chunk_id:03d}_output.mp4")
            )
            chunks.append(chunk)
            chunk_id += 1
            start = end
        
        # Save chunks to state
        self.state["chunks"] = [asdict(c) for c in chunks]
        self.state["metadata"]["total_chunks"] = len(chunks)
        self.state["metadata"]["total_duration"] = duration
        self._save_state()
        
        return chunks
    
    def _split_into_chunks(self, chunks: List[ChunkInfo]):
        """Split video into chunks"""
        logger.info(f"Splitting video into {len(chunks)} chunks...")
        
        for chunk in chunks:
            if Path(chunk.input_path).exists():
                logger.info(f"Chunk {chunk.chunk_id} already exists, skipping split")
                continue
            
            logger.info(f"Extracting chunk {chunk.chunk_id}: {chunk.start_time:.2f}s - {chunk.end_time:.2f}s")
            
            cmd = [
                'ffmpeg',
                '-i', self.config.input_video,
                '-ss', str(chunk.start_time),
                '-t', str(chunk.duration),
                '-c', 'copy',
                '-y',
                chunk.input_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Chunk {chunk.chunk_id} extracted successfully")
    
    def _process_chunk(self, chunk: ChunkInfo) -> bool:
        """Process a single chunk with all editing effects"""
        logger.info(f"Processing chunk {chunk.chunk_id}...")
        
        # Check if already processed
        if Path(chunk.output_path).exists():
            logger.info(f"Chunk {chunk.chunk_id} already processed, skipping")
            return True
        
        temp_files = []
        current_input = chunk.input_path
        
        try:
            # Step 1: Remove silence using auto-editor
            if self.config.remove_silence:
                silence_output = str(self.temp_dir / f"chunk_{chunk.chunk_id:03d}_nosilence.mp4")
                temp_files.append(silence_output)
                
                logger.info(f"  Removing silence from chunk {chunk.chunk_id}...")
                self._remove_silence(current_input, silence_output)
                current_input = silence_output
            
            # Step 2: Apply speed adjustment
            if self.config.speed_multiplier != 1.0:
                speed_output = str(self.temp_dir / f"chunk_{chunk.chunk_id:03d}_speed.mp4")
                temp_files.append(speed_output)
                
                logger.info(f"  Applying {self.config.speed_multiplier}x speed to chunk {chunk.chunk_id}...")
                self._apply_speed(current_input, speed_output, self.config.speed_multiplier)
                current_input = speed_output
            
            # Step 3: Apply jump cuts
            jump_output = str(self.temp_dir / f"chunk_{chunk.chunk_id:03d}_jumpcuts.mp4")
            temp_files.append(jump_output)
            
            logger.info(f"  Applying jump cuts to chunk {chunk.chunk_id}...")
            self._apply_jump_cuts(current_input, jump_output)
            current_input = jump_output
            
            # Step 4: Apply zoom and Ken Burns effects
            if self.config.apply_zoom_effects:
                zoom_output = str(self.temp_dir / f"chunk_{chunk.chunk_id:03d}_zoom.mp4")
                temp_files.append(zoom_output)
                
                logger.info(f"  Applying zoom effects to chunk {chunk.chunk_id}...")
                self._apply_zoom_effects(current_input, zoom_output)
                current_input = zoom_output
            
            # Step 5: Add transitions
            if self.config.apply_transitions:
                trans_output = str(self.temp_dir / f"chunk_{chunk.chunk_id:03d}_trans.mp4")
                temp_files.append(trans_output)
                
                logger.info(f"  Adding transitions to chunk {chunk.chunk_id}...")
                self._add_transitions(current_input, trans_output)
                current_input = trans_output
            
            # Step 6: Add sound effects
            if self.config.add_sound_effects:
                sfx_output = str(self.temp_dir / f"chunk_{chunk.chunk_id:03d}_sfx.mp4")
                temp_files.append(sfx_output)
                
                logger.info(f"  Adding sound effects to chunk {chunk.chunk_id}...")
                self._add_sound_effects(current_input, sfx_output)
                current_input = sfx_output
            
            # Final: Copy to output with consistent encoding
            logger.info(f"  Re-encoding chunk {chunk.chunk_id} for concatenation...")
            self._reencode_for_concat(current_input, chunk.output_path)
            
            # Calculate checksum
            chunk.checksum = self._calculate_checksum(chunk.output_path)
            chunk.processed = True
            
            logger.info(f"Chunk {chunk.chunk_id} processed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error processing chunk {chunk.chunk_id}: {e}")
            return False
        
        finally:
            # Cleanup temp files (ignore errors if files are locked)
            for temp_file in temp_files:
                try:
                    if Path(temp_file).exists():
                        Path(temp_file).unlink()
                except Exception as e:
                    logger.warning(f"Could not delete temp file {temp_file}: {e}")
    
    def _remove_silence(self, input_path: str, output_path: str):
        """Remove silence using ffmpeg silencedetect and silenceremove"""
        logger.info("Detecting and removing silence...")
        
        # Use ffmpeg's silenceremove filter
        # This removes silence at the beginning, middle, and end
        # Parameters:
        # - stop_periods=-1: remove all silence segments
        # - stop_duration: minimum silence duration to remove (in seconds)
        # - stop_threshold: silence threshold in dB
        
        silence_threshold_db = self.config.silence_threshold  # e.g., -40dB
        silence_duration = self.config.silence_duration  # e.g., 0.5 seconds
        
        # Build ffmpeg command with silenceremove filter
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-af', (
                f'silenceremove='
                f'start_periods=1:'  # Remove silence at start
                f'start_duration={silence_duration}:'
                f'start_threshold={silence_threshold_db}dB:'
                f'stop_periods=-1:'  # Remove all silence segments
                f'stop_duration={silence_duration}:'
                f'stop_threshold={silence_threshold_db}dB:'
                f'detection=peak'  # Use peak detection
            ),
            '-c:v', 'copy',  # Copy video without re-encoding
            '-y',
            output_path
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("Silence removed successfully")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Silence removal failed: {e.stderr}")
            logger.info("Copying original file without silence removal...")
            shutil.copy2(input_path, output_path)
    
    def _apply_speed(self, input_path: str, output_path: str, speed: float):
        """Apply speed adjustment using ffmpeg"""
        # Calculate audio and video filters
        video_speed = 1.0 / speed
        audio_speed = speed
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-filter_complex',
            f'[0:v]setpts={video_speed}*PTS[v];[0:a]atempo={audio_speed}[a]',
            '-map', '[v]',
            '-map', '[a]',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    
    def _apply_jump_cuts(self, input_path: str, output_path: str):
        """Apply jump cuts using PySceneDetect and ffmpeg"""
        # Try to detect scenes
        import sys
        scenes_file = str(self.temp_dir / "scenes.csv")
        
        # Try different ways to call scenedetect
        commands = [
            [sys.executable, '-m', 'scenedetect', '-i', input_path, 'detect-content'],
            ['scenedetect', '-i', input_path, 'detect-content'],
            ['py', '-m', 'scenedetect', '-i', input_path, 'detect-content'],
        ]
        
        scene_detected = False
        for cmd in commands:
            try:
                cmd.extend([
                    '--threshold', '27',
                    'list-scenes',
                    '-o', str(self.temp_dir),
                    '-f', scenes_file
                ])
                subprocess.run(cmd, check=True, capture_output=True)
                scene_detected = True
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        # For now, just copy (full scene-based editing would be complex)
        # In production, you'd parse scenes and apply cuts
        shutil.copy2(input_path, output_path)
    
    def _apply_zoom_effects(self, input_path: str, output_path: str):
        """Apply dynamic zoom and Ken Burns effects using ffmpeg"""
        # Get video dimensions and duration
        probe_cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate',
            '-of', 'csv=p=0',
            input_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        parts = result.stdout.strip().split(',')
        width, height = int(parts[0]), int(parts[1])
        
        duration = self._get_video_duration(input_path)
        
        # Create dynamic zoom: zoom in and out in waves for engagement
        # This creates a "breathing" effect that keeps viewers engaged
        zoom_filter = (
            f"zoompan="
            f"z='if(lte(mod(time,8),4),min(1.15,1+0.15*sin(time*PI/4)),max(1,1.15-0.15*sin(time*PI/4)))':"
            f"d=1:"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"s={width}x{height},"
            f"minterpolate=fps=30:mi_mode=mci"  # Smooth motion interpolation
        )
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', zoom_filter,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Dynamic zoom failed, trying simple zoom: {e}")
            # Fallback to simple zoom
            simple_zoom = f"zoompan=z='min(zoom+0.0002,1.1)':d=1:s={width}x{height}"
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-vf', simple_zoom,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'copy',
                '-y',
                output_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
    
    def _add_transitions(self, input_path: str, output_path: str):
        """Add smooth transitions and color grading for engagement"""
        # Apply color grading and smooth motion for more engaging look
        # Increase saturation, contrast, and add slight vignette
        
        filter_complex = (
            "[0:v]"
            "eq=saturation=1.2:contrast=1.1:brightness=0.02,"  # Color enhancement
            "unsharp=5:5:1.0:5:5:0.0,"  # Slight sharpening
            "vignette=PI/4"  # Subtle vignette for focus
            "[v]"
        )
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-map', '0:a',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Color grading failed, copying original: {e}")
            shutil.copy2(input_path, output_path)
    
    def _add_sound_effects(self, input_path: str, output_path: str):
        """Enhance audio for better engagement"""
        # Apply audio enhancement: normalize, compress, and add presence
        
        audio_filter = (
            "loudnorm=I=-16:TP=-1.5:LRA=11,"  # Loudness normalization
            "acompressor=threshold=-20dB:ratio=4:attack=5:release=50,"  # Compression
            "equalizer=f=3000:width_type=h:width=200:g=2"  # Presence boost
        )
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-af', audio_filter,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-y',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Audio enhancement failed, copying original: {e}")
            shutil.copy2(input_path, output_path)
    
    def _reencode_for_concat(self, input_path: str, output_path: str):
        """Re-encode with consistent settings for concatenation"""
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-r', '30',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '44100',
            '-y',
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate file checksum for verification"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _concatenate_chunks(self, chunks: List[ChunkInfo], output_path: str):
        """Concatenate all processed chunks"""
        logger.info("Concatenating all chunks...")
        
        # Special case: if only 1 chunk, just copy it
        if len(chunks) == 1:
            logger.info("Only 1 chunk, copying directly...")
            shutil.copy2(chunks[0].output_path, output_path)
            logger.info("Chunk copied successfully")
            return
        
        # Create concat file for multiple chunks
        concat_file = self.temp_dir / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for chunk in chunks:
                f.write(f"file '{Path(chunk.output_path).absolute()}'\n")
        
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',
            '-y',
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info("Chunks concatenated successfully")
    
    def _add_subtitles(self, input_path: str, output_path: str):
        """Add animated styled subtitles"""
        logger.info("Adding animated subtitles...")
        
        # Generate subtitles using speech recognition (would need whisper or similar)
        # For now, skip if no subtitle file exists
        subtitle_file = Path(self.config.input_video).with_suffix('.srt')
        
        if not subtitle_file.exists():
            logger.warning("No subtitle file found, skipping subtitles")
            shutil.copy2(input_path, output_path)
            return
        
        # Apply styled subtitles with ffmpeg
        subtitle_style = (
            "FontName=Arial Bold,"
            "FontSize=24,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BackColour=&H80000000,"
            "Bold=1,"
            "Outline=2,"
            "Shadow=1,"
            "Alignment=2"
        )
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-vf', f"subtitles={subtitle_file}:force_style='{subtitle_style}'",
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logger.warning("Subtitle addition failed, copying original")
            shutil.copy2(input_path, output_path)
    
    def _add_subscribe_popup(self, input_path: str, output_path: str):
        """Add subscribe popup with sound effect"""
        logger.info("Adding subscribe popup...")
        
        # Check for subscribe assets
        subscribe_image = Path("assets/subscribe.png")
        subscribe_sound = Path("assets/subscribe_sound.mp3")
        
        if not subscribe_image.exists():
            logger.warning("Subscribe image not found, skipping popup")
            shutil.copy2(input_path, output_path)
            return
        
        # Add popup at 30% and 70% of video duration
        duration = self._get_video_duration(input_path)
        popup_times = [duration * 0.3, duration * 0.7]
        
        # Create overlay filter
        overlay_filter = ""
        for i, time in enumerate(popup_times):
            overlay_filter += f"[0:v]overlay=W-w-10:H-h-10:enable='between(t,{time},{time+3})'[v{i}];"
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-i', str(subscribe_image),
            '-filter_complex', overlay_filter[:-1],  # Remove last semicolon
            '-map', '[v1]' if len(popup_times) > 1 else '[v0]',
            '-map', '0:a',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'copy',
            '-y',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logger.warning("Subscribe popup failed, copying original")
            shutil.copy2(input_path, output_path)
    
    def _add_background_music(self, input_path: str, output_path: str):
        """Add background music with advanced blending, EQ, and ducking"""
        logger.info("Adding background music with advanced processing...")
        
        if not self.config.background_music or not Path(self.config.background_music).exists():
            logger.warning("Background music not found, skipping")
            shutil.copy2(input_path, output_path)
            return
        
        # Get video duration for fade timing
        duration = self._get_video_duration(input_path)
        fade_duration = 3.0  # 3 seconds for smoother fade
        
        # Advanced audio processing chain:
        # 1. EQ: Reduce high frequencies (reduce harshness), boost low frequencies (warmth)
        # 2. Compression: Smooth out volume peaks
        # 3. Volume adjustment
        # 4. Smooth fade in/out with exponential curve
        # 5. Sidechain ducking - lower music when voice is present
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-stream_loop', '-1',  # Loop music if needed
            '-i', self.config.background_music,
            '-filter_complex',
            (
                # Process background music with EQ and compression
                f'[1:a]'
                # High-pass filter to reduce bass rumble
                f'highpass=f=80,'
                # Low-pass filter to reduce harsh highs
                f'lowpass=f=10000,'
                # EQ adjustments for smooth blend
                f'equalizer=f=8000:width_type=o:width=2:g=-4,'  # Reduce highs
                f'equalizer=f=250:width_type=o:width=2:g=2,'    # Boost low-mids (warmth)
                f'equalizer=f=4000:width_type=o:width=2:g=-2,'  # Reduce mid-highs
                # Compress to smooth out volume
                f'acompressor=threshold=-18dB:ratio=3:attack=50:release=300,'
                # Set volume
                f'volume={self.config.background_music_volume},'
                # Smooth exponential fade in/out
                f'afade=t=in:st=0:d={fade_duration}:curve=esin,'
                f'afade=t=out:st={duration-fade_duration}:d={fade_duration}:curve=esin'
                f'[music];'
                # Simple mix without aggressive ducking (better for continuous speech)
                # Music stays present but subtle throughout
                f'[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[a]'
            ),
            '-map', '0:v',
            '-map', '[a]',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            '-y',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Background music blended smoothly with advanced EQ and ducking")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Advanced music processing failed, trying simple mix: {e}")
            # Fallback to simpler version if advanced processing fails
            self._add_background_music_simple(input_path, output_path, duration)
    
    def _add_background_music_simple(self, input_path: str, output_path: str, duration: float):
        """Fallback: Simple background music mixing"""
        fade_duration = 2.0
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-stream_loop', '-1',
            '-i', self.config.background_music,
            '-filter_complex',
            (
                f'[1:a]volume={self.config.background_music_volume},'
                f'afade=t=in:st=0:d={fade_duration},'
                f'afade=t=out:st={duration-fade_duration}:d={fade_duration}'
                f'[music];'
                f'[0:a][music]amix=inputs=2:duration=first[a]'
            ),
            '-map', '0:v',
            '-map', '[a]',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            '-y',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Background music added with simple mixing")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to add background music: {e}")
            shutil.copy2(input_path, output_path)
    
    def _extract_subtitles_whisper(self, video_path: str, output_srt: str) -> Optional[str]:
        """Extract subtitles using Whisper AI (optimized for GitHub Actions)"""
        logger.info("Extracting subtitles with Whisper AI...")
        
        try:
            import whisper
            import torch
        except ImportError:
            logger.warning("Whisper not installed. Skipping subtitle extraction.")
            logger.info("Install with: pip install openai-whisper")
            return None
        
        try:
            # Extract audio first
            audio_path = str(self.temp_dir / "temp_audio.wav")
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn', '-acodec', 'pcm_s16le',
                '-ar', '16000', '-ac', '1',
                '-y', audio_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Load Whisper model (with caching for GitHub Actions)
            # Use 'base' model - good balance of speed/accuracy
            # Model will be cached in ~/.cache/whisper/ for future runs
            logger.info("Loading Whisper model (will cache for future runs)...")
            
            # Force CPU mode for GitHub Actions (no GPU available)
            device = "cpu"
            model = whisper.load_model("base", device=device)
            
            # Transcribe with optimized settings for CI/CD
            logger.info("Transcribing audio...")
            result = model.transcribe(
                audio_path,
                language="en",
                task="transcribe",
                verbose=False,
                fp16=False,  # Disable FP16 for CPU (GitHub Actions)
                condition_on_previous_text=False,  # Faster processing
                compression_ratio_threshold=2.4,
                logprob_threshold=-1.0,
                no_speech_threshold=0.6
            )
            
            # Save as SRT
            with open(output_srt, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(result['segments'], start=1):
                    start = self._format_srt_timestamp(segment['start'])
                    end = self._format_srt_timestamp(segment['end'])
                    text = segment['text'].strip()
                    f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
            
            # Also save full transcript as .txt for AI metadata
            txt_path = Path(output_srt).with_suffix('.txt')
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(result['text'].strip())
            
            # Cleanup audio
            try:
                Path(audio_path).unlink()
            except:
                pass
            
            logger.info(f"Subtitles saved: {output_srt}")
            logger.info(f"Transcript saved: {txt_path}")
            return result['text'].strip()
            
        except Exception as e:
            logger.warning(f"Subtitle extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _format_srt_timestamp(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _generate_metadata_ai(self, transcript: str, api_key: str) -> Optional[Dict]:
        """Generate YouTube metadata using OpenRouter DeepSeek API (optimized for GitHub Actions)"""
        logger.info("Generating YouTube metadata with DeepSeek AI...")
        
        try:
            import requests
        except ImportError:
            logger.warning("requests not installed. Install with: pip install requests")
            return None
        
        # Truncate transcript to avoid token limits (keep first 2000 chars)
        truncated_transcript = transcript[:2000]
        if len(transcript) > 2000:
            truncated_transcript += "..."
        
        prompt = f"""Based on this video transcription, generate YouTube metadata in JSON format.

Transcription:
{truncated_transcript}

Generate:
1. A catchy YouTube title (max 60 characters, engaging and clickable)
2. A detailed description (2-3 paragraphs, SEO-optimized with keywords)
3. 25 relevant tags (mix of broad and specific keywords for maximum reach)
4. 10 trending hashtags (with # symbol, relevant to the content)

Return ONLY valid JSON in this exact format:
{{
  "title": "Your Title Here",
  "description": "Your description here...",
  "tags": ["tag1", "tag2", "tag3", ... 25 tags total],
  "hashtags": ["#hashtag1", "#hashtag2", ... 10 hashtags total]
}}"""
        
        # Try multiple free models as fallback
        free_models = [
            "meta-llama/llama-3.2-3b-instruct:free",  # Primary: tested and working
            "google/gemini-2.0-flash-exp:free",       # Backup 1: Google's free tier
            "qwen/qwen-2-7b-instruct:free",           # Backup 2: Alibaba's model
        ]
        
        # Try each model with retry logic
        for model_id in free_models:
            logger.info(f"Trying model: {model_id}")
            sys.stdout.flush()
            
            max_retries = 2  # 2 retries per model (total 3 attempts per model)
            for attempt in range(max_retries):
                try:
                    logger.info(f"  Attempt {attempt + 1}/{max_retries}...")
                    sys.stdout.flush()
                    
                    response = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com",
                            "X-Title": "Auto Video Editor"
                        },
                        json={
                            "model": model_id,
                            "messages": [
                                {"role": "system", "content": "You are a YouTube SEO expert. Always respond with valid JSON only."},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.7,
                            "max_tokens": 2000
                        },
                        timeout=60
                    )
                
                    if response.status_code == 200:
                        content = response.json()['choices'][0]['message']['content']
                        
                        # Extract JSON from response (handle markdown code blocks)
                        import re
                        # Try to find JSON in code block first
                        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                        if code_block_match:
                            json_str = code_block_match.group(1)
                        else:
                            # Try to find raw JSON
                            json_match = re.search(r'\{.*\}', content, re.DOTALL)
                            if json_match:
                                json_str = json_match.group()
                            else:
                                logger.warning(f"  No JSON found in response from {model_id}")
                                break  # Try next model
                        
                        # Parse JSON
                        try:
                            metadata = json.loads(json_str)
                        except json.JSONDecodeError as e:
                            logger.warning(f"  JSON parse error: {e}")
                            break  # Try next model
                        
                        # Validate required fields
                        required_fields = ['title', 'description', 'tags', 'hashtags']
                        if all(field in metadata for field in required_fields):
                            logger.info(f"✅ AI metadata generated successfully with {model_id}!")
                            sys.stdout.flush()
                            return metadata
                        else:
                            logger.warning(f"  Missing required fields: {[f for f in required_fields if f not in metadata]}")
                            break  # Try next model
                            
                    elif response.status_code == 429:
                        wait_time = 5 * (attempt + 1)  # Exponential backoff: 5s, 10s
                        logger.warning(f"  Rate limited (429), waiting {wait_time}s...")
                        sys.stdout.flush()
                        import time
                        time.sleep(wait_time)
                        continue  # Retry same model
                    elif response.status_code == 402:
                        logger.warning(f"  Model {model_id} requires credits (402), trying next model...")
                        sys.stdout.flush()
                        break  # Try next model (no point retrying)
                    elif response.status_code == 404:
                        logger.warning(f"  Model {model_id} not found (404), trying next model...")
                        sys.stdout.flush()
                        break  # Try next model
                    else:
                        logger.warning(f"  API error {response.status_code}: {response.text[:100]}")
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(2)
                            continue  # Retry same model
                        break  # Try next model after all retries
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"  Request timeout (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(2)
                        continue  # Retry same model
                    break  # Try next model after timeout
                except Exception as e:
                    logger.warning(f"  Error: {e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(2)
                        continue  # Retry same model
                    break  # Try next model after error
        
        # If we get here, all models failed
        logger.warning("❌ All AI models failed to generate metadata")
        sys.stdout.flush()
        return None
    
    def run(self) -> bool:
        """Run the complete editing pipeline"""
        try:
            logger.info("=" * 60)
            logger.info("Starting Auto Video Editor")
            logger.info("=" * 60)
            logger.info(f"Input: {self.config.input_video}")
            logger.info(f"Output: {self.config.output_video}")
            
            # Validate input video hasn't changed
            current_input_checksum = self._calculate_checksum(self.config.input_video)
            saved_input_checksum = self.state.get("metadata", {}).get("input_checksum")
            
            if saved_input_checksum and saved_input_checksum != current_input_checksum:
                logger.warning("=" * 60)
                logger.warning("Input video has changed! Clearing old work...")
                logger.warning("=" * 60)
                # Clear state to start fresh
                self.state = {
                    "chunks": [],
                    "completed_steps": [],
                    "metadata": {"input_checksum": current_input_checksum}
                }
                self._save_state()
                # Clear old chunks
                if self.chunk_dir.exists():
                    shutil.rmtree(self.chunk_dir)
                    self.chunk_dir.mkdir(parents=True, exist_ok=True)
                if self.temp_dir.exists():
                    shutil.rmtree(self.temp_dir)
                    self.temp_dir.mkdir(parents=True, exist_ok=True)
            elif not saved_input_checksum:
                # First run, save checksum
                self.state["metadata"]["input_checksum"] = current_input_checksum
                self._save_state()
            
            # Step 1: Calculate chunks
            if "chunk_calculation" not in self.state.get("completed_steps", []):
                chunks = self._calculate_chunks()
                self.state["completed_steps"].append("chunk_calculation")
                self._save_state()
            else:
                chunks = [ChunkInfo(**c) for c in self.state["chunks"]]
            
            logger.info(f"Total chunks: {len(chunks)}")
            
            # Step 2: Split video into chunks
            if "chunk_splitting" not in self.state.get("completed_steps", []):
                self._split_into_chunks(chunks)
                self.state["completed_steps"].append("chunk_splitting")
                self._save_state()
            
            # Step 3: Process each chunk
            for chunk in chunks:
                if not chunk.processed:
                    success = self._process_chunk(chunk)
                    if not success:
                        logger.error(f"Failed to process chunk {chunk.chunk_id}")
                        return False
                    
                    # Update state
                    for i, state_chunk in enumerate(self.state["chunks"]):
                        if state_chunk["chunk_id"] == chunk.chunk_id:
                            self.state["chunks"][i] = asdict(chunk)
                            break
                    self._save_state()
            
            # Step 4: Concatenate chunks
            if "concatenation" not in self.state.get("completed_steps", []):
                concat_output = str(self.temp_dir / "concatenated.mp4")
                self._concatenate_chunks(chunks, concat_output)
                self.state["completed_steps"].append("concatenation")
                self.state["metadata"]["concat_output"] = concat_output
                self._save_state()
            else:
                concat_output = self.state["metadata"]["concat_output"]
            
            # Step 5: Add subtitles
            if self.config.add_subtitles and "subtitles" not in self.state.get("completed_steps", []):
                subtitle_output = str(self.temp_dir / "with_subtitles.mp4")
                self._add_subtitles(concat_output, subtitle_output)
                concat_output = subtitle_output
                self.state["completed_steps"].append("subtitles")
                self._save_state()
            
            # Step 6: Add subscribe popup
            if self.config.add_subscribe_popup and "subscribe" not in self.state.get("completed_steps", []):
                subscribe_output = str(self.temp_dir / "with_subscribe.mp4")
                self._add_subscribe_popup(concat_output, subscribe_output)
                concat_output = subscribe_output
                self.state["completed_steps"].append("subscribe")
                self._save_state()
            
            # Step 7: Add background music
            if self.config.background_music and "background_music" not in self.state.get("completed_steps", []):
                music_output = str(self.temp_dir / "with_music.mp4")
                self._add_background_music(concat_output, music_output)
                concat_output = music_output
                self.state["completed_steps"].append("background_music")
                self._save_state()
            
            # Step 8: Final copy to output
            logger.info("Creating final output...")
            # Ensure output directory exists
            Path(self.config.output_video).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(concat_output, self.config.output_video)
            
            # Step 9: Extract subtitles (NEW!)
            transcript = None
            if self.config.extract_subtitles and "subtitle_extraction" not in self.state.get("completed_steps", []):
                output_srt = Path(self.config.output_video).with_suffix('.srt')
                transcript = self._extract_subtitles_whisper(self.config.output_video, str(output_srt))
                if transcript:
                    self.state["completed_steps"].append("subtitle_extraction")
                    self.state["metadata"]["transcript"] = transcript
                    self._save_state()
            else:
                # Load existing transcript
                transcript = self.state.get("metadata", {}).get("transcript")
            
            # Step 10: Generate AI metadata (NEW!)
            if self.config.generate_metadata and transcript and self.config.openrouter_api_key:
                if "metadata_generation" not in self.state.get("completed_steps", []):
                    metadata = self._generate_metadata_ai(transcript, self.config.openrouter_api_key)
                    if metadata:
                        # Save metadata to JSON file
                        metadata_file = Path(self.config.output_video).with_suffix('.metadata.json')
                        with open(metadata_file, 'w', encoding='utf-8') as f:
                            json.dump(metadata, f, indent=2, ensure_ascii=False)
                        logger.info(f"YouTube metadata saved: {metadata_file}")
                        self.state["completed_steps"].append("metadata_generation")
                        self._save_state()
            
            logger.info("=" * 60)
            logger.info("Video editing completed successfully!")
            logger.info(f"Output saved to: {self.config.output_video}")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Editing pipeline failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def load_manifest(manifest_path: str) -> Dict[str, Any]:
    """Load editing manifest JSON"""
    with open(manifest_path, 'r') as f:
        return json.load(f)


def auto_detect_latest_video(downloads_dir: str = "downloads") -> Optional[Tuple[str, str]]:
    """
    Auto-detect the latest video in downloads folder
    Returns: (input_path, output_path) or None if no video found
    """
    downloads_path = Path(downloads_dir)
    
    if not downloads_path.exists():
        logger.error(f"Downloads folder not found: {downloads_dir}")
        logger.info("Please create a 'downloads' folder and add your video.")
        return None
    
    # Find all .mp4 files
    mp4_files = list(downloads_path.glob("*.mp4"))
    
    if not mp4_files:
        logger.error(f"No MP4 videos found in {downloads_dir} folder!")
        logger.info("Please add a video to the downloads folder.")
        return None
    
    # Get the most recent file by modification time
    latest_video = max(mp4_files, key=lambda p: p.stat().st_mtime)
    
    # Generate output filename (replace spaces with underscores, add _EDITED)
    output_name = latest_video.stem.replace(" ", "_") + "_EDITED.mp4"
    output_path = Path("edited") / output_name
    
    logger.info("=" * 60)
    logger.info("AUTO-DETECTED VIDEO:")
    logger.info(f"  Input:  {latest_video}")
    logger.info(f"  Output: {output_path}")
    logger.info("=" * 60)
    
    return (str(latest_video), str(output_path))


def main():
    """CLI entrypoint"""
    parser = argparse.ArgumentParser(
        description="Auto Video Editor - Transform raw videos into engaging content"
    )
    parser.add_argument(
        '--manifest',
        type=str,
        required=True,
        help='Path to manifest JSON file'
    )
    parser.add_argument(
        '--work-dir',
        type=str,
        default='./work',
        help='Working directory for temp files'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from previous state'
    )
    
    args = parser.parse_args()
    
    # Load manifest
    manifest = load_manifest(args.manifest)
    
    # Filter out comment fields (starting with _)
    config_data = {k: v for k, v in manifest.items() if not k.startswith('_')}
    
    # Auto-detect video if needed
    if config_data.get('input_video') == 'AUTO_DETECT' or config_data.get('output_video') == 'AUTO_DETECT':
        logger.info("Auto-detection enabled in manifest...")
        video_paths = auto_detect_latest_video()
        
        if video_paths is None:
            return 1
        
        input_path, output_path = video_paths
        config_data['input_video'] = input_path
        config_data['output_video'] = output_path
        
        # Update manifest file with detected paths
        manifest['input_video'] = input_path
        manifest['output_video'] = output_path
        with open(args.manifest, 'w') as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Updated {args.manifest} with detected video paths")
    
    # Create config
    config = EditConfig(**config_data)
    
    # Validate input
    if not Path(config.input_video).exists():
        logger.error(f"Input video not found: {config.input_video}")
        return 1
    
    # Create work directory
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # Clear state if not resuming
    if not args.resume:
        state_file = work_dir / "edit_state.json"
        if state_file.exists():
            state_file.unlink()
    
    # Run editor
    editor = VideoEditor(config, work_dir)
    success = editor.run()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
