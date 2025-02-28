# Combine Codes Service v1 (combinecodesv1) Alpha

A web service that allows users to concatenate and analyze files from GitHub repositories.

## Features

- GitHub repository integration with support for both public and private repositories
- Secure payment processing with Stripe
- Comprehensive file analysis and statistics
- Beautiful, responsive UI with dark/light mode support
- Real-time processing status updates
- Export results in multiple formats (PNG, PDF)
- Detailed directory structure visualization
- Support for custom ignore patterns
- Caching system for improved performance

## Setup

1. Clone the repository:
```bash
git clone https://github.com/gilzero/combinecodesv1
cd combinecodesv1
```

2. Create and activate a virtual environment:
```bash
(use python 3.11 : python3.11 -m venv venv)
python -m venv venv 
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with the following configuration:
```env
# GitHub Configuration
GITHUB_TOKEN=your_github_token  # Optional, for private repos

# Stripe Configuration
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key
STRIPE_PAYMENT_METHOD_CONFIG=

# Cache Configuration (optional)
CACHE_DIR=path/to/cache
CACHE_TTL_HOURS=1

# App Configuration
DEBUG=True
ENVIRONMENT=development 
```

5. Run the application:
```bash
python main.py
```

The application will be available at `http://localhost:8000`

## Usage

1. Visit the homepage and enter a GitHub repository URL
2. Optionally provide a GitHub token for private repositories
3. Review repository information and pricing
4. Complete the payment process
5. Wait for the concatenation process to complete
6. Download the combined files and view statistics

## Features

### File Processing
- Concatenates all text files in the repository
- Maintains original file structure information
- Handles various file encodings
- Skips binary files automatically

### Statistics
- Total files processed
- File size distribution
- Lines of code analysis
- Directory structure visualization
- File type breakdown
- Most effective ignore patterns

### Security
- Secure payment processing
- Safe handling of GitHub tokens
- Repository access validation
- Rate limit handling

### User Experience
- Real-time progress updates
- Responsive design
- Dark/light theme support
- Export functionality
- Detailed error messages
- Automatic cleanup of temporary files

## API Documentation

### Endpoints

- `GET /` - Home page
- `POST /pre-check` - Repository validation and payment setup
- `POST /concatenate` - Process repository files
- `GET /download/{file_path}` - Download concatenated files
- `GET /success` - Payment success handler
- `GET /cancel` - Payment cancellation handler

## Error Handling

The service includes comprehensive error handling for:
- Invalid repository URLs
- Authentication failures
- Rate limit exceeded
- File system errors
- Payment processing issues
- Invalid file types
- Network connectivity problems

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - See LICENSE file for details

## Author
gilzero / Weiming Chen
https://weiming.ai

## Known Issues
- not all stats info are passed to the front end
- compute stats is across files, should be centralized
- UI

## Future Improvements
- feed to LLM
- refactor

## Checkpoints
- 2025-02-13: Alpha release

## Deployment
https://combine.codes


Last updated: 2025-02-28 19:56:13 UTC+0800
