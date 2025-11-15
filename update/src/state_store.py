#!/usr/bin/env python3
"""
State Store Module for CapCut Automation

This module provides persistent state management for jobs, sessions, and retry policies.
Handles job status tracking, session TTL management, and resume capabilities.
"""

import os
import json
import time
import random
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import threading
import shutil


class JobStatus(Enum):
    """Job status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class SessionStatus(Enum):
    """Session status enumeration."""
    VALID = "valid"
    STALE = "stale"
    EXPIRED = "expired"
    INVALID = "invalid"


class StateStore:
    """
    Persistent state management for CapCut automation.
    """
    
    # Default configuration
    DEFAULT_SESSION_MAX_AGE = 3600  # 1 hour
    DEFAULT_MAX_ATTEMPTS = 3
    DEFAULT_BASE_BACKOFF = 2
    DEFAULT_MAX_BACKOFF = 60
    DEFAULT_BACKOFF_MULTIPLIER = 2.0
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize state store.
        
        Args:
            project_root: Project root directory path
        """
        # Set up paths
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.state_dir = self.project_root / "state"
        self.config_dir = self.project_root / "config"
        
        # Ensure directories exist
        self.state_dir.mkdir(exist_ok=True)
        self.config_dir.mkdir(exist_ok=True)
        
        # State files
        self.jobs_file = self.state_dir / "jobs.json"
        self.session_file = self.state_dir / "session.json"
        self.settings_file = self.config_dir / "settings.json"
        self.settings_example_file = self.config_dir / "settings.example.json"
        
        # Thread lock for concurrent access
        self._lock = threading.Lock()
        
        # Load configuration
        self.settings = self._load_settings()
        
        # Initialize state files if they don't exist
        self._initialize_state_files()
    
    def _load_settings(self) -> Dict[str, Any]:
        """
        Load settings from configuration file.
        
        Returns:
            Settings dictionary
        """
        try:
            # Try to load custom settings first
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    # Remove metadata if present
                    if '_metadata' in settings:
                        del settings['_metadata']
                    return settings
            
            # Fall back to example settings
            elif self.settings_example_file.exists():
                with open(self.settings_example_file, 'r') as f:
                    settings = json.load(f)
                    # Remove metadata if present
                    if '_metadata' in settings:
                        del settings['_metadata']
                    
                    # Copy example to settings.json for user customization
                    with open(self.settings_file, 'w') as f_out:
                        json.dump(settings, f_out, indent=2)
                    
                    print(f"Created settings.json from example template")
                    return settings
            
            else:
                # Use default settings
                print("No settings file found, using defaults")
                return self._get_default_settings()
        
        except Exception as e:
            print(f"Error loading settings: {e}, using defaults")
            return self._get_default_settings()
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings configuration."""
        return {
            "session": {
                "max_age_seconds": self.DEFAULT_SESSION_MAX_AGE,
                "reuse_state": True,
                "force_per_job_relogin": False
            },
            "retry_policy": {
                "max_attempts": self.DEFAULT_MAX_ATTEMPTS,
                "base_backoff_seconds": self.DEFAULT_BASE_BACKOFF,
                "max_backoff_seconds": self.DEFAULT_MAX_BACKOFF,
                "backoff_multiplier": self.DEFAULT_BACKOFF_MULTIPLIER,
                "jitter": True
            }
        }
    
    def _initialize_state_files(self):
        """Initialize state files if they don't exist."""
        # Initialize jobs file
        if not self.jobs_file.exists():
            initial_jobs_state = {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0.0",
                    "total_jobs": 0
                },
                "jobs": {}
            }
            
            with open(self.jobs_file, 'w') as f:
                json.dump(initial_jobs_state, f, indent=2)
        
        # Initialize session file
        if not self.session_file.exists():
            initial_session_state = {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0.0"
                },
                "session": {
                    "last_state_saved_at": None,
                    "session_valid": False,
                    "state_file_path": None,
                    "login_count": 0,
                    "last_validation_at": None
                }
            }
            
            with open(self.session_file, 'w') as f:
                json.dump(initial_session_state, f, indent=2)
    
    def _backup_state_file(self, file_path: Path):
        """Create a timestamped backup of a state file."""
        if file_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = file_path.with_suffix(f".bak.{timestamp}{file_path.suffix}")
            
            try:
                shutil.copy2(file_path, backup_path)
                
                # Keep only last 5 backups
                backup_pattern = f"{file_path.stem}.bak.*{file_path.suffix}"
                backups = sorted(file_path.parent.glob(backup_pattern))
                
                if len(backups) > 5:
                    for old_backup in backups[:-5]:
                        old_backup.unlink()
                        
            except Exception as e:
                print(f"Warning: Could not backup {file_path}: {e}")
    
    def _load_jobs_state(self) -> Dict[str, Any]:
        """Load jobs state from file."""
        try:
            with self._lock:
                with open(self.jobs_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading jobs state: {e}")
            return {"metadata": {}, "jobs": {}}
    
    def _save_jobs_state(self, state: Dict[str, Any]):
        """Save jobs state to file."""
        try:
            with self._lock:
                # Backup existing file
                self._backup_state_file(self.jobs_file)
                
                # Update metadata
                state["metadata"]["last_updated"] = datetime.now().isoformat()
                state["metadata"]["total_jobs"] = len(state.get("jobs", {}))
                
                # Save to file
                with open(self.jobs_file, 'w') as f:
                    json.dump(state, f, indent=2)
                    
        except Exception as e:
            print(f"Error saving jobs state: {e}")
    
    def _load_session_state(self) -> Dict[str, Any]:
        """Load session state from file."""
        try:
            with self._lock:
                with open(self.session_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading session state: {e}")
            return {"metadata": {}, "session": {}}
    
    def _save_session_state(self, state: Dict[str, Any]):
        """Save session state to file."""
        try:
            with self._lock:
                # Backup existing file
                self._backup_state_file(self.session_file)
                
                # Update metadata
                state["metadata"]["last_updated"] = datetime.now().isoformat()
                
                # Save to file
                with open(self.session_file, 'w') as f:
                    json.dump(state, f, indent=2)
                    
        except Exception as e:
            print(f"Error saving session state: {e}")
    
    def add_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """
        Add a new job to the state store.
        
        Args:
            job_id: Unique job identifier
            job_data: Job data dictionary
            
        Returns:
            True if job added successfully
        """
        try:
            state = self._load_jobs_state()
            
            job_entry = {
                "job_id": job_id,
                "job_data": job_data,
                "status": JobStatus.PENDING.value,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "attempts": 0,
                "max_attempts": self.settings.get("retry_policy", {}).get("max_attempts", self.DEFAULT_MAX_ATTEMPTS),
                "last_error": None,
                "diagnostics": [],
                "current_step": None,
                "start_time": None,
                "end_time": None,
                "export_metadata": None
            }
            
            state["jobs"][job_id] = job_entry
            self._save_jobs_state(state)
            
            return True
            
        except Exception as e:
            print(f"Error adding job {job_id}: {e}")
            return False
    
    def mark_job_status(self, job_id: str, status: JobStatus, error_message: Optional[str] = None, 
                       current_step: Optional[str] = None, diagnostics: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update job status and metadata.
        
        Args:
            job_id: Job identifier
            status: New job status
            error_message: Optional error message
            current_step: Current processing step
            diagnostics: Optional diagnostic information
            
        Returns:
            True if status updated successfully
        """
        try:
            state = self._load_jobs_state()
            
            if job_id not in state["jobs"]:
                print(f"Job {job_id} not found in state store")
                return False
            
            job = state["jobs"][job_id]
            
            # Update basic fields
            job["status"] = status.value
            job["updated_at"] = datetime.now().isoformat()
            
            if error_message:
                job["last_error"] = error_message
            
            if current_step:
                job["current_step"] = current_step
            
            # Handle status-specific updates
            if status == JobStatus.IN_PROGRESS:
                if not job["start_time"]:
                    job["start_time"] = datetime.now().isoformat()
                job["attempts"] += 1
            
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.SKIPPED]:
                job["end_time"] = datetime.now().isoformat()
            
            elif status == JobStatus.RETRYING:
                job["attempts"] += 1
            
            # Add diagnostics
            if diagnostics:
                job["diagnostics"].append({
                    "timestamp": datetime.now().isoformat(),
                    "status": status.value,
                    "step": current_step,
                    "data": diagnostics
                })
            
            self._save_jobs_state(state)
            return True
            
        except Exception as e:
            print(f"Error updating job {job_id} status: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job information by ID.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job dictionary or None if not found
        """
        try:
            state = self._load_jobs_state()
            return state["jobs"].get(job_id)
        except Exception as e:
            print(f"Error getting job {job_id}: {e}")
            return None
    
    def get_jobs_by_status(self, status: JobStatus) -> List[Dict[str, Any]]:
        """
        Get all jobs with specified status.
        
        Args:
            status: Job status to filter by
            
        Returns:
            List of job dictionaries
        """
        try:
            state = self._load_jobs_state()
            return [job for job in state["jobs"].values() if job["status"] == status.value]
        except Exception as e:
            print(f"Error getting jobs by status {status}: {e}")
            return []
    
    def get_pending_jobs(self) -> List[Dict[str, Any]]:
        """Get all pending jobs."""
        return self.get_jobs_by_status(JobStatus.PENDING)
    
    def get_failed_jobs(self) -> List[Dict[str, Any]]:
        """Get all failed jobs that can be retried."""
        try:
            state = self._load_jobs_state()
            failed_jobs = []
            
            for job in state["jobs"].values():
                if (job["status"] == JobStatus.FAILED.value and 
                    job["attempts"] < job["max_attempts"]):
                    failed_jobs.append(job)
            
            return failed_jobs
        except Exception as e:
            print(f"Error getting failed jobs: {e}")
            return []
    
    def resume_failed_jobs(self) -> List[str]:
        """
        Mark failed jobs as pending for retry.
        
        Returns:
            List of job IDs that were marked for retry
        """
        try:
            failed_jobs = self.get_failed_jobs()
            resumed_jobs = []
            
            for job in failed_jobs:
                job_id = job["job_id"]
                if self.mark_job_status(job_id, JobStatus.PENDING):
                    resumed_jobs.append(job_id)
                    print(f"Marked job {job_id} for retry (attempt {job['attempts'] + 1}/{job['max_attempts']})")
            
            return resumed_jobs
            
        except Exception as e:
            print(f"Error resuming failed jobs: {e}")
            return []
    
    def calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate backoff delay for retry attempts.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        retry_config = self.settings.get("retry_policy", {})
        
        base_backoff = retry_config.get("base_backoff_seconds", self.DEFAULT_BASE_BACKOFF)
        max_backoff = retry_config.get("max_backoff_seconds", self.DEFAULT_MAX_BACKOFF)
        multiplier = retry_config.get("backoff_multiplier", self.DEFAULT_BACKOFF_MULTIPLIER)
        use_jitter = retry_config.get("jitter", True)
        
        # Calculate exponential backoff
        delay = base_backoff * (multiplier ** (attempt - 1))
        delay = min(delay, max_backoff)
        
        # Add jitter to avoid thundering herd
        if use_jitter:
            jitter = random.uniform(0.1, 0.3) * delay
            delay += jitter
        
        return delay
    
    def update_session_state(self, last_state_saved_at: Optional[str] = None, 
                           session_valid: bool = False, state_file_path: Optional[str] = None) -> bool:
        """
        Update session state information.
        
        Args:
            last_state_saved_at: Timestamp when state was last saved
            session_valid: Whether session is currently valid
            state_file_path: Path to browser state file
            
        Returns:
            True if session state updated successfully
        """
        try:
            state = self._load_session_state()
            session = state.get("session", {})
            
            if last_state_saved_at:
                session["last_state_saved_at"] = last_state_saved_at
            
            session["session_valid"] = session_valid
            session["last_validation_at"] = datetime.now().isoformat()
            
            if state_file_path:
                session["state_file_path"] = state_file_path
            
            if session_valid:
                session["login_count"] = session.get("login_count", 0) + 1
            
            state["session"] = session
            self._save_session_state(state)
            
            return True
            
        except Exception as e:
            print(f"Error updating session state: {e}")
            return False
    
    def check_session_ttl(self) -> SessionStatus:
        """
        Check if session is still valid based on TTL.
        
        Returns:
            Session status
        """
        try:
            state = self._load_session_state()
            session = state.get("session", {})
            
            last_saved = session.get("last_state_saved_at")
            if not last_saved:
                return SessionStatus.INVALID
            
            # Parse timestamp
            try:
                last_saved_dt = datetime.fromisoformat(last_saved.replace('Z', '+00:00'))
            except:
                return SessionStatus.INVALID
            
            # Check TTL
            max_age = self.settings.get("session", {}).get("max_age_seconds", self.DEFAULT_SESSION_MAX_AGE)
            age_seconds = (datetime.now() - last_saved_dt.replace(tzinfo=None)).total_seconds()
            
            if age_seconds > max_age:
                return SessionStatus.EXPIRED
            elif age_seconds > max_age * 0.8:  # 80% of max age
                return SessionStatus.STALE
            else:
                return SessionStatus.VALID
                
        except Exception as e:
            print(f"Error checking session TTL: {e}")
            return SessionStatus.INVALID
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get current session information.
        
        Returns:
            Session information dictionary
        """
        try:
            state = self._load_session_state()
            session = state.get("session", {})
            
            # Add TTL status
            session["ttl_status"] = self.check_session_ttl().value
            
            return session
            
        except Exception as e:
            print(f"Error getting session info: {e}")
            return {}
    
    def get_job_statistics(self) -> Dict[str, Any]:
        """
        Get job statistics summary.
        
        Returns:
            Statistics dictionary
        """
        try:
            state = self._load_jobs_state()
            jobs = state.get("jobs", {})
            
            stats = {
                "total_jobs": len(jobs),
                "by_status": {},
                "retry_stats": {
                    "jobs_with_retries": 0,
                    "total_attempts": 0,
                    "max_attempts_reached": 0
                },
                "timing": {
                    "average_duration": None,
                    "completed_jobs": 0
                }
            }
            
            # Count by status
            for status in JobStatus:
                stats["by_status"][status.value] = 0
            
            total_duration = 0
            completed_count = 0
            
            for job in jobs.values():
                # Status counts
                status = job.get("status", "unknown")
                if status in stats["by_status"]:
                    stats["by_status"][status] += 1
                
                # Retry stats
                attempts = job.get("attempts", 0)
                max_attempts = job.get("max_attempts", 0)
                
                if attempts > 1:
                    stats["retry_stats"]["jobs_with_retries"] += 1
                
                stats["retry_stats"]["total_attempts"] += attempts
                
                if attempts >= max_attempts and status == JobStatus.FAILED.value:
                    stats["retry_stats"]["max_attempts_reached"] += 1
                
                # Timing stats
                if status == JobStatus.COMPLETED.value:
                    start_time = job.get("start_time")
                    end_time = job.get("end_time")
                    
                    if start_time and end_time:
                        try:
                            start_dt = datetime.fromisoformat(start_time)
                            end_dt = datetime.fromisoformat(end_time)
                            duration = (end_dt - start_dt).total_seconds()
                            total_duration += duration
                            completed_count += 1
                        except:
                            pass
            
            # Calculate average duration
            if completed_count > 0:
                stats["timing"]["average_duration"] = total_duration / completed_count
                stats["timing"]["completed_jobs"] = completed_count
            
            return stats
            
        except Exception as e:
            print(f"Error getting job statistics: {e}")
            return {}
    
    def cleanup_old_diagnostics(self, days_to_keep: int = 7):
        """
        Clean up old diagnostic files and backups.
        
        Args:
            days_to_keep: Number of days to keep files
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            
            # Clean up screenshot files
            screenshot_patterns = [
                "export_handler_*.png",
                "generation_watcher_*.png", 
                "error_*.png",
                "*.bak.*"
            ]
            
            cleaned_count = 0
            
            for pattern in screenshot_patterns:
                for file_path in self.state_dir.glob(pattern):
                    try:
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_time:
                            file_path.unlink()
                            cleaned_count += 1
                    except Exception as e:
                        print(f"Warning: Could not clean up {file_path}: {e}")
            
            if cleaned_count > 0:
                print(f"Cleaned up {cleaned_count} old diagnostic files")
                
        except Exception as e:
            print(f"Error during cleanup: {e}")


# Convenience functions
def create_state_store(project_root: Optional[str] = None) -> StateStore:
    """Create a StateStore instance."""
    return StateStore(project_root)


def mark_job_status(job_id: str, status: JobStatus, error_message: Optional[str] = None,
                   current_step: Optional[str] = None, diagnostics: Optional[Dict[str, Any]] = None,
                   state_store: Optional[StateStore] = None) -> bool:
    """
    Convenience function to mark job status.
    
    Args:
        job_id: Job identifier
        status: New job status
        error_message: Optional error message
        current_step: Current processing step
        diagnostics: Optional diagnostic information
        state_store: Optional StateStore instance
        
    Returns:
        True if status updated successfully
    """
    if not state_store:
        state_store = StateStore()
    
    return state_store.mark_job_status(job_id, status, error_message, current_step, diagnostics)


def get_pending_jobs(state_store: Optional[StateStore] = None) -> List[Dict[str, Any]]:
    """
    Convenience function to get pending jobs.
    
    Args:
        state_store: Optional StateStore instance
        
    Returns:
        List of pending jobs
    """
    if not state_store:
        state_store = StateStore()
    
    return state_store.get_pending_jobs()


def resume_failed_jobs(state_store: Optional[StateStore] = None) -> List[str]:
    """
    Convenience function to resume failed jobs.
    
    Args:
        state_store: Optional StateStore instance
        
    Returns:
        List of resumed job IDs
    """
    if not state_store:
        state_store = StateStore()
    
    return state_store.resume_failed_jobs()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CapCut Automation - State Store")
    parser.add_argument('--inspect', action='store_true', help='Inspect current job states')
    parser.add_argument('--resume', action='store_true', help='Resume failed jobs')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='Clean up files older than DAYS')
    parser.add_argument('--stats', action='store_true', help='Show job statistics')
    parser.add_argument('--session', action='store_true', help='Show session information')
    
    args = parser.parse_args()
    
    # Create state store
    store = StateStore()
    
    if args.inspect:
        print("=" * 60)
        print("Job State Inspection")
        print("=" * 60)
        
        # Load and display job states
        state = store._load_jobs_state()
        jobs = state.get("jobs", {})
        
        if not jobs:
            print("No jobs found in state store")
        else:
            print(f"Total jobs: {len(jobs)}")
            print()
            
            # Group by status
            by_status = {}
            for job in jobs.values():
                status = job.get("status", "unknown")
                if status not in by_status:
                    by_status[status] = []
                by_status[status].append(job)
            
            for status, job_list in by_status.items():
                print(f"{status.upper()} ({len(job_list)} jobs):")
                for job in job_list[:5]:  # Show first 5
                    job_id = job.get("job_id", "unknown")
                    title = job.get("job_data", {}).get("title", "No title")
                    attempts = job.get("attempts", 0)
                    max_attempts = job.get("max_attempts", 0)
                    
                    print(f"  {job_id}: '{title}' (attempts: {attempts}/{max_attempts})")
                
                if len(job_list) > 5:
                    print(f"  ... and {len(job_list) - 5} more")
                print()
    
    elif args.resume:
        print("=" * 60)
        print("Resuming Failed Jobs")
        print("=" * 60)
        
        resumed_jobs = store.resume_failed_jobs()
        
        if resumed_jobs:
            print(f"Resumed {len(resumed_jobs)} failed jobs:")
            for job_id in resumed_jobs:
                print(f"  {job_id}")
        else:
            print("No failed jobs to resume")
    
    elif args.cleanup is not None:
        print("=" * 60)
        print(f"Cleaning up files older than {args.cleanup} days")
        print("=" * 60)
        
        store.cleanup_old_diagnostics(args.cleanup)
    
    elif args.stats:
        print("=" * 60)
        print("Job Statistics")
        print("=" * 60)
        
        stats = store.get_job_statistics()
        
        print(f"Total jobs: {stats['total_jobs']}")
        print()
        
        print("By status:")
        for status, count in stats["by_status"].items():
            if count > 0:
                print(f"  {status}: {count}")
        print()
        
        retry_stats = stats["retry_stats"]
        print("Retry statistics:")
        print(f"  Jobs with retries: {retry_stats['jobs_with_retries']}")
        print(f"  Total attempts: {retry_stats['total_attempts']}")
        print(f"  Max attempts reached: {retry_stats['max_attempts_reached']}")
        print()
        
        timing = stats["timing"]
        if timing["average_duration"]:
            print(f"Average job duration: {timing['average_duration']:.1f} seconds")
            print(f"Completed jobs: {timing['completed_jobs']}")
    
    elif args.session:
        print("=" * 60)
        print("Session Information")
        print("=" * 60)
        
        session_info = store.get_session_info()
        
        print(f"Session valid: {session_info.get('session_valid', False)}")
        print(f"TTL status: {session_info.get('ttl_status', 'unknown')}")
        print(f"Last saved: {session_info.get('last_state_saved_at', 'never')}")
        print(f"Last validation: {session_info.get('last_validation_at', 'never')}")
        print(f"Login count: {session_info.get('login_count', 0)}")
        
        state_file = session_info.get('state_file_path')
        if state_file:
            print(f"State file: {state_file}")
    
    else:
        print("State Store Module")
        print("Use --help for available commands")
        print()
        print("Quick commands:")
        print("  --inspect    Show current job states")
        print("  --resume     Resume failed jobs")
        print("  --stats      Show job statistics")
        print("  --session    Show session information")
