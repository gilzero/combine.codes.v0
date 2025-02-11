"""
Configuration for system-wide ignore patterns.
These patterns are used across different parts of the application.
"""

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

def get_system_ignores() -> list:
    """Get the list of system-wide ignore patterns."""
    return SYSTEM_IGNORES.copy()

def combine_ignore_patterns(repo_ignores: list = None) -> list:
    """
    Combine system ignores and repository ignores while removing duplicates.
    
    Args:
        repo_ignores (list, optional): List of repository-specific ignore patterns
        
    Returns:
        list: Combined and deduplicated list of ignore patterns
    """
    # Start with system ignores
    all_ignores = set(SYSTEM_IGNORES)
    
    # Add repository ignores if provided
    if repo_ignores:
        # Normalize patterns (remove empty lines and comments)
        normalized_patterns = {
            pattern.strip() for pattern in repo_ignores 
            if pattern.strip() and not pattern.strip().startswith('#')
        }
        all_ignores.update(normalized_patterns)
    
    # Convert back to sorted list for consistent ordering
    return sorted(all_ignores)

def should_ignore_file(file_path: str, repo_ignores: list = None) -> bool:
    """
    Check if a file should be ignored based on combined patterns.
    
    Args:
        file_path (str): Path to check
        repo_ignores (list, optional): Repository-specific ignore patterns
        
    Returns:
        bool: True if file should be ignored, False otherwise
    """
    from pathspec import PathSpec
    from pathspec.patterns import GitWildMatchPattern
    
    all_ignores = combine_ignore_patterns(repo_ignores)
    spec = PathSpec.from_lines(GitWildMatchPattern, all_ignores)
    return spec.match_file(file_path) 