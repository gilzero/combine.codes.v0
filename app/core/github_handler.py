"""
GitHub repository handler for the File Concatenator application.
This module provides functionality to clone GitHub repositories and manage temporary directories.
"""

import git
import tempfile
import os
from typing import Optional, Tuple, Dict, Any
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
    GitHubConfig,
    GitHubRepoInfo,
    CacheInfo,
    CloneResult,
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
    
    def __init__(self, cache_dir: Optional[str] = None, github_token: Optional[str] = None, cache_ttl: int = 3600):
        self.config = GitHubConfig(
            cache_dir=cache_dir,
            github_token=github_token,
            cache_ttl=cache_ttl
        )
        self._session = None
        self._cleanup_task = None
        self._temp_dir = None
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        
        # Setup cache directory
        if self.config.cache_dir:
            self._cache_dir = Path(self.config.cache_dir)
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
        
    @property
    async def session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

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
                            if now - mtime > self.config.cache_ttl_delta:
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
    
    def validate_github_url(self, url: str) -> GitHubRepoInfo:
        """
        Validate and parse GitHub repository URL.
        
        Args:
            url: The repository URL to validate
            
        Returns:
            GitHubRepoInfo: Repository information
            
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
                
            base_url = f"https://github.com/{owner}/{repo}"
            clone_url = base_url
            
            return GitHubRepoInfo(
                owner=owner,
                repo_name=repo,
                subdir=subdir,
                base_url=base_url,
                clone_url=clone_url
            )
            
        except Exception as e:
            if isinstance(e, InvalidRepositoryError):
                raise
            raise InvalidRepositoryError(
                url, 
                f"Invalid GitHub URL format. Please use format: https://github.com/owner/repository[/path/to/directory]. Error: {str(e)}"
            )
    
    def _get_repo_hash(self, repo_info: GitHubRepoInfo) -> str:
        """Generate a unique hash for the repository."""
        # Include token in hash if provided to handle private repos differently
        hash_input = f"{repo_info.base_url}:{self.config.github_token if self.config.github_token else ''}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def _get_cached_repo(self, repo_info: GitHubRepoInfo) -> Optional[CacheInfo]:
        """
        Check if a valid cached version of the repository exists.
        
        Raises:
            CacheError: If there's an error accessing the cache
        """
        try:
            repo_hash = self._get_repo_hash(repo_info)
            cache_path = self._cache_dir / repo_hash
            
            if cache_path.exists():
                try:
                    # Check if cache is still valid
                    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
                    now = datetime.now()
                    expires_at = mtime + self.config.cache_ttl_delta
                    
                    if now < expires_at:
                        # Verify cache integrity
                        if not (cache_path / ".git").exists():
                            raise CacheError("Cache corrupted: .git directory missing")
                        # Update access time to prevent cleanup
                        os.utime(cache_path, None)
                        return CacheInfo(
                            cache_path=cache_path,
                            is_valid=True,
                            created_at=mtime,
                            expires_at=expires_at
                        )
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

    async def clone_repository(self, repo_url: str, github_token: Optional[str] = None) -> CloneResult:
        """
        Clone a GitHub repository to a temporary directory with caching.
        
        Args:
            repo_url (str): The URL of the GitHub repository to clone
            github_token (Optional[str]): GitHub personal access token for private repositories
            
        Returns:
            CloneResult: Result of the clone operation
            
        Raises:
            RepositoryNotFoundError: If the repository doesn't exist
            AuthenticationError: If authentication fails
            RateLimitError: If GitHub API rate limit is exceeded
            GitHubError: For other GitHub-related errors
            FileSystemError: For filesystem-related errors
            CacheError: For cache-related errors
        """
        try:
            # Override token if provided
            if github_token:
                self.config.github_token = github_token
                
            # Validate repository URL and get info
            repo_info = self.validate_github_url(repo_url)
            
            # Check cache first
            try:
                if cache_info := self._get_cached_repo(repo_info):
                    logger.info(f"Using cached repository: {repo_info.base_url}")
                    # Verify subdirectory exists if specified
                    if repo_info.subdir:
                        subdir_path = cache_info.cache_path / repo_info.subdir
                        if not subdir_path.exists():
                            raise FileSystemError(f"Specified directory not found: {repo_info.subdir}", str(subdir_path))
                    return CloneResult(
                        repo_path=cache_info.cache_path,
                        subdir=repo_info.subdir,
                        from_cache=True,
                        cache_info=cache_info
                    )
            except CacheError as e:
                logger.warning(f"Cache error, falling back to fresh clone: {e}")
            
            # Generate cache path
            repo_hash = self._get_repo_hash(repo_info)
            cache_path = self._cache_dir / repo_hash
            
            # Ensure cache directory is clean
            if cache_path.exists():
                try:
                    shutil.rmtree(cache_path)
                except Exception as e:
                    raise FileSystemError(f"Cannot clean existing cache: {e}", str(cache_path))
            
            # Modify URL if token is provided
            clone_url = repo_info.clone_url
            if self.config.github_token:
                if clone_url.startswith("https://"):
                    clone_url = clone_url.replace("https://", f"https://{self.config.github_token}@")
                else:
                    raise InvalidRepositoryError(repo_url, "Must use HTTPS protocol when using a token")
            
            # Clone the repository to cache directory
            logger.info(f"Cloning repository: {repo_info.base_url} to cache")
            
            # Use ThreadPoolExecutor for blocking git operations
            def clone_repo():
                try:
                    git.Repo.clone_from(clone_url, cache_path)
                    # Verify subdirectory exists if specified
                    if repo_info.subdir:
                        subdir_path = cache_path / repo_info.subdir
                        if not subdir_path.exists():
                            raise FileSystemError(f"Specified directory not found: {repo_info.subdir}", str(subdir_path))
                    return cache_path
                except git.exc.GitCommandError as e:
                    error_msg = str(e)
                    if "not found" in error_msg.lower() or "repository not found" in error_msg.lower():
                        raise RepositoryNotFoundError(repo_info.base_url)
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
            
            # Create cache info for the newly cloned repository
            now = datetime.now()
            cache_info = CacheInfo(
                cache_path=cloned_path,
                is_valid=True,
                created_at=now,
                expires_at=now + self.config.cache_ttl_delta
            )
            
            return CloneResult(
                repo_path=cloned_path,
                subdir=repo_info.subdir,
                from_cache=False,
                cache_info=cache_info
            )
            
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
        if self._session and not self._session.closed:
            logger.warning("Session was not properly closed. Use 'await github_handler.close()' for cleanup.")
        self.cleanup()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self._executor.shutdown(wait=False)

    async def _make_github_request(self, url: str, headers: dict, auth_token: Optional[str] = None) -> Tuple[dict, int]:
        """Make a request to GitHub API with proper error handling."""
        request_headers = headers.copy()
        if auth_token:
            request_headers["Authorization"] = f"token {auth_token}"
        
        session = await self.session
        async with session.get(url, headers=request_headers) as response:
            response_text = await response.text()
            logger.debug(f"GitHub API response status: {response.status}")
            logger.debug(f"GitHub API response headers: {dict(response.headers)}")
            logger.debug(f"GitHub API response body: {response_text}")
            
            try:
                response_data = await response.json()
            except ValueError:
                response_data = {}
                
            return response_data, response.status

    def _get_base_headers(self) -> dict:
        """Get base headers for GitHub API requests."""
        return {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "File-Concatenator-App/1.0 (https://github.com/gilzero/combinefile-fetch-github)"
        }

    def _validate_token(self, token: Optional[str]) -> Optional[str]:
        """Validate GitHub token format."""
        if not token:  # Return None for empty/None tokens
            return None
            
        token = token.strip()
        if not token:  # Return None for whitespace-only tokens
            return None
            
        # Only validate non-empty tokens
        if len(token) < 30:
            logger.warning("Token appears to be too short for a GitHub token")
            return None
            
        return token

    async def _handle_error_response(self, status: int, response_data: dict, response_text: str) -> None:
        """Handle GitHub API error responses."""
        if status == 404:
            logger.error("Repository not found")
            raise RepositoryNotFoundError(repo_url="")
        elif status == 401:
            logger.error("Authentication failed - Invalid token")
            raise AuthenticationError("Invalid GitHub token")
        elif status == 403:
            if "rate limit exceeded" in response_text.lower():
                logger.error("Rate limit exceeded")
                raise RateLimitError()
            else:
                logger.error("Token lacks required permissions")
                raise AuthenticationError("Token lacks required permissions")
        else:
            logger.error(f"Unexpected GitHub API error: {status}")
            raise GitHubError(f"GitHub API error: {status} - {response_text}")

    async def pre_check_repository(self, repo_url: str, github_token: Optional[str] = None) -> GitHubRepoInfo:
        """
        Pre-check a repository to get basic information without cloning.
        Returns repository stats including name, owner, and size.
        """
        try:
            # Parse repository URL and get info
            repo_info = self.validate_github_url(repo_url)
            logger.info(f"Validating repository URL: {repo_url}")
            logger.info(f"Repository info - Owner: {repo_info.owner}, Repo: {repo_info.repo_name}")
            
            # Setup request
            headers = self._get_base_headers()
            api_url = f"https://api.github.com/repos/{repo_info.owner}/{repo_info.repo_name}"
            
            # Try public access first
            logger.info(f"Attempting public access for repository: {repo_info.owner}/{repo_info.repo_name}")
            repo_data, status = await self._make_github_request(api_url, headers)
            
            if status == 200:
                logger.info("Successfully accessed public repository")
                repo_info.size = repo_data.get("size", 0)
                repo_info.estimated_file_count = repo_data.get("size", 0) // 2
                return repo_info
            
            # If public access fails, try with token
            token = self._validate_token(github_token or self.config.github_token)
            if token:
                logger.info("Attempting authenticated access")
                repo_data, status = await self._make_github_request(api_url, headers, token)
                
                if status == 200:
                    logger.info("Successfully accessed repository with authentication")
                    repo_info.size = repo_data.get("size", 0)
                    repo_info.estimated_file_count = repo_data.get("size", 0) // 2
                    return repo_info
                
                await self._handle_error_response(status, repo_data, str(repo_data))
            else:
                # If no valid token and public access failed, handle the original error
                logger.error("No valid token provided and public access failed")
                await self._handle_error_response(status, repo_data, str(repo_data))
            
            return repo_info  # This line will not be reached due to error handling
            
        except Exception as e:
            logger.error(f"Error pre-checking repository: {str(e)}", exc_info=True)
            if isinstance(e, (RepositoryNotFoundError, AuthenticationError, RateLimitError, GitHubError)):
                raise
            raise GitHubError(f"Unexpected error while checking repository: {str(e)}")

    async def close(self):
        """Close the session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self._executor.shutdown(wait=False)
        self.cleanup() 