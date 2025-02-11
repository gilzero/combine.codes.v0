"""
@fileoverview
This module provides centralized management of ignore patterns for the application.
It combines system-wide, repository-specific, and user-provided patterns into a single
set of patterns for consistent application across different components.
"""

from typing import List
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

# System-wide ignore patterns
SYSTEM_IGNORES = [
    # Version control
    ".git/",
    ".svn/",
    ".hg/",
    
    # Dependencies and build artifacts
    "node_modules/",
    "venv/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "build/",
    "dist/",
    "*.egg-info/",
    
    # IDE and editor files
    ".idea/",
    ".vscode/",
    "*.swp",
    "*.swo",
    ".DS_Store",
    
    # Common build and test directories
    "coverage/",
    ".coverage",
    ".pytest_cache/",
    ".tox/",
    
    # Large binary and media files
    "*.zip",
    "*.tar.gz",
    "*.rar",
    "*.mp4",
    "*.mp3",
    "*.avi",
    "*.mov",
    "*.iso"
]

def get_system_ignores() -> List[str]:
    """Get the list of system-wide ignore patterns."""
    return SYSTEM_IGNORES.copy()

class PatternManager:
    """
    Manages ignore patterns by combining system-wide, repository-specific, and user-provided patterns.

    Example:
        repo_ignores = ["*.log", "# Comment", " "]
        user_ignores = ["*.tmp", "*.bak"]
        pattern_manager = PatternManager(repo_ignores=repo_ignores, user_ignores=user_ignores)
        should_ignore = pattern_manager.should_ignore("example.log")
    """
    def __init__(self, repo_ignores: List[str] = None, user_ignores: List[str] = None):
        """
        Initialize the PatternManager with repository-specific and user-provided patterns.
        
        Args:
            repo_ignores (List[str], optional): Repository-specific ignore patterns.
            user_ignores (List[str], optional): User-provided additional ignore patterns.
        """
        self.system_ignores = get_system_ignores()
        self.repo_ignores = self._normalize_patterns(repo_ignores or [])
        self.user_ignores = self._normalize_patterns(user_ignores or [])
        
        # Combine all patterns
        self.all_ignores = self._combine_patterns()
        
        # Create a PathSpec for matching
        self.spec = PathSpec.from_lines(GitWildMatchPattern, self.all_ignores)

    def _normalize_patterns(self, patterns: List[str]) -> List[str]:
        """
        Normalize patterns by removing comments and empty lines.
        
        Args:
            patterns (List[str]): List of patterns to normalize.
            
        Returns:
            List[str]: Normalized list of patterns.
        """
        return [pattern.strip() for pattern in patterns if pattern.strip() and not pattern.strip().startswith('#')]

    def _combine_patterns(self) -> List[str]:
        """
        Combine system, repository, and user patterns into a single list.
        
        Returns:
            List[str]: Combined and deduplicated list of ignore patterns.
        """
        combined = set(self.system_ignores)
        combined.update(self.repo_ignores)
        combined.update(self.user_ignores)
        return sorted(combined)

    def should_ignore(self, file_path: str) -> bool:
        """
        Check if a file should be ignored based on combined patterns.
        
        Args:
            file_path (str): Path to check.
            
        Returns:
            bool: True if file should be ignored, False otherwise.
        """
        return self.spec.match_file(file_path) 