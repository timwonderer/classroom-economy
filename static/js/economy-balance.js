/**
 * Economy Balance Checker - Client-side integration
 *
 * Provides real-time validation and recommendations for economy settings
 * based on CWI (Classroom Wage Index) calculations per AGENTS specification.
 *
 * Usage:
 * 1. Include this script in your page
 * 2. Add data attributes to your input fields:
 *    - data-economy-validate="feature_type" (rent, insurance, fine, store_item)
 *    - data-economy-frequency="weekly" (for insurance only)
 * 3. Add a div for displaying warnings:
 *    - <div id="economy-warnings"></div>
 */

class EconomyBalanceChecker {
    constructor(options = {}) {
        this.apiBaseUrl = '/admin/api/economy';
        this.warningsContainer = options.warningsContainer || '#economy-warnings';
        this.autoValidate = options.autoValidate !== false;
        this.expectedWeeklyHours = options.expectedWeeklyHours || 5.0;
        this.debounceDelay = options.debounceDelay || 500;
        this.debounceTimer = null;
        this.currentCWI = null;

        if (this.autoValidate) {
            this.initializeAutoValidation();
        }
    }

    /**
     * Initialize automatic validation for all marked inputs
     */
    initializeAutoValidation() {
        const inputs = document.querySelectorAll('[data-economy-validate]');

        inputs.forEach(input => {
            input.addEventListener('input', (e) => {
                clearTimeout(this.debounceTimer);
                this.debounceTimer = setTimeout(() => {
                    this.validateInput(e.target);
                }, this.debounceDelay);
            });

            input.addEventListener('blur', (e) => {
                this.validateInput(e.target);
            });
        });
    }

    /**
     * Validate a single input field
     */
    async validateInput(input) {
        const feature = input.dataset.economyValidate;
        const value = parseFloat(input.value);

        if (isNaN(value) || value <= 0) {
            this.clearWarnings();
            return;
        }

        const frequency = input.dataset.economyFrequency || 'weekly';

        try {
            const result = await this.validate(feature, value, frequency);
            this.displayWarnings(result.warnings, result.recommendations);

            // Add visual feedback to input
            this.updateInputFeedback(input, result.warnings);
        } catch (error) {
            console.error('Validation error:', error);
        }
    }

    /**
     * Update input field visual feedback
     */
    updateInputFeedback(input, warnings) {
        // Remove existing feedback classes
        input.classList.remove('is-valid', 'is-invalid', 'is-warning');

        const criticalWarnings = warnings.filter(w => w.level === 'critical');
        const normalWarnings = warnings.filter(w => w.level === 'warning');
        const successWarnings = warnings.filter(w => w.level === 'success');

        if (criticalWarnings.length > 0) {
            input.classList.add('is-invalid');
        } else if (normalWarnings.length > 0) {
            input.classList.add('is-warning');
        } else if (successWarnings.length > 0) {
            input.classList.add('is-valid');
        }
    }

    /**
     * Display warnings and recommendations in the warnings container
     */
    displayWarnings(warnings, recommendations) {
        const container = document.querySelector(this.warningsContainer);
        if (!container) return;

        if (warnings.length === 0) {
            container.innerHTML = '';
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';

        let html = '<div class="economy-balance-feedback">';

        const critical = warnings.filter(w => w.level === 'critical');
        const warning = warnings.filter(w => w.level === 'warning');
        const success = warnings.filter(w => w.level === 'success');

        if (critical.length > 0) {
            html += '<div class="alert alert-danger mb-2">';
            html += '<strong><i class="bi bi-exclamation-triangle-fill"></i> Critical Issues:</strong><ul class="mb-0 mt-1">';
            critical.forEach(w => {
                html += `<li>${w.message}</li>`;
            });
            html += '</ul></div>';
        }

        if (warning.length > 0) {
            html += '<div class="alert alert-warning mb-2">';
            html += '<strong><i class="bi bi-exclamation-circle-fill"></i> Warnings:</strong><ul class="mb-0 mt-1">';
            warning.forEach(w => {
                html += `<li>${w.message}</li>`;
            });
            html += '</ul></div>';
        }

        if (success.length > 0 && critical.length === 0 && warning.length === 0) {
            html += '<div class="alert alert-success mb-2">';
            html += '<strong><i class="bi bi-check-circle-fill"></i> Balance Check:</strong><ul class="mb-0 mt-1">';
            success.forEach(w => {
                html += `<li>${w.message}</li>`;
            });
            html += '</ul></div>';
        }

        // Display recommendations
        if (recommendations && Object.keys(recommendations).length > 0) {
            html += '<div class="alert alert-info mb-0">';
            html += '<strong><i class="bi bi-lightbulb-fill"></i> Recommendations:</strong>';
            html += '<div class="mt-2">';

            if (recommendations.min !== undefined && recommendations.max !== undefined) {
                html += `<div class="recommendation-range">`;
                html += `<strong>Recommended Range:</strong> $${recommendations.min} - $${recommendations.max}`;
                if (recommendations.recommended) {
                    html += ` (Ideal: $${recommendations.recommended})`;
                }
                html += `</div>`;
            }

            if (recommendations.tiers) {
                html += '<div class="pricing-tiers mt-2">';
                html += '<strong>Store Item Pricing Tiers:</strong>';
                html += '<div class="row mt-1">';
                Object.entries(recommendations.tiers).forEach(([tier, range]) => {
                    html += `<div class="col-6 col-md-3 mb-1">`;
                    html += `<span class="badge bg-secondary">${tier.toUpperCase()}</span><br>`;
                    html += `<small>$${range.min} - $${range.max}</small>`;
                    html += `</div>`;
                });
                html += '</div></div>';
            }

            html += '</div></div>';
        }

        html += '</div>';

        container.innerHTML = html;
    }

    /**
     * Clear all warnings
     */
    clearWarnings() {
        const container = document.querySelector(this.warningsContainer);
        if (container) {
            container.innerHTML = '';
            container.style.display = 'none';
        }
    }

    /**
     * Get CSRF token from meta tag
     */
    getCsrfToken() {
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        return metaTag ? metaTag.getAttribute('content') : '';
    }

    /**
     * Calculate CWI based on pay rate
     */
    async calculateCWI(payRate, expectedWeeklyHours = null) {
        const hours = expectedWeeklyHours || this.expectedWeeklyHours;

        try {
            const response = await fetch(`${this.apiBaseUrl}/calculate-cwi`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    pay_rate: payRate,
                    expected_weekly_hours: hours
                })
            });

            const data = await response.json();

            if (data.status === 'success') {
                this.currentCWI = data.cwi;
                return data;
            } else {
                throw new Error(data.message || 'Failed to calculate CWI');
            }
        } catch (error) {
            console.error('Error calculating CWI:', error);
            throw error;
        }
    }

    /**
     * Validate a specific value against CWI
     */
    async validate(feature, value, frequency = 'weekly') {
        try {
            const response = await fetch(`${this.apiBaseUrl}/validate/${feature}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    value: value,
                    frequency: frequency,
                    expected_weekly_hours: this.expectedWeeklyHours
                })
            });

            const data = await response.json();

            if (data.status === 'success' || data.status === 'warning') {
                this.currentCWI = data.cwi;
                return data;
            } else {
                throw new Error(data.message || 'Validation failed');
            }
        } catch (error) {
            console.error('Validation error:', error);
            throw error;
        }
    }

    /**
     * Get complete economy analysis
     */
    async analyzeEconomy(expectedWeeklyHours = null) {
        const hours = expectedWeeklyHours || this.expectedWeeklyHours;

        try {
            const response = await fetch(`${this.apiBaseUrl}/analyze`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({
                    expected_weekly_hours: hours
                })
            });

            const data = await response.json();

            if (data.status === 'success') {
                this.currentCWI = data.cwi;
                return data;
            } else {
                throw new Error(data.message || 'Analysis failed');
            }
        } catch (error) {
            console.error('Analysis error:', error);
            throw error;
        }
    }

    /**
     * Display CWI info in a designated container
     */
    displayCWIInfo(cwiData, containerId = '#cwi-info') {
        const container = document.querySelector(containerId);
        if (!container) return;

        let html = '<div class="cwi-info-box alert alert-info">';
        html += '<h6><i class="bi bi-info-circle-fill"></i> Classroom Wage Index (CWI)</h6>';
        html += `<div class="cwi-value">Weekly Expected Income: <strong>$${cwiData.cwi.toFixed(2)}</strong></div>`;

        if (cwiData.cwi_breakdown || cwiData.breakdown) {
            html += '<details class="mt-2">';
            html += '<summary style="cursor: pointer;">Calculation Details</summary>';
            html += '<div class="mt-2 small">';
            const breakdown = cwiData.cwi_breakdown || cwiData.breakdown;
            html += `<div>Pay Rate: $${breakdown.pay_rate_per_hour?.toFixed(2) || 'N/A'}/hour</div>`;
            html += `<div>Expected Hours: ${breakdown.expected_weekly_hours || 'N/A'} hours/week</div>`;
            html += `<div>Total Weekly Minutes: ${breakdown.expected_weekly_minutes || 'N/A'} minutes</div>`;
            html += '</div></details>';
        }

        html += '</div>';

        container.innerHTML = html;
    }

    /**
     * Add recommendation badges to form sections
     */
    addRecommendationBadge(inputElement, recommendedValue) {
        const badge = document.createElement('span');
        badge.className = 'badge bg-info ms-2 economy-recommendation-badge';
        badge.innerHTML = `<i class="bi bi-lightbulb"></i> Recommended: $${recommendedValue.toFixed(2)}`;
        badge.style.cursor = 'pointer';
        badge.title = 'Click to use recommended value';

        badge.addEventListener('click', () => {
            inputElement.value = recommendedValue.toFixed(2);
            inputElement.dispatchEvent(new Event('input'));
        });

        // Remove existing badge if present
        const existingBadge = inputElement.parentElement.querySelector('.economy-recommendation-badge');
        if (existingBadge) {
            existingBadge.remove();
        }

        inputElement.parentElement.appendChild(badge);
    }
}

// Add CSS for warning state
const style = document.createElement('style');
style.textContent = `
    .is-warning {
        border-color: #ffc107 !important;
    }

    .economy-balance-feedback {
        margin-top: 1rem;
    }

    .economy-balance-feedback .alert {
        border-left: 4px solid;
    }

    .economy-balance-feedback .alert-danger {
        border-left-color: #dc3545;
    }

    .economy-balance-feedback .alert-warning {
        border-left-color: #ffc107;
    }

    .economy-balance-feedback .alert-success {
        border-left-color: #28a745;
    }

    .economy-balance-feedback .alert-info {
        border-left-color: #17a2b8;
    }

    .cwi-info-box {
        padding: 1rem;
        margin-bottom: 1rem;
        background: linear-gradient(135deg, #e3f2fd 0%, #f0f8ff 100%);
        border-left: 4px solid #2196f3;
    }

    .cwi-value {
        font-size: 1.1rem;
        margin-top: 0.5rem;
    }

    .economy-recommendation-badge {
        font-size: 0.85rem;
        padding: 0.35em 0.65em;
        vertical-align: middle;
    }

    .pricing-tiers .badge {
        display: inline-block;
        margin-bottom: 0.25rem;
    }
`;
document.head.appendChild(style);

// Export for use in other scripts
window.EconomyBalanceChecker = EconomyBalanceChecker;
