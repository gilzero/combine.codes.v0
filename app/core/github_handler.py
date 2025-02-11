"""
GitHub repository handler for the File Concatenator application.
This module provides functionality to clone GitHub repositories and manage temporary directories.
"""

import git
import tempfile
import os
from typing import Optional, Dict, Any
from pathlib import Path
import logging
import re
import uuid
from datetime import datetime
import hashlib
import shutil
import asyncio
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from app.models.schemas import (
    GitHubConfig,
    GitHubRepoInfo,
    CacheInfo,
    CloneResult,
    GitHubError,
    RepositoryNotFoundError,
    InvalidRepositoryError,
    AuthenticationError,
    FileSystemError,
    CacheError
)
from app.config.ignore_patterns import get_system_ignores

logger = logging.getLogger(__name__)

class GitHubHandler:
    """Handles GitHub repository operations including cloning and temporary directories with caching."""
    
    def __init__(self, cache_dir: Optional[str] = None, github_token: Optional[str] = None, cache_ttl: int = 3600):
        self.config = GitHubConfig(
            cache_dir=cache_dir,
            github_token=github_token,
            cache_ttl=cache_ttl
        )
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
            clone_url = f"{base_url}.git"
            
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

    async def pre_check_repository(self, repo_url: str, github_token: Optional[str] = None) -> GitHubRepoInfo:
        """
        Quick check if a repository exists and is accessible.
        Does a lightweight clone to get accurate file information.
        """
        try:
            # Parse repository URL and get info
            repo_info = self.validate_github_url(repo_url)
            logger.info(f"Validating repository URL: {repo_url}")
            
            # Create a temporary directory for the clone
            temp_dir = Path(tempfile.mkdtemp(prefix="repo_precheck_"))
            
            try:
                # Modify URL if token is provided
                clone_url = repo_info.clone_url
                if github_token or self.config.github_token:
                    token = github_token or self.config.github_token
                    clone_url = clone_url.replace("https://", f"https://{token}@")

                # Use ThreadPoolExecutor for blocking git operations
                def check_repo():
                    try:
                        # Do a shallow clone (depth=1) to minimize download
                        logger.info(f"Performing shallow clone to check repository")
                        git.Repo.clone_from(clone_url, temp_dir, depth=1, branch="main")  # Explicitly checkout main branch
                        repo = git.Repo(temp_dir)

                        # Load repository's .gitignore patterns if they exist
                        repo_ignores = []
                        gitignore_path = temp_dir / ".gitignore"
                        if gitignore_path.exists():
                            with open(gitignore_path, "r") as f:
                                repo_ignores = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                        
                        # Get combined ignore patterns
                        from app.config.ignore_patterns import combine_ignore_patterns
                        all_ignores = combine_ignore_patterns(repo_ignores)
                        logger.info("Using combined ignore patterns:")
                        for pattern in all_ignores:
                            logger.info(f"- {pattern}")

                        # Calculate actual file information
                        total_size = 0
                        file_count = 0

                        # Walk through the repository
                        target_dir = temp_dir
                        if repo_info.subdir:
                            target_dir = temp_dir / repo_info.subdir
                            if not target_dir.exists():
                                logger.warning(f"Subdirectory not found at expected path: {target_dir}")
                                raise FileSystemError(f"Specified directory not found: {repo_info.subdir}")

                        for root, _, files in os.walk(target_dir):
                            # Skip ignored directories
                            rel_root = str(Path(root).relative_to(temp_dir))
                            if any(PathSpec.from_lines(GitWildMatchPattern, [pattern]).match_file(rel_root) 
                                  for pattern in all_ignores):
                                continue
                            
                            for file in files:
                                file_path = Path(root) / file
                                rel_path = str(file_path.relative_to(temp_dir))
                                
                                # Skip ignored files
                                if any(PathSpec.from_lines(GitWildMatchPattern, [pattern]).match_file(rel_path) 
                                      for pattern in all_ignores):
                                    continue
                                
                                try:
                                    # Get actual file size
                                    size = file_path.stat().st_size
                                    total_size += size
                                    file_count += 1
                                except Exception as e:
                                    logger.warning(f"Error getting file info for {file_path}: {e}")

                        # Convert total size to KB
                        size_kb = total_size / 1024

                        logger.info(f"Repository scan results for {repo_info.base_url}:")
                        logger.info(f"Total files: {file_count}")
                        logger.info(f"Total size: {size_kb:.2f}KB")

                        repo_info.size_kb = float(size_kb)
                        repo_info.file_count = int(file_count)
                        return True

                    except git.exc.GitCommandError as e:
                        error_msg = str(e).lower()
                        if "not found" in error_msg or "repository not found" in error_msg:
                            raise RepositoryNotFoundError(repo_info.base_url)
                        elif "authentication" in error_msg or "authorization" in error_msg:
                            raise AuthenticationError("Repository requires authentication")
                        else:
                            raise GitHubError(f"Git error: {error_msg}")

                await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    check_repo
                )

                return repo_info

            finally:
                # Clean up temporary directory
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.error(f"Error cleaning up temporary directory: {e}")

        except Exception as e:
            logger.error(f"Error pre-checking repository: {str(e)}", exc_info=True)
            if isinstance(e, (RepositoryNotFoundError, AuthenticationError, GitHubError, FileSystemError)):
                raise
            raise GitHubError(f"Unexpected error while checking repository: {str(e)}")

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
                clone_url = clone_url.replace("https://", f"https://{self.config.github_token}@")
            
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
                    error_msg = str(e).lower()
                    if "not found" in error_msg or "repository not found" in error_msg:
                        raise RepositoryNotFoundError(repo_info.base_url)
                    elif "authentication" in error_msg or "authorization" in error_msg:
                        raise AuthenticationError("Repository requires authentication")
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
            if isinstance(e, (RepositoryNotFoundError, AuthenticationError, 
                            GitHubError, FileSystemError, CacheError, InvalidRepositoryError)):
                raise
            raise GitHubError(f"Unexpected error while cloning repository: {str(e)}")
    
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

    def __del__(self):
        """Cleanup on object destruction."""
        self.cleanup()
        self._executor.shutdown(wait=False) 