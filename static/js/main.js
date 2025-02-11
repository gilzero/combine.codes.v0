// Global variables
let ignorePatterns = [];
let currentRepoName = '';
let lastRequest = null;

// Initialize Stripe
const stripe = Stripe(STRIPE_PUBLISHABLE_KEY);

let activeCheckoutSessionId = null;

// Utility functions
function generateUniqueId() {
    return 'xxxxxxxx'.replace(/[x]/g, function(c) {
        var r = Math.random() * 16 | 0;
        return r.toString(16);
    });
}

function generateUniqueFilename(repoName, extension) {
    const timestamp = new Date().toISOString()
        .replace(/[-:]/g, '')
        .replace('T', '_')
        .replace(/\..+/, '');
    const uniqueId = generateUniqueId();
    const pid = Math.floor(Math.random() * 100000);
    return `file-stats_${repoName}_${timestamp}_pid${pid}_${uniqueId}.${extension}`;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// UI Functions
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast animate__animated animate__fadeInRight ${type}`;
    toast.innerHTML = `
        <div class="toast-header">
            <i class="bi bi-${type === 'success' ? 'check-circle' : 'info-circle'} me-2"></i>
            <strong class="me-auto">Notification</strong>
            <button type="button" class="btn-close" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.remove('animate__fadeInRight');
        toast.classList.add('animate__fadeOutRight');
        setTimeout(() => toast.remove(), 1000);
    }, 3000);
}

function updateProgress(value) {
    const progressBar = document.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.style.width = `${value}%`;
        progressBar.setAttribute('aria-valuenow', value);
    }
}

function triggerConfetti() {
    const count = 200;
    const defaults = {
        origin: { y: 0.7 },
        zIndex: 9999
    };

    function fire(particleRatio, opts) {
        confetti({
            ...defaults,
            ...opts,
            particleCount: Math.floor(count * particleRatio),
        });
    }

    fire(0.25, {
        spread: 26,
        startVelocity: 55,
    });

    fire(0.2, {
        spread: 60,
    });

    fire(0.35, {
        spread: 100,
        decay: 0.91,
        scalar: 0.8
    });

    fire(0.1, {
        spread: 120,
        startVelocity: 25,
        decay: 0.92,
        scalar: 1.2
    });

    fire(0.1, {
        spread: 120,
        startVelocity: 45,
    });
}

// Theme handling
function setTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    const icon = document.querySelector('[data-theme-icon]');
    const toggle = document.querySelector('.theme-toggle');
    icon.className = theme === 'dark' ? 'bi bi-moon-stars-fill' : 'bi bi-sun-fill';
    toggle.setAttribute('aria-pressed', theme === 'dark');
    localStorage.setItem('theme', theme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
}

function initializeTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        setTheme(savedTheme);
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        setTheme('dark');
    }

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem('theme')) {
            setTheme(e.matches ? 'dark' : 'light');
        }
    });
}

// Export functionality
async function exportAsImage() {
    const result = document.getElementById('result');
    if (!result.firstElementChild) return;

    try {
        const clone = result.cloneNode(true);
        document.body.appendChild(clone);
        clone.style.position = 'absolute';
        clone.style.left = '-9999px';
        clone.style.transform = 'none';

        await new Promise(resolve => setTimeout(resolve, 100));

        const canvas = await html2canvas(clone, {
            scale: 2,
            backgroundColor: getComputedStyle(document.body).backgroundColor,
            logging: false,
            removeContainer: true
        });

        document.body.removeChild(clone);

        const image = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        const filename = generateUniqueFilename(currentRepoName, 'png');
        link.download = filename;
        link.href = image;
        link.click();
    } catch (error) {
        console.error('Error exporting image:', error);
        showToast('Failed to export image. Please try again.', 'error');
    }
}

async function exportAsPDF() {
    const result = document.getElementById('result');
    if (!result.firstElementChild) return;

    try {
        const clone = result.cloneNode(true);
        document.body.appendChild(clone);
        clone.style.position = 'absolute';
        clone.style.left = '-9999px';
        clone.style.transform = 'none';

        await new Promise(resolve => setTimeout(resolve, 100));

        const canvas = await html2canvas(clone, {
            scale: 2,
            backgroundColor: getComputedStyle(document.body).backgroundColor,
            logging: false,
            removeContainer: true
        });

        document.body.removeChild(clone);

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF({
            orientation: 'portrait',
            unit: 'px',
            format: [canvas.width / 2, canvas.height / 2]
        });

        pdf.addImage(
            canvas.toDataURL('image/png'),
            'PNG',
            0,
            0,
            canvas.width / 2,
            canvas.height / 2
        );

        const filename = generateUniqueFilename(currentRepoName, 'pdf');
        pdf.save(filename);
    } catch (error) {
        console.error('Error exporting PDF:', error);
        showToast('Failed to export PDF. Please try again.', 'error');
    }
}

// Main functionality
function showError(message) {
    const errorArea = document.getElementById('error-area');
    errorArea.innerHTML = `
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <i class="bi bi-exclamation-triangle-fill me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
}

function showProcessing(show = true) {
    const processingArea = document.getElementById('processing-area');
    if (show) {
        processingArea.classList.remove('d-none');
    } else {
        processingArea.classList.add('d-none');
    }
}

async function handleRepositorySubmit(event) {
    event.preventDefault();
    
    // Clear previous errors and results
    document.getElementById('error-area').innerHTML = '';
    document.getElementById('confirmation-area').innerHTML = '';
    document.getElementById('result-area').innerHTML = '';
    
    const repoUrl = document.getElementById('repo-url').value;
    const githubToken = document.getElementById('github-token').value;
    
    if (!repoUrl) {
        showError('Please enter a GitHub repository URL');
        return;
    }
    
    showProcessing(true);
    
    try {
        // First, do pre-check
        const preCheckResponse = await fetch('/pre-check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                repo_url: repoUrl,
                github_token: githubToken || null,
                base_url: window.location.origin + '/'
            }),
        });
        
        showProcessing(false);
        
        if (!preCheckResponse.ok) {
            const error = await preCheckResponse.json();
            console.log('Error response:', error);
            
            let errorMessage = error.detail.message || 'Failed to process repository';
            let suggestionMessage = '';
            
            // Add specific suggestions based on error type
            switch (error.detail.error_type) {
                case 'InvalidTokenFormat':
                    suggestionMessage = 'Please check your token format and try again.';
                    break;
                case 'InsufficientPermissions':
                    suggestionMessage = 'Please ensure your token has the required permissions (repo scope).';
                    break;
                case 'RateLimitExceeded':
                    suggestionMessage = 'Please try again later or provide a GitHub token to increase rate limits.';
                    break;
                case 'RepositoryNotFound':
                    if (error.detail.requires_token) {
                        suggestionMessage = 'This might be a private repository. Try providing a GitHub token.';
                    } else {
                        suggestionMessage = 'Please check the repository URL and try again.';
                    }
                    break;
                case 'AuthenticationError':
                    suggestionMessage = 'Please provide a valid GitHub token and try again.';
                    break;
            }
            
            // Show error with suggestion if available
            showError(`${errorMessage}${suggestionMessage ? '\n\n' + suggestionMessage : ''}`);
            return;
        }
        
        const preCheckData = await preCheckResponse.json();
        
        // Show repository information and payment confirmation
        updateRepositoryDetails(preCheckData);
        
        const confirmationHtml = `
            <div class="card">
                <div class="card-header">
                    <h5 class="card-title mb-0">Repository Details</h5>
                </div>
                <div class="card-body">
                    <dl class="row mb-0">
                        <dt class="col-sm-4">Repository:</dt>
                        <dd class="col-sm-8">${preCheckData.owner}/${preCheckData.repo_name}</dd>
                        
                        <dt class="col-sm-4">Estimated Files:</dt>
                        <dd class="col-sm-8">${preCheckData.estimated_file_count || 'Calculating...'}</dd>
                        
                        <dt class="col-sm-4">Repository Size:</dt>
                        <dd class="col-sm-8">${preCheckData.repository_size_kb ? formatFileSize(preCheckData.repository_size_kb * 1024) : 'Calculating...'}</dd>
                        
                        <dt class="col-sm-4">Price:</dt>
                        <dd class="col-sm-8">$${preCheckData.price_usd.toFixed(2)} USD</dd>
                    </dl>
                </div>
                <div class="card-footer text-end">
                    <button type="button" id="cancel-payment" class="btn btn-secondary me-2">Cancel</button>
                    <button type="button" id="proceed-payment" class="btn btn-primary">
                        <i class="bi bi-credit-card me-2"></i>Proceed to Payment
                    </button>
                </div>
            </div>
        `;
        
        document.getElementById('confirmation-area').innerHTML = confirmationHtml;
        
        // Store checkout session ID
        activeCheckoutSessionId = preCheckData.checkout_session_id;
        
        // Add event listeners
        document.getElementById('proceed-payment').addEventListener('click', handlePayment);
        document.getElementById('cancel-payment').addEventListener('click', () => {
            document.getElementById('confirmation-area').innerHTML = '';
        });
        
    } catch (error) {
        console.error('Error:', error);
        showError('An unexpected error occurred. Please try again later.');
    }
}

async function handlePayment() {
    try {
        // Redirect to Stripe Checkout
        const result = await stripe.redirectToCheckout({
            sessionId: activeCheckoutSessionId
        });
        
        if (result.error) {
            throw new Error(result.error.message);
        }
    } catch (error) {
        console.error('Payment error:', error);
        showError('Payment failed. Please try again.');
    }
}

async function verifyPayment(sessionId) {
    try {
        const response = await fetch('/verify-payment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                checkout_session_id: sessionId
            }),
        });
        
        if (!response.ok) {
            throw new Error('Payment verification failed');
        }
        
        const data = await response.json();
        
        if (data.can_proceed) {
            // Payment successful, proceed with concatenation
            processConcatenation(sessionId);
        } else if (data.status === 'pending') {
            // Check again in 2 seconds
            setTimeout(() => verifyPayment(sessionId), 2000);
        } else {
            showError(data.message);
        }
    } catch (error) {
        console.error('Verification error:', error);
        showError('Payment verification failed. Please try again.');
    }
}

async function processConcatenation(sessionId) {
    try {
        const response = await fetch('/concatenate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                repo_url: document.getElementById('repo-url').value,
                github_token: document.getElementById('github-token').value || null,
                checkout_session_id: sessionId
            }),
        });
        
        if (!response.ok) {
            throw new Error('Concatenation failed');
        }
        
        const result = await response.json();
        displayResults(result);
    } catch (error) {
        console.error('Concatenation error:', error);
        showError('Failed to concatenate files. Please try again.');
    }
}

// Check for payment success on page load
document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    
    if (sessionId) {
        verifyPayment(sessionId);
    }
});

function displayResults(data) {
    const result = document.getElementById('result');
    const stats = data.statistics || {};
    stats.file_stats = stats.file_stats || {};
    stats.dir_stats = stats.dir_stats || {};
    stats.filter_stats = stats.filter_stats || {};

    // Helper functions
    const formatNumber = (num) => {
        return (num || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    };

    const formatBytes = (bytes) => {
        if (!bytes || bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    result.innerHTML = `
        <div class="card shadow-sm success-animate">
            <div class="card-header bg-success text-white d-flex align-items-center">
                <i class="bi bi-check-circle-fill me-2"></i>
                <span class="flex-grow-1">Processing Complete!</span>
                <button class="btn btn-sm btn-outline-light" onclick="triggerConfetti()">
                    <i class="bi bi-stars"></i> Celebrate
                </button>
            </div>
            <div class="card-body">
                <!-- Directory Tree Visualization -->
                <div class="row g-3 mb-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <i class="bi bi-diagram-3 me-2"></i>Directory Structure
                            </div>
                            <div class="card-body">
                                <div class="directory-tree font-monospace small">
                                    ${(() => {
                                        function renderNode(node, prefix = "", isLast = true) {
                                            if (!node) return '';
                                            
                                            const currentPrefix = prefix + (isLast ? "└── " : "├── ");
                                            const nextPrefix = prefix + (isLast ? "    " : "│   ");
                                            
                                            let sizeInfo = "";
                                            if (node.type === 'file' && node.metadata?.size !== null) {
                                                sizeInfo = ` (${formatBytes(node.metadata.size)})`;
                                            }
                                            
                                            let output = `<div class="tree-node">
                                                <span class="tree-prefix">${currentPrefix}</span>
                                                <span class="tree-name ${node.type}">${node.name}</span>
                                                <span class="tree-size">${sizeInfo}</span>
                                            </div>`;
                                            
                                            if (node.children && node.children.length > 0) {
                                                node.children.forEach((child, index) => {
                                                    output += renderNode(child, nextPrefix, index === node.children.length - 1);
                                                });
                                            }
                                            
                                            return output;
                                        }
                                        
                                        return stats.dir_stats.tree ? 
                                            renderNode(stats.dir_stats.tree) : 
                                            '<div class="text-muted">No directory structure available</div>';
                                    })()}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- File Processing Overview -->
                <div class="row g-3 mb-4">
                    <div class="col-md-3">
                        <div class="card h-100 border-primary">
                            <div class="card-body text-center">
                                <h6 class="card-subtitle mb-2 text-muted">Files Processed</h6>
                                <h2 class="card-title mb-0 text-primary">
                                    ${formatNumber(stats.file_stats.processed_files)}
                                    <small class="text-muted">/ ${formatNumber(stats.file_stats.total_files)}</small>
                                </h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100 border-info">
                            <div class="card-body text-center">
                                <h6 class="card-subtitle mb-2 text-muted">Total Size</h6>
                                <h2 class="card-title mb-0 text-info">
                                    ${formatBytes(stats.file_stats.total_size)}
                                </h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100 border-success">
                            <div class="card-body text-center">
                                <h6 class="card-subtitle mb-2 text-muted">Lines of Code</h6>
                                <h2 class="card-title mb-0 text-success">
                                    ${formatNumber(stats.file_stats.total_lines - (stats.file_stats.empty_lines || 0) - (stats.file_stats.comment_lines || 0))}
                                </h2>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100 border-warning">
                            <div class="card-body text-center">
                                <h6 class="card-subtitle mb-2 text-muted">Directories</h6>
                                <h2 class="card-title mb-0 text-warning">
                                    ${formatNumber(stats.dir_stats.total_dirs)}
                                </h2>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Download Button -->
                <div class="mt-4 text-center">
                    <a href="/download/${data.output_file}" class="btn btn-success btn-lg">
                        <i class="bi bi-download me-2"></i>
                        Download Combined Files
                    </a>
                    <div class="text-muted mt-2">
                        <small>
                            <i class="bi bi-info-circle me-1"></i>
                            Output file ready
                        </small>
                    </div>
                </div>
            </div>
        </div>`;

    // Show export buttons
    document.getElementById('exportButtons').classList.remove('d-none');
    
    // Trigger confetti animation
    triggerConfetti();
}

function updateRepositoryDetails(preCheckData) {
    const detailsHtml = `
        <div class="card">
            <div class="card-header">
                <h5 class="card-title mb-0">Repository Details</h5>
            </div>
            <div class="card-body">
                <dl class="row mb-0">
                    <dt class="col-sm-4">Repository:</dt>
                    <dd class="col-sm-8">${preCheckData.owner}/${preCheckData.repo_name}</dd>
                    
                    <dt class="col-sm-4">Estimated Files:</dt>
                    <dd class="col-sm-8">${preCheckData.estimated_file_count ? formatNumber(preCheckData.estimated_file_count) : 'Calculating...'}</dd>
                    
                    <dt class="col-sm-4">Repository Size:</dt>
                    <dd class="col-sm-8">${preCheckData.repository_size_kb ? formatFileSize(preCheckData.repository_size_kb * 1024) : 'Calculating...'}</dd>
                    
                    <dt class="col-sm-4">Price:</dt>
                    <dd class="col-sm-8">$${preCheckData.price_usd.toFixed(2)} USD</dd>
                </dl>
            </div>
        </div>
    `;
    document.getElementById('repository-details').innerHTML = detailsHtml;
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    initializeEventListeners();
});

function initializeEventListeners() {
    // Input validation
    document.getElementById('repo-url').addEventListener('input', validateInput);
    document.getElementById('repo-url').addEventListener('paste', validateInput);

    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const status = document.getElementById('status');
            if (!status.classList.contains('d-none')) {
                // TODO: Add ability to cancel processing
                console.log('Processing cancellation not implemented');
            }
        }
    });

    // Result observer for export buttons
    const result = document.getElementById('result');
    const originalSetInnerHTML = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML').set;
    Object.defineProperty(result, 'innerHTML', {
        set: function(value) {
            originalSetInnerHTML.call(this, value);
            const exportButtons = document.getElementById('exportButtons');
            exportButtons.classList.toggle('d-none', !value.trim());
        },
        get: function() {
            return Element.prototype.innerHTML.get.call(this);
        }
    });

    // Button animations
    document.querySelectorAll('.btn').forEach(button => {
        button.addEventListener('click', function(e) {
            const circle = document.createElement('div');
            const d = Math.max(this.clientWidth, this.clientHeight);
            
            circle.style.width = circle.style.height = d + 'px';
            circle.style.left = e.clientX - this.offsetLeft - d/2 + 'px';
            circle.style.top = e.clientY - this.offsetTop - d/2 + 'px';
            circle.classList.add('ripple');
            
            this.appendChild(circle);
            setTimeout(() => circle.remove(), 600);
        });
    });
}
