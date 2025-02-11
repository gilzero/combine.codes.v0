import pytest
import aiohttp
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
from app.core.github_handler import GitHubHandler
from app.models.schemas import (
    GitHubConfig,
    GitHubRepoInfo,
    AuthenticationError,
    RateLimitError,
    RepositoryNotFoundError
)
import logging

@pytest.fixture
def github_handler():
    """Create a GitHubHandler instance for testing."""
    handler = GitHubHandler()
    return handler

@pytest.mark.asyncio
async def test_validate_token():
    """Test token validation logic."""
    handler = GitHubHandler()
    
    # Test empty token
    assert handler._validate_token(None) is None
    assert handler._validate_token("") is None
    assert handler._validate_token("   ") is None
    
    # Test invalid token (too short)
    assert handler._validate_token("short_token") is None
    
    # Test valid token format
    valid_token = "ghp_" + "a" * 36  # Simulate a valid token format
    assert handler._validate_token(valid_token) == valid_token

@pytest.mark.asyncio
async def test_github_api_access_public_repo():
    """Test accessing a public repository."""
    handler = GitHubHandler()
    
    # Mock successful public repo response
    mock_data = {
        "size": 1000,
        "private": False,
        "name": "test-repo"
    }
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_data)
        mock_response.text = AsyncMock(return_value=str(mock_data))
        mock_response.headers = {
            'X-RateLimit-Limit': '60',
            'X-RateLimit-Remaining': '59'
        }
        mock_get.return_value.__aenter__.return_value = mock_response
        
        repo_info = await handler.pre_check_repository("https://github.com/test-owner/test-repo")
        assert repo_info.repo_name == "test-repo"
        assert repo_info.size == 1000

@pytest.mark.asyncio
async def test_github_api_access_rate_limit():
    """Test handling of rate limit errors."""
    handler = GitHubHandler()
    
    # Mock rate limit response
    mock_response = {
        "message": "API rate limit exceeded"
    }
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.json.return_value = {"message": "API rate limit exceeded"}
        mock_response.text.return_value = '{"message": "API rate limit exceeded"}'
        mock_response.headers = {
            'X-RateLimit-Limit': '60',
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': '1612345678'
        }
        mock_get.return_value.__aenter__.return_value = mock_response
        
        with pytest.raises(RateLimitError):
            await handler.pre_check_repository("https://github.com/test-owner/test-repo")

@pytest.mark.asyncio
async def test_github_api_access_private_repo():
    """Test accessing a private repository with and without token."""
    handler = GitHubHandler()
    
    with patch('aiohttp.ClientSession.get') as mock_get:
        # First request (public access) fails
        mock_response_unauthorized = AsyncMock()
        mock_response_unauthorized.status = 404
        mock_response_unauthorized.json.return_value = {"message": "Not Found"}
        mock_response_unauthorized.text.return_value = '{"message": "Not Found"}'
        mock_response_unauthorized.headers = {
            'X-RateLimit-Limit': '60',
            'X-RateLimit-Remaining': '59'
        }
        mock_get.return_value.__aenter__.return_value = mock_response_unauthorized
        
        with pytest.raises(RepositoryNotFoundError):
            await handler.pre_check_repository("https://github.com/test-owner/private-repo")
        
        # Reset mock for second test with token
        mock_response_authorized = AsyncMock()
        mock_response_authorized.status = 200
        mock_response_authorized.json.return_value = {
            "size": 1000,
            "private": True,
            "name": "private-repo"
        }
        mock_response_authorized.text.return_value = '{"size": 1000, "private": true, "name": "private-repo"}'
        mock_response_authorized.headers = {
            'X-RateLimit-Limit': '5000',
            'X-RateLimit-Remaining': '4999'
        }
        mock_get.return_value.__aenter__.return_value = mock_response_authorized
        
        repo_info = await handler.pre_check_repository(
            "https://github.com/test-owner/private-repo",
            github_token="ghp_" + "a" * 36
        )
        assert repo_info.repo_name == "private-repo"
        assert repo_info.size == 1000

@pytest.mark.asyncio
async def test_invalid_token_format():
    """Test handling of invalid token formats."""
    handler = GitHubHandler()
    
    # Test various invalid token formats
    invalid_tokens = [
        "invalid",
        "gh_12345",
        "token_",
        "ghp_" + "a" * 10  # Too short
    ]
    
    for token in invalid_tokens:
        assert handler._validate_token(token) is None

@pytest.mark.asyncio
async def test_github_api_headers():
    """Test that correct headers are sent with requests."""
    handler = GitHubHandler()
    
    headers = handler._get_base_headers()
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert "User-Agent" in headers
    
    # Test headers with token
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {}
        mock_response.text.return_value = "{}"
        mock_response.headers = {
            'X-RateLimit-Limit': '5000',
            'X-RateLimit-Remaining': '4999'
        }
        mock_get.return_value.__aenter__.return_value = mock_response
        
        await handler._make_github_request(
            "https://api.github.com/repos/test/test",
            headers,
            "test_token"
        )
        
        # Verify Authorization header was added
        called_headers = mock_get.call_args[1]["headers"]
        assert called_headers["Authorization"] == "token test_token"

@pytest.mark.asyncio
async def test_session_management():
    """Test proper session management."""
    handler = GitHubHandler()
    
    # Test session creation
    session1 = await handler.session
    assert session1 is not None
    assert not session1.closed
    
    # Test session reuse
    session2 = await handler.session
    assert session2 is session1
    
    # Test session cleanup
    await handler.close()
    assert session1.closed

@pytest.mark.asyncio
async def test_env_github_token(caplog):
    """Test the GitHub token from environment variables."""
    caplog.set_level(logging.INFO)
    
    env_token = os.getenv("GITHUB_TOKEN")
    logging.info(f"\nChecking environment token:")
    logging.info(f"Token from env: {env_token}")
    
    if not env_token:
        logging.warning("GITHUB_TOKEN environment variable not set")
        # Try to load from .env file directly
        try:
            from dotenv import load_dotenv
            load_dotenv()
            env_token = os.getenv("GITHUB_TOKEN")
            logging.info(f"Token after loading .env: {env_token}")
        except ImportError:
            logging.error("python-dotenv not installed")
        pytest.skip("GITHUB_TOKEN environment variable not set")
    
    handler = GitHubHandler(github_token=env_token)
    logging.info(f"Handler token: {handler.config.github_token}")
    
    # Test 1: Verify token format
    validated_token = handler._validate_token(env_token)
    logging.info(f"Validated token: {validated_token}")
    assert validated_token is not None, "Environment token failed format validation"
    assert len(validated_token) >= 30, "Token is too short"
    assert validated_token.startswith(("ghp_", "github_pat_")), "Token should start with 'ghp_' or 'github_pat_'"
    
    # Test 2: Verify token works with GitHub API
    headers = handler._get_base_headers()
    api_url = "https://api.github.com/user"  # Simple endpoint to verify token
    
    async with aiohttp.ClientSession() as session:
        headers["Authorization"] = f"token {validated_token}"
        logging.info(f"\nMaking API request with headers: {headers}")
        async with session.get(api_url, headers=headers) as response:
            logging.info(f"API Response status: {response.status}")
            response_text = await response.text()
            logging.info(f"API Response: {response_text}")
            assert response.status != 401, "Token authentication failed"
            if response.status == 200:
                data = await response.json()
                logging.info(f"\nToken belongs to GitHub user: {data.get('login')}")
            elif response.status == 403:
                rate_limit_url = "https://api.github.com/rate_limit"
                async with session.get(rate_limit_url, headers=headers) as rate_response:
                    rate_data = await rate_response.json()
                    logging.info(f"\nRate limit info: {rate_data.get('rate', {})}")

@pytest.mark.asyncio
async def test_github_token_from_config():
    """Test that token is properly loaded from GitHubConfig."""
    test_token = "ghp_" + "a" * 36
    
    # Test token via constructor
    handler1 = GitHubHandler(github_token=test_token)
    assert handler1.config.github_token == test_token
    
    # Test token via environment
    with patch.dict(os.environ, {'GITHUB_TOKEN': test_token}):
        handler2 = GitHubHandler()
        assert handler2.config.github_token == test_token
        
    # Test token precedence (constructor over environment)
    override_token = "ghp_" + "b" * 36
    with patch.dict(os.environ, {'GITHUB_TOKEN': test_token}):
        handler3 = GitHubHandler(github_token=override_token)
        assert handler3.config.github_token == override_token

if __name__ == "__main__":
    pytest.main(["-v", "test_github_handler.py"]) 