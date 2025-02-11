"""
Pydantic models for the File Concatenator application.
"""

from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Optional, Union, Any, Type
import pathlib
from datetime import datetime, timedelta
from enum import Enum

class ConcatenateRequest(BaseModel):
    """Request model for file concatenation."""
    repo_url: HttpUrl
    github_token: Optional[str] = None
    additional_ignores: Optional[List[str]] = []
    checkout_session_id: str

class ConcatenateResponse(BaseModel):
    """Response model for file concatenation."""
    status: str
    message: str
    output_file: str
    statistics: dict

class FileStats(BaseModel):
    """Model for file statistics."""
    total_files: int = 0
    processed_files: int = 0
    skipped_files: int = 0
    file_types: Dict[str, int] = {}
    largest_file: Dict[str, Union[str, int, None]] = {"path": None, "size": 0}
    total_size: int = 0
    total_lines: int = 0
    empty_lines: int = 0
    comment_lines: int = 0

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            pathlib.Path: str
        }
        allow_population_by_field_name = True

    @property
    def avg_lines_per_file(self) -> float:
        """Calculate average lines per file."""
        if not self.processed_files or not self.total_lines:
            return 0.0
        return round(self.total_lines / self.processed_files, 2)

    def dict(self, *args, **kwargs):
        """Custom dict method to include computed properties."""
        d = super().dict(*args, **kwargs)
        d['avg_lines_per_file'] = self.avg_lines_per_file
        # Include file_types under both names for compatibility
        d['by_type'] = self.file_types
        return d

    class Config:
        """Additional configuration for JSON serialization."""
        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type['FileStats']) -> None:
            """Add computed properties to the schema."""
            schema['properties']['by_type'] = {
                'title': 'By Type',
                'description': 'File statistics grouped by file type',
                'type': 'object',
                'additionalProperties': {'type': 'integer'}
            }

class TreeNode(BaseModel):
    """Model for directory tree visualization."""
    name: str
    path: str
    type: str  # 'file' or 'directory'
    size: Optional[int] = None
    children: List['TreeNode'] = []
    metadata: Dict[str, Any] = {}

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            pathlib.Path: str
        }

class DirectoryStats(BaseModel):
    """Model for directory statistics."""
    total_dirs: int = 0
    max_depth: int = 0
    dirs_with_most_files: Dict[str, Union[str, int, None]] = {"path": None, "count": 0}
    empty_dirs: int = 0
    tree: Optional[TreeNode] = None  # Add tree to DirectoryStats

class FilterStats(BaseModel):
    """Model for filter statistics."""
    gitignore_filtered: int = 0
    custom_filtered: int = 0
    pattern_matches: Dict[str, int] = {}

    @property
    def most_effective_patterns(self) -> List[Dict[str, Union[str, int]]]:
        """Get the most effective patterns sorted by number of files filtered."""
        return [
            {"pattern": pattern, "files_filtered": count}
            for pattern, count in sorted(
                self.pattern_matches.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]  # Return top 5 most effective patterns
        ]

    def dict(self, *args, **kwargs):
        """Custom dict method to include computed properties."""
        d = super().dict(*args, **kwargs)
        d['most_effective_patterns'] = self.most_effective_patterns
        return d

class ConcatenationStats(BaseModel):
    """Model for overall concatenation statistics."""
    file_stats: FileStats = FileStats()
    dir_stats: DirectoryStats = DirectoryStats()
    filter_stats: FilterStats = FilterStats()

class GitHubConfig(BaseModel):
    """Configuration model for GitHub handler."""
    cache_dir: Optional[str] = None
    github_token: Optional[str] = None
    cache_ttl: int = 3600  # Default 1 hour
    max_workers: int = 4

    @property
    def cache_ttl_delta(self) -> timedelta:
        """Convert cache_ttl to timedelta."""
        return timedelta(hours=self.cache_ttl if self.cache_ttl is not None else 1)

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            pathlib.Path: str,
            timedelta: lambda v: v.total_seconds() // 3600
        }

class GitHubRepoInfo(BaseModel):
    """Model for GitHub repository information."""
    owner: str
    repo_name: str
    subdir: Optional[str] = None
    base_url: str
    clone_url: str
    
    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            pathlib.Path: str
        }

class CacheInfo(BaseModel):
    """Model for cache information."""
    cache_path: pathlib.Path
    is_valid: bool
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            pathlib.Path: str,
            datetime: lambda v: v.isoformat() if v else None
        }

class CloneResult(BaseModel):
    """Model for clone operation result."""
    repo_path: pathlib.Path
    subdir: Optional[str] = None
    from_cache: bool = False
    cache_info: Optional[CacheInfo] = None
    
    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            pathlib.Path: str
        }

# Base exception class for application
class FileConcatenatorError(Exception):
    """Base exception class for all application errors."""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to a dictionary format suitable for API responses."""
        return {
            "status": "error",
            "message": self.message,
            "error_type": self.__class__.__name__,
            "status_code": self.status_code,
            "details": self.details
        }

class GitHubError(FileConcatenatorError):
    """Exception raised for GitHub-related errors."""
    def __init__(self, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code, details)

class RepositoryNotFoundError(GitHubError):
    """Exception raised when a repository is not found."""
    def __init__(self, repo_url: str):
        details = {"repository_url": repo_url}
        message = f"Repository not found: {repo_url}"
        super().__init__(message, status_code=404, details=details)

class InvalidRepositoryError(GitHubError):
    """Exception raised when a repository URL is invalid."""
    def __init__(self, repo_url: str, reason: str, suggestion: Optional[str] = None):
        details = {
            "repository_url": repo_url,
            "reason": reason
        }
        if suggestion:
            details["suggestion"] = suggestion
        super().__init__(
            f"Invalid repository URL '{repo_url}': {reason}",
            status_code=400,
            details=details
        )

class AuthenticationError(GitHubError):
    """Exception raised for GitHub authentication errors."""
    def __init__(self, message: str = "GitHub authentication failed"):
        details = {
            "help": "Please provide a valid GitHub token for private repositories"
        }
        super().__init__(message, status_code=401, details=details)

class FileSystemError(FileConcatenatorError):
    """Exception raised for filesystem-related errors."""
    def __init__(self, message: str, path: Optional[str] = None, suggestion: Optional[str] = None):
        details = {}
        if path:
            details["path"] = path
        if suggestion:
            details["suggestion"] = suggestion
        super().__init__(
            f"Filesystem error: {message}",
            status_code=500,
            details=details
        )

class CacheError(FileConcatenatorError):
    """Exception raised for cache-related errors."""
    def __init__(self, message: str, cache_path: Optional[str] = None, can_retry: bool = True):
        details = {
            "can_retry": can_retry
        }
        if cache_path:
            details["cache_path"] = cache_path
        super().__init__(
            f"Cache error: {message}",
            status_code=500,
            details=details
        )

class RepositoryPreCheckRequest(BaseModel):
    """Request model for repository pre-check."""
    repo_url: HttpUrl
    github_token: Optional[str] = None
    base_url: HttpUrl  # URL of the application for Stripe success/cancel redirects

class RepositoryPreCheckResponse(BaseModel):
    """Response model for repository pre-check."""
    repo_name: str
    owner: str
    price_usd: float = 0.50
    checkout_session_id: str
    status: str = "ready"
    message: Optional[str] = None

class PaymentVerificationRequest(BaseModel):
    """Request model for payment verification."""
    checkout_session_id: str

class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"

class PaymentVerificationResponse(BaseModel):
    """Response model for payment verification."""
    status: PaymentStatus
    message: str
    can_proceed: bool = False 