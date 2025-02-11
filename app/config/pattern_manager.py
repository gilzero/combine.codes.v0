"""
@fileoverview
This module provides centralized management of ignore patterns for the application.
It combines system-wide, repository-specific, and user-provided patterns into a single
set of patterns for consistent application across different components.
"""

import pathlib
from typing import List, Union
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
import logging

logger = logging.getLogger(__name__)

# System-wide ignore patterns (same as before)
SYSTEM_IGNORES = [
    ".git/", ".svn/", ".hg/", "node_modules/", "venv/", "__pycache__/",
    "*.pyc", "*.pyo", "*.pyd", "build/", "dist/", "*.egg-info/",
    ".idea/", ".vscode/", "*.swp", "*.swo", ".DS_Store",
    "coverage/", ".coverage", ".pytest_cache/", ".tox/",
    "*.zip", "*.tar.gz", "*.rar", "*.mp4", "*.mp3", "*.avi", "*.mov", "*.iso"
]

def get_system_ignores() -> List[str]:
    """Get the list of system-wide ignore patterns."""
    return SYSTEM_IGNORES.copy()

class PatternManager:
    """
    Manages ignore patterns.
    """
    def __init__(self, repo_ignores: List[str] = None, user_ignores: List[str] = None):
        """
        Initialize the PatternManager.
        """
        self.system_ignores = get_system_ignores()
        self.repo_ignores = self._normalize_patterns(repo_ignores)
        self.user_ignores = self._normalize_patterns(user_ignores)

        self.all_ignores = self._combine_patterns()
        self.spec = PathSpec.from_lines(GitWildMatchPattern, self.all_ignores)

    def _normalize_patterns(self, patterns: List[str]) -> List[str]:
        """Normalize patterns."""
        if not patterns:
            return []
        return [
            p.strip() for p in patterns
            if p.strip() and not p.strip().startswith("#")
        ]

    def _combine_patterns(self) -> List[str]:
        """Combine system, repository, and user patterns."""
        combined = set(self.system_ignores)
        combined.update(self.repo_ignores)
        combined.update(self.user_ignores)
        return sorted(combined)

    def should_ignore(self, file_path: Union[str, pathlib.Path]) -> bool:
        """Check if a file should be ignored."""
        return self.spec.match_file(str(file_path))

    @classmethod
    def from_repo_path(cls, repo_path: Union[str, pathlib.Path], user_ignores: List[str] = None) -> "PatternManager":
        """
        Create a PatternManager from a repo path, reading .gitignore.
        """
        repo_path = pathlib.Path(repo_path)
        gitignore_path = repo_path / ".gitignore"
        repo_ignores = []

        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r") as f:
                    repo_ignores = [line.strip() for line in f]
            except OSError:
                pass

        # *** CORRECTLY INITIALIZE WITH ALL IGNORE TYPES ***
        return cls(repo_ignores=repo_ignores, user_ignores=user_ignores) # THIS LINE IS CRUCIAL


    def _recalculate_patterns(self):
        """Recalculate all_ignores and update the PathSpec."""
        self.all_ignores = self._combine_patterns()
        self.spec = PathSpec.from_lines(GitWildMatchPattern, self.all_ignores)

    def add_user_ignores(self, user_ignores: List[str]):
        """Adds user ignores and updates the combined patterns."""
        self.user_ignores.extend(self._normalize_patterns(user_ignores))
        self._recalculate_patterns()