# File Concatenator (v4)

A powerful tool that concatenates files from GitHub repositories while respecting `.gitignore` rules and providing comprehensive statistics.

## Features

- **GitHub Repository Support**: Load files directly from any GitHub repository using HTTPS URLs
- **Private Repository Support**: Access private repositories using GitHub tokens
- **Smart File Filtering**: Respects `.gitignore` rules from the repository
- **Additional Ignore Patterns**: Add custom patterns to exclude files
- **Comprehensive Statistics**: Get detailed information about processed files
- **Modern UI**: Clean and responsive interface with dark mode support
- **Export Options**: Save results as PDF or PNG
- **Directory Tree Visualization**: Visual representation of repository structure
- **Detailed Analytics**: Code analysis, filter statistics, and directory information
- **Accessibility Features**: Screen reader support and keyboard navigation
- **Responsive Design**: Works on desktop and mobile devices
- **Theme Support**: Light and dark mode with system preference detection

## What's New in v4

### UI Enhancements
- Added beautiful directory tree visualization
- Implemented dark/light theme toggle with system preference detection
- Added export functionality for statistics (PDF and PNG)
- Improved accessibility with ARIA labels and keyboard navigation
- Added responsive design for mobile devices

### Statistics Improvements
- Added detailed code analysis (code lines, comments, empty lines)
- Enhanced directory statistics with depth and file distribution
- Added filter effectiveness tracking
- Improved file type categorization

### Technical Improvements
- Updated to latest FastAPI version
- Enhanced error handling and user feedback
- Improved GitHub repository handling
- Added support for larger repositories
- Optimized file processing performance

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/file-concatenator.git
   cd file-concatenator
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Start the server:
   ```bash
   python main.py

   or (python -m uvicorn main:app --reload)
   ```

2. Open your browser and navigate to `http://localhost:8000`

3. Enter a GitHub repository URL:
   - For public repositories: Just paste the HTTPS URL (e.g., `https://github.com/username/repository`)
   - For private repositories: Add your GitHub token

4. (Optional) Add additional ignore patterns:
   - One pattern per line
   - Uses the same format as `.gitignore`
   - Examples:
     ```
     *.log
     temp/*
     *.bak
     ```

5. Click "Process Repository" and wait for the results

## API Reference

### POST /concatenate

Concatenates files from a GitHub repository.

**Request Body:**
```json
{
    "repo_url": "https://github.com/username/repository",
    "github_token": "your_github_token",  // Optional
    "additional_ignores": [  // Optional
        "*.log",
        "temp/*"
    ]
}
```

**Response:**
```json
{
    "status": "success",
    "message": "Files concatenated successfully",
    "output_file": "output_filename.txt",
    "statistics": {
        "file_stats": {
            "total_files": 100,
            "processed_files": 80,
            "skipped_files": 20,
            "file_types": {
                ".py": 50,
                ".js": 30
            }
        }
    }
}
```

### GET /download/{file_path}

Downloads a concatenated file.

## Development

### Project Structure

```
file-concatenator/
├── app/
│   ├── api/
│   │   └── routes.py          # API endpoints
│   │   └── concatenator.py    # Core concatenation logic
│   │   └── github_handler.py  # GitHub repository handling
│   └── models/
│       └── schemas.py         # Pydantic models
├── templates/
│   └── index.html            # Frontend template
├── output/                   # Concatenated files
├── main.py                   # Application entry point
└── requirements.txt          # Python dependencies
```

### Adding New Features

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests
5. Submit a pull request

## Requirements

- Python 3.11 or later
- Git
- FastAPI
- GitPython
- Modern web browser with JavaScript enabled

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

This project is developed by [@gilzero](https://github.com/gilzero).

Weiming.ai [weiming.ai] (https://weiming.ai)

## Roadmap

- [x] Add support for more file sub directories
- [ ] Better error handling UI
- [ ] Add support for payment processing
