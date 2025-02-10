"""
Services package for the File Concatenator application.
Contains service classes that implement business logic and coordinate between different components.
"""

from .github_service import GitHubService

__all__ = ['GitHubService'] 