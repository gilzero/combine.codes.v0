import pytest
import os
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from app.core.github_handler import GitHubHandler
from app.config.ignore_patterns import get_system_ignores
from app.models.schemas import RepositoryPreCheckResponse

client = TestClient(app)

def get_repo_ignores(repo_path: Path) -> list:
    """Read repository's .gitignore patterns if they exist."""
    gitignore_path = repo_path / ".gitignore"
    patterns = []
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return patterns

def test_pre_check_repository_details():
    """Test that pre-check returns valid repository size and file count while respecting combined ignore patterns."""
    # Mock repository URL
    repo_url = "https://github.com/gilzero/EditorDocAIAgentV1"
    print(f"\nTesting repository: {repo_url}")
    
    # Create handler instance
    handler = GitHubHandler()
    
    # Test the pre-check directly
    repo_info = handler.validate_github_url(repo_url)
    print("\nRepository Info from validate_github_url:")
    print(f"Owner: {repo_info.owner}")
    print(f"Repository Name: {repo_info.repo_name}")
    print(f"Base URL: {repo_info.base_url}")
    print(f"Clone URL: {repo_info.clone_url}")
    print(f"Subdirectory: {repo_info.subdir or 'None'}")
    
    assert repo_info is not None
    assert repo_info.owner == "gilzero"
    assert repo_info.repo_name == "EditorDocAIAgentV1"
    assert repo_info.subdir is None
    
    # Test the API endpoint
    response = client.post(
        "/pre-check",
        json={
            "repo_url": repo_url,
            "github_token": None,
            "base_url": "http://localhost:8000/"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Print full API response for debugging
    print("\nFull API Response:")
    for key, value in data.items():
        print(f"{key}: {value}")
    
    # Verify repository details
    assert data["repo_name"] == "EditorDocAIAgentV1"
    assert data["owner"] == "gilzero"
    assert data["repository_size_kb"] is not None
    assert data["repository_size_kb"] > 0
    assert data["estimated_file_count"] is not None
    assert data["estimated_file_count"] > 0
    assert data["price_usd"] == 0.50
    
    # Print actual values for debugging
    print(f"\nRepository Details from API:")
    print(f"Size (KB): {data['repository_size_kb']}")
    print(f"File Count: {data['estimated_file_count']}")

    # Print system ignores being used
    print("\nSystem Ignores Applied:")
    for pattern in get_system_ignores():
        print(f"- {pattern}")

def print_file_structure(temp_dir: Path, indent: str = ""):
    """Print the file structure of a directory."""
    try:
        # Get all entries and sort them (directories first, then files)
        entries = sorted(temp_dir.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        
        for entry in entries:
            if entry.name.startswith('.git'):  # Skip .git directory
                continue
                
            is_last = entry == entries[-1]
            prefix = indent + ("└── " if is_last else "├── ")
            print(f"{prefix}{entry.name}")
            
            if entry.is_dir():
                next_indent = indent + ("    " if is_last else "│   ")
                print_file_structure(entry, next_indent)
    except Exception as e:
        print(f"Error reading directory {temp_dir}: {e}")

def print_file_type_stats(temp_dir: Path):
    """Print statistics about file types in the directory."""
    file_types = {}
    
    for file_path in temp_dir.rglob("*"):
        if file_path.is_file() and not str(file_path).startswith(str(temp_dir / '.git')):
            ext = file_path.suffix.lower() or 'no extension'
            if ext.startswith('.'):
                ext = ext[1:]  # Remove the leading dot
            file_types[ext] = file_types.get(ext, 0) + 1
    
    if file_types:
        print("\nFile type statistics:")
        # Sort by count (descending) and then by extension name
        for ext, count in sorted(file_types.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {ext}: {count} files")
    else:
        print("\nNo files found in the directory.")

@pytest.mark.asyncio
async def test_github_handler_pre_check():
    """Test the GitHub handler's pre-check method with combined ignore patterns."""
    handler = GitHubHandler()
    repo_url = "https://github.com/gilzero/EditorDocAIAgentV1"
    print(f"\nTesting pre-check for repository: {repo_url}")
    
    # Create temporary directory for clone
    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="repo_precheck_test_"))
    try:
        # Do a quick clone to get .gitignore
        import git
        git.Repo.clone_from(repo_url, temp_dir, depth=1)
        
        print("\nRepository file structure:")
        print_file_structure(temp_dir)
        print_file_type_stats(temp_dir)
        
        # Get and print repository's ignore patterns
        repo_ignores = get_repo_ignores(temp_dir)
        print("\nRepository's ignore patterns:")
        if repo_ignores:
            for pattern in repo_ignores:
                print(f"- {pattern}")
        else:
            print("No .gitignore file found in repository")
            
        # Get combined ignore patterns
        from app.config.ignore_patterns import combine_ignore_patterns
        all_ignores = combine_ignore_patterns(repo_ignores)
        print("\nCombined ignore patterns:")
        for pattern in all_ignores:
            print(f"- {pattern}")
            
    except Exception as e:
        print(f"Error reading repository's ignore patterns: {e}")
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_dir)
    
    # Perform pre-check
    repo_info = await handler.pre_check_repository(repo_url)
    
    # Print detailed repository information
    print("\nDetailed Repository Information:")
    print(f"Owner: {repo_info.owner}")
    print(f"Repository Name: {repo_info.repo_name}")
    print(f"Base URL: {repo_info.base_url}")
    print(f"Clone URL: {repo_info.clone_url}")
    print(f"Size (KB): {repo_info.size_kb}")
    print(f"Estimated Files: {repo_info.file_count}")
    print(f"Subdirectory: {repo_info.subdir or 'None'}")
    
    # Verify repository info
    assert repo_info is not None
    assert repo_info.size_kb is not None
    assert repo_info.size_kb > 0
    assert repo_info.file_count is not None
    assert repo_info.file_count > 0
    assert repo_info.subdir is None

    # More precise assertions based on known repository state
    assert 20 <= repo_info.file_count <= 30, f"File count {repo_info.file_count} outside expected range"
    assert 200 <= repo_info.size_kb <= 300, f"Size {repo_info.size_kb}KB outside expected range"

@pytest.mark.asyncio
async def test_github_handler_pre_check_with_subdir():
    """Test the GitHub handler's pre-check method with subdirectory and combined ignore patterns."""
    handler = GitHubHandler()
    repo_url = "https://github.com/gilzero/EditorDocAIAgentV1/tree/main/documentation"
    print(f"\nTesting pre-check for repository with subdirectory: {repo_url}")

    # First validate the URL parsing
    repo_info = handler.validate_github_url(repo_url)
    print("\nParsed Repository Info:")
    print(f"Owner: {repo_info.owner}")
    print(f"Repository Name: {repo_info.repo_name}")
    print(f"Base URL: {repo_info.base_url}")
    print(f"Clone URL: {repo_info.clone_url}")
    print(f"Subdirectory: {repo_info.subdir}")

    # Verify URL parsing
    assert repo_info.owner == "gilzero"
    assert repo_info.repo_name == "EditorDocAIAgentV1"
    assert repo_info.subdir == "documentation"

    # Create temporary directory for clone
    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="repo_precheck_test_"))
    try:
        # Do a quick clone to get .gitignore
        import git
        git.Repo.clone_from(repo_info.clone_url, temp_dir, depth=1, branch="main")  # Explicitly checkout main branch

        # Print file structure for both the full repository and the subdirectory
        print("\nFull repository file structure:")
        print_file_structure(temp_dir)
        print_file_type_stats(temp_dir)

        # Print file structure for the subdirectory
        subdir_path = temp_dir / repo_info.subdir
        if subdir_path.exists():
            print(f"\nSubdirectory '{repo_info.subdir}' file structure:")
            print_file_structure(subdir_path)
            print_file_type_stats(subdir_path)
        else:
            print(f"\nWarning: Subdirectory '{repo_info.subdir}' not found")

        # Get and print repository's ignore patterns
        repo_ignores = get_repo_ignores(temp_dir)
        print("\nRepository's ignore patterns:")
        if repo_ignores:
            for pattern in repo_ignores:
                print(f"- {pattern}")
        else:
            print("No .gitignore file found in repository")

        # Get combined ignore patterns
        from app.config.ignore_patterns import combine_ignore_patterns
        all_ignores = combine_ignore_patterns(repo_ignores)
        print("\nCombined ignore patterns:")
        for pattern in all_ignores:
            print(f"- {pattern}")

    except Exception as e:
        print(f"Error reading repository's ignore patterns: {e}")
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_dir)

    # Perform pre-check
    repo_info = await handler.pre_check_repository(repo_url)

    # Print detailed repository information
    print("\nDetailed Repository Information:")
    print(f"Owner: {repo_info.owner}")
    print(f"Repository Name: {repo_info.repo_name}")
    print(f"Base URL: {repo_info.base_url}")
    print(f"Clone URL: {repo_info.clone_url}")
    print(f"Size (KB): {repo_info.size_kb}")
    print(f"Estimated Files: {repo_info.file_count}")
    print(f"Subdirectory: {repo_info.subdir}")

    # Verify repository info
    assert repo_info is not None
    assert repo_info.size_kb is not None
    assert repo_info.size_kb > 0
    assert repo_info.file_count is not None
    assert repo_info.file_count > 0
    assert repo_info.subdir == "documentation", "Subdirectory path should be preserved"

    # More precise assertions for subdirectory
    assert repo_info.file_count == 4, f"File count {repo_info.file_count} should be exactly 4 for /documentation subdirectory"
    assert 140 <= repo_info.size_kb <= 160, f"Size {repo_info.size_kb}KB outside expected range for /documentation subdirectory"

if __name__ == "__main__":
    pytest.main(["-v", "test_pre_check.py"]) 