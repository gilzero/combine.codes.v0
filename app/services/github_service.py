"""
@fileoverview
This module defines the GitHubService class, which provides high-level operations
for validating and processing GitHub repositories. It includes methods for
validating GitHub URLs, processing repositories by cloning and concatenating files,
and handling various exceptions related to GitHub operations.
"""

from typing import Tuple, Optional, Dict, Any
import re
from urllib.parse import urlparse
import logging
from pathlib import Path

from app.core.github_handler import GitHubHandler
from app.core.file_concatenator import FileConcatenator
from app.models.schemas import (
    InvalidRepositoryError,
    RepositoryNotFoundError,
    AuthenticationError,
    RateLimitError
)

logger = logging.getLogger(__name__)

class GitHubService:
    """Service for handling GitHub repository operations."""
    
    def __init__(self):
        """Initialize the GitHub service with a GitHubHandler instance."""
        self.github_handler = GitHubHandler()
    
    def validate_github_url(self, url: str) -> Tuple[str, str]:
        """
        Validate and parse a GitHub repository URL.
        
        Args:
            url (str): The repository URL to validate.
            
        Returns:
            Tuple[str, str]: A tuple containing the repository owner and name.
            
        Raises:
            InvalidRepositoryError: If the URL is invalid or not a GitHub URL.
        """
        try:
            # Clean up the URL
            url = url.strip()
            url = url.replace('(', '').replace(')', '').replace('@', '')
            
            # Parse URL
            parsed = urlparse(url)
            if parsed.netloc != "github.com":
                raise InvalidRepositoryError(url, "Not a GitHub URL")
            
            # Remove .git extension and split path
            path = parsed.path.rstrip(".git").strip("/")
            parts = path.split("/")
            
            if len(parts) < 2:
                raise InvalidRepositoryError(
                    url, 
                    "Invalid repository path. URL should be in format: https://github.com/owner/repository"
                )
            
            owner, repo = parts[0], parts[1]
            if not owner or not repo:
                raise InvalidRepositoryError(
                    url, 
                    "Missing owner or repository name"
                )
            
            # Basic validation of owner and repo names
            if not re.match(r'^[\w.-]+$', owner) or not re.match(r'^[\w.-]+$', repo):
                raise InvalidRepositoryError(
                    url,
                    "Invalid characters in repository owner or name"
                )
            
            return owner, repo
            
        except Exception as e:
            if isinstance(e, InvalidRepositoryError):
                raise
            raise InvalidRepositoryError(
                url, 
                f"Invalid GitHub URL format: {str(e)}"
            )
    
    async def process_repository(
        self,
        repo_url: str,
        file_pattern: Optional[str] = None,
        github_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a GitHub repository by cloning it and concatenating its files.
        
        Args:
            repo_url (str): The repository URL to process.
            file_pattern (Optional[str]): Optional pattern for filtering files.
            github_token (Optional[str]): Optional GitHub token for private repositories.
            
        Returns:
            Dict[str, Any]: A dictionary containing processing results and statistics.
            
        Raises:
            Various exceptions from github_handler and concatenator.
        """
        try:
            # Validate repository URL first
            owner, repo = self.validate_github_url(repo_url)
            
            # Clone the repository
            repo_path, subdir = await self.github_handler.clone_repository(
                repo_url=repo_url,
                github_token=github_token
            )
            
            # Determine base directory
            base_dir = repo_path
            if subdir:
                base_dir = repo_path / subdir
            
            # Create concatenator
            concatenator = FileConcatenator(
                base_dir=str(base_dir),
                file_pattern=file_pattern
            )
            
            # Process files
            output_file = await concatenator.concatenate_files()
            
            # Return results
            return {
                "output_file": output_file,
                "statistics": concatenator.stats,
                "details": {
                    "repository_url": repo_url,
                    "owner": owner,
                    "repo": repo,
                    "subdirectory": subdir,
                    "base_directory": str(base_dir),
                    "file_pattern": file_pattern
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing repository {repo_url}: {str(e)}")
            if isinstance(e, (InvalidRepositoryError, RepositoryNotFoundError,
                            AuthenticationError, RateLimitError)):
                raise
            raise Exception(f"Failed to process repository: {str(e)}")
    
    def __del__(self):
        """Cleanup resources when the service is destroyed."""
        if hasattr(self, 'github_handler'):
            self.github_handler.cleanup() 