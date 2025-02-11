/**
 * @fileoverview Results visualization and export functionality.
 * 
 * Handles displaying and exporting repository analysis:
 * - Statistics display
 * - Results visualization
 * - PNG/PDF export functionality
 * - Confetti animations
 * - Directory tree visualization
 * 
 * @requires ./utils.js
 * @requires ./ui.js
 * @requires ./main.js
 */

// Results display and export functionality
import { formatFileSize, formatNumber, generateUniqueFilename } from './utils.js';
import { showToast } from './ui.js';
import { currentRepoName } from './main.js';

export function displayResults(data) {
    if (!data || !data.statistics) {
        throw new Error('Invalid results data');
    }

    const result = document.getElementById('result');
    const stats = data.statistics;

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
                <!-- Statistics Cards -->
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
                    <!-- ... other stat cards ... -->
                </div>

                <!-- Download Button -->
                <div class="mt-4 text-center">
                    <a href="/download/${data.output_file}" class="btn btn-success btn-lg">
                        <i class="bi bi-download me-2"></i>
                        Download Combined Files
                    </a>
                </div>
            </div>
        </div>`;

    document.getElementById('exportButtons').classList.remove('d-none');
    triggerConfetti();
}

export async function exportAsImage() {
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
        link.download = generateUniqueFilename(currentRepoName, 'png');
        link.href = image;
        link.click();
    } catch (error) {
        console.error('Error exporting image:', error);
        showToast('Failed to export image. Please try again.', 'error');
    }
}

export async function exportAsPDF() {
    // ... PDF export logic (similar to exportAsImage) ...
}

export function triggerConfetti() {
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
} 