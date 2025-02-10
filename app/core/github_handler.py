"""
GitHub repository handler for the File Concatenator application.
This module provides functionality to clone GitHub repositories and manage temporary directories.
"""

import git
import tempfile
import os
from typing import Optional, Tuple
from pathlib import Path
import logging
import re
import uuid
from datetime import datetime, timedelta
import hashlib
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import aiohttp

from app.models.schemas import (
    GitHubError,
    RepositoryNotFoundError,
    InvalidRepositoryError,
    AuthenticationError,
    RateLimitError,
    FileSystemError,
    CacheError
)

logger = logging.getLogger(__name__)

class GitHubHandler:
    """Handles GitHub repository operations including cloning and temporary directories with caching."""
    
    def __init__(self, cache_dir: str, github_token: str, cache_ttl: int = 3600):
        self.cache_dir = cache_dir
        self.github_token = github_token
        self.cache_ttl = cache_ttl
        self.session = aiohttp.ClientSession()
        self._cleanup_task = None
        self._temp_dir = None
        self._cache_ttl = timedelta(hours=cache_ttl if cache_ttl is not None else 1)
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Setup cache directory
        if cache_dir:
            self._cache_dir = Path(cache_dir)
        else:
            self._cache_dir = Path(tempfile.gettempdir()) / "file_concatenator_cache"
        
        # Ensure cache directory exists and is writable
        try:
            self._cache_dir.mkdir(exist_ok=True)
            # Test write access
            test_file = self._cache_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            raise FileSystemError(f"Cannot create or access cache directory: {e}", str(self._cache_dir))
        
    async def initialize(self):
        """Async initialization method"""
        await self._start_cleanup_task()
    
    async def _start_cleanup_task(self):
        """Start the cleanup task asynchronously"""
        self._cleanup_task = asyncio.create_task(self._cleanup_old_cache())
    
    async def _cleanup_old_cache(self):
        """Periodically clean up expired cache entries."""
        while True:
            try:
                now = datetime.now()
                for cache_entry in self._cache_dir.iterdir():
                    if cache_entry.is_dir():
                        try:
                            mtime = datetime.fromtimestamp(cache_entry.stat().st_mtime)
                            if now - mtime > self._cache_ttl:
                                try:
                                    shutil.rmtree(cache_entry)
                                    logger.info(f"Cleaned up expired cache: {cache_entry}")
                                except Exception as e:
                                    logger.error(f"Error cleaning up cache {cache_entry}: {e}")
                        except Exception as e:
                            logger.error(f"Error checking cache entry {cache_entry}: {e}")
                
                # Sleep for 1 hour before next cleanup
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
                await asyncio.sleep(3600)  # Retry after an hour
    
    def validate_github_url(self, url: str) -> Tuple[str, str, Optional[str]]:
        """
        Validate and parse GitHub repository URL.
        
        Args:
            url: The repository URL to validate
            
        Returns:
            Tuple[str, str, Optional[str]]: The owner, repository name, and optional subdirectory path
            
        Raises:
            InvalidRepositoryError: If the URL is not a valid GitHub repository URL
        """
        try:
            # Clean up the URL first
            url = url.strip()
            # Remove any parentheses and @ symbols
            url = url.replace('(', '').replace(')', '').replace('@', '')
            
            parsed = urlparse(url)
            if parsed.netloc != "github.com":
                raise InvalidRepositoryError(url, "Not a GitHub URL")
            
            # Remove .git extension and split path
            path = parsed.path.rstrip(".git").strip("/")
            parts = path.split("/")
            
            if len(parts) < 2:
                raise InvalidRepositoryError(
                    url, 
                    "Invalid repository path. URL should be in format: https://github.com/owner/repository[/path/to/directory]"
                )
                
            owner, repo = parts[0], parts[1]
            if not owner or not repo:
                raise InvalidRepositoryError(
                    url, 
                    "Missing owner or repository name. URL should be in format: https://github.com/owner/repository[/path/to/directory]"
                )

            # Extract subdirectory path if it exists
            subdir = None
            if len(parts) > 2:
                if parts[2] == "tree" and len(parts) > 3:
                    # Handle GitHub web UI URLs (/tree/branch/path/to/dir)
                    subdir = "/".join(parts[4:]) if len(parts) > 4 else None
                else:
                    # Handle direct paths (/path/to/dir)
                    subdir = "/".join(parts[2:])
                
            return owner, repo, subdir
            
        except Exception as e:
            if isinstance(e, InvalidRepositoryError):
                raise
            raise InvalidRepositoryError(
                url, 
                f"Invalid GitHub URL format. Please use format: https://github.com/owner/repository[/path/to/directory]. Error: {str(e)}"
            )
    
    def _get_repo_hash(self, repo_url: str, github_token: Optional[str] = None) -> str:
        """Generate a unique hash for the repository."""
        # Include token in hash if provided to handle private repos differently
        hash_input = f"{repo_url}:{github_token if github_token else ''}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def _get_cached_repo(self, repo_url: str, github_token: Optional[str] = None) -> Optional[Path]:
        """
        Check if a valid cached version of the repository exists.
        
        Raises:
            CacheError: If there's an error accessing the cache
        """
        try:
            repo_hash = self._get_repo_hash(repo_url, github_token)
            cache_path = self._cache_dir / repo_hash
            
            if cache_path.exists():
                try:
                    # Check if cache is still valid
                    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
                    if datetime.now() - mtime < self._cache_ttl:
                        # Verify cache integrity
                        if not (cache_path / ".git").exists():
                            raise CacheError("Cache corrupted: .git directory missing")
                        # Update access time to prevent cleanup
                        os.utime(cache_path, None)
                        return cache_path
                except Exception as e:
                    if isinstance(e, CacheError):
                        raise
                    raise CacheError(f"Error validating cache: {e}")
            return None
        except Exception as e:
            if isinstance(e, CacheError):
                raise
            raise CacheError(f"Error accessing cache: {e}")
    
    def __enter__(self):
        """Context manager entry point."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point that ensures cleanup of temporary directory."""
        self.cleanup()
        
    def cleanup(self):
        """Clean up temporary directory if it exists."""
        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up temporary directory: {e}")
            finally:
                self._temp_dir = None

    def _extract_repo_name(self, repo_url: str) -> str:
        """Extract repository name from URL."""
        try:
            owner, repo, _ = self.validate_github_url(repo_url)  # Add _ to unpack the third value (subdir)
            return re.sub(r'[^\w\-]', '_', repo)
        except InvalidRepositoryError:
            # Fall back to basic extraction if validation fails
            repo_url = repo_url.rstrip('.git')
            repo_name = repo_url.split('/')[-1]
            return re.sub(r'[^\w\-]', '_', repo_name)

    def _generate_unique_dir_name(self, repo_name: str) -> str:
        """Generate a unique directory name."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # Include microseconds
        unique_id = uuid.uuid4().hex[:8]  # 8 characters from UUID
        pid = os.getpid()  # Process ID
        return f"{repo_name}_{timestamp}_pid{pid}_{unique_id}"

    async def clone_repository(self, repo_url: str, github_token: Optional[str] = None) -> Tuple[Path, Optional[str]]:
        """
        Clone a GitHub repository to a temporary directory with caching.
        
        Args:
            repo_url (str): The URL of the GitHub repository to clone
            github_token (Optional[str]): GitHub personal access token for private repositories
            
        Returns:
            Tuple[Path, Optional[str]]: Path to the cloned repository directory and optional subdirectory path
            
        Raises:
            RepositoryNotFoundError: If the repository doesn't exist
            AuthenticationError: If authentication fails
            RateLimitError: If GitHub API rate limit is exceeded
            GitHubError: For other GitHub-related errors
            FileSystemError: For filesystem-related errors
            CacheError: For cache-related errors
        """
        try:
            # Validate repository URL and get subdirectory if specified
            owner, repo, subdir = self.validate_github_url(repo_url)
            
            # Construct base repository URL
            base_repo_url = f"https://github.com/{owner}/{repo}"
            
            # Check cache first
            try:
                if cached_path := self._get_cached_repo(base_repo_url, github_token):
                    logger.info(f"Using cached repository: {base_repo_url}")
                    # Verify subdirectory exists if specified
                    if subdir:
                        subdir_path = cached_path / subdir
                        if not subdir_path.exists():
                            raise FileSystemError(f"Specified directory not found: {subdir}", str(subdir_path))
                    return cached_path, subdir
            except CacheError as e:
                logger.warning(f"Cache error, falling back to fresh clone: {e}")
            
            # Extract repository name and generate unique directory name
            repo_name = self._extract_repo_name(base_repo_url)
            repo_hash = self._get_repo_hash(base_repo_url, github_token)
            cache_path = self._cache_dir / repo_hash
            
            # Ensure cache directory is clean
            if cache_path.exists():
                try:
                    shutil.rmtree(cache_path)
                except Exception as e:
                    raise FileSystemError(f"Cannot clean existing cache: {e}", str(cache_path))
            
            # Modify URL if token is provided
            clone_url = base_repo_url
            if github_token:
                if clone_url.startswith("https://"):
                    clone_url = clone_url.replace("https://", f"https://{github_token}@")
                else:
                    raise InvalidRepositoryError(repo_url, "Must use HTTPS protocol when using a token")
            
            # Clone the repository to cache directory
            logger.info(f"Cloning repository: {base_repo_url} to cache")
            
            # Use ThreadPoolExecutor for blocking git operations
            def clone_repo():
                try:
                    git.Repo.clone_from(clone_url, cache_path)
                    # Verify subdirectory exists if specified
                    if subdir:
                        subdir_path = cache_path / subdir
                        if not subdir_path.exists():
                            raise FileSystemError(f"Specified directory not found: {subdir}", str(subdir_path))
                    return cache_path
                except git.exc.GitCommandError as e:
                    error_msg = str(e)
                    if "not found" in error_msg.lower() or "repository not found" in error_msg.lower():
                        raise RepositoryNotFoundError(base_repo_url)
                    elif "authentication" in error_msg.lower() or "authorization" in error_msg.lower():
                        raise AuthenticationError()
                    elif "rate limit" in error_msg.lower():
                        raise RateLimitError()
                    else:
                        raise GitHubError(f"Git error: {error_msg}")
            
            cloned_path = await asyncio.get_event_loop().run_in_executor(
                self._executor, 
                clone_repo
            )
            return cloned_path, subdir
            
        except Exception as e:
            # Clean up any partial cache
            try:
                if 'cache_path' in locals() and cache_path.exists():
                    shutil.rmtree(cache_path)
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up after failed clone: {cleanup_error}")
            
            # Re-raise appropriate exception
            if isinstance(e, (RepositoryNotFoundError, AuthenticationError, RateLimitError, 
                            GitHubError, FileSystemError, CacheError, InvalidRepositoryError)):
                raise
            raise GitHubError(f"Unexpected error while cloning repository: {str(e)}")
    
    def __del__(self):
        """Cleanup on object destruction."""
        self.cleanup()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self._executor.shutdown(wait=False) 