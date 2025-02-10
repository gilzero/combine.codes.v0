// Global variables
let ignorePatterns = [];
let currentRepoName = '';
let lastRequest = null;

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
async function concatenateFiles() {
    const repoUrl = document.getElementById('repoUrl').value;
    const githubToken = document.getElementById('githubToken').value;
    const additionalIgnores = document.getElementById('additionalIgnores').value
        .split('\n')
        .filter(line => line.trim());
    const status = document.getElementById('status');
    const result = document.getElementById('result');

    lastRequest = {
        repo_url: repoUrl,
        github_token: githubToken,
        additional_ignores: additionalIgnores
    };

    status.classList.remove('d-none');
    result.innerHTML = '';

    try {
        const response = await fetch('/concatenate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(lastRequest)
        });

        const data = await response.json();

        if (!response.ok) {
            displayError(data);
            return;
        }

        // Process and display results
        displayResults(data);
        triggerConfetti();

    } catch (error) {
        displayError({
            detail: {
                status: "error",
                message: "Network error occurred while processing your request.",
                error_type: "NetworkError",
                details: {
                    help: "Please check your internet connection and try again."
                }
            }
        });
    } finally {
        status.classList.add('d-none');
    }
}

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

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    initializeEventListeners();
});

function initializeEventListeners() {
    // Input validation
    document.getElementById('repoUrl').addEventListener('input', validateInput);
    document.getElementById('repoUrl').addEventListener('paste', validateInput);

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
