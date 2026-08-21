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
        // When true, displayWarnings() skips the Recommended Range / Ideal
        // block for callers that already show that info elsewhere on the
        // page (e.g. rent-settings' CWI helper box). Store-item tier
        // recommendations still render, since no equivalent proactive
        // display exists for them.
        this.suppressRecommendationsEcho = options.suppressRecommendationsEcho === true;

        if (this.autoValidate) {
            this.initializeAutoValidation();
        }
    }

    /**
     * Initialize automatic validation for all marked inputs
     */
    initializeAutoValidation() {
        const inputs = document.querySelectorAll('[data-economy-validate]');
        const triggerInputs = document.querySelectorAll('[data-economy-trigger]');

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

        triggerInputs.forEach(input => {
            const targetSelector = input.dataset.economyTrigger;
            if (!targetSelector) return;
            const target = document.querySelector(targetSelector);
            if (!target) return;
            const eventType = input.tagName === 'SELECT' ? 'change' : 'input';
            input.addEventListener(eventType, () => {
                target.dispatchEvent(new Event('input'));
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
        const claimTypeTarget = input.dataset.economyClaimTypeTarget;
        const coverageTarget = input.dataset.economyCoverageTarget;
        const periodTarget = input.dataset.economyPeriodTarget;

        // Collect block parameter (important for multi-class teachers)
        let additionalParams = {};
        const settingsBlockInput = document.getElementById('settings_block_selector') ||
                                  document.querySelector('input[name="settings_block"]') ||
                                  document.querySelector('select[name="block"]');

        // CRITICAL: Always include block parameter so validation uses the correct payroll settings
        if (settingsBlockInput) {
            additionalParams.block = settingsBlockInput.value;
        }
        if (feature === 'insurance') {
            const getParamValue = (targetSelector, paramName) => {
                if (!targetSelector) return;
                const field = document.querySelector(targetSelector);
                if (!field) return;

                const parsedValue = parseFloat(field.value);
                if (!isNaN(parsedValue) && parsedValue > 0) {
                    additionalParams[paramName] = parsedValue;
                }
            };

            const claimTypeField = claimTypeTarget ? document.querySelector(claimTypeTarget) : null;
            if (claimTypeField && claimTypeField.value) {
                additionalParams.claim_type = claimTypeField.value;
            }

            getParamValue(coverageTarget, 'max_claim_amount');
            getParamValue(periodTarget, 'max_payout_per_period');
        }

        // For rent validation, collect additional frequency parameters from the form
        if (feature === 'rent') {
            const frequencyTypeInput = document.getElementById('frequency_type');
            const customFrequencyValueInput = document.getElementById('custom_frequency_value');
            const customFrequencyUnitInput = document.getElementById('custom_frequency_unit');

            if (frequencyTypeInput) {
                additionalParams.frequency_type = frequencyTypeInput.value;
            }
            if (customFrequencyValueInput) {
                additionalParams.custom_frequency_value = parseFloat(customFrequencyValueInput.value) || null;
            }
            if (customFrequencyUnitInput) {
                additionalParams.custom_frequency_unit = customFrequencyUnitInput.value;
            }
        }

        try {
            const result = await this.validate(feature, value, frequency, additionalParams);
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

        // Alert-card visual: card wrapper + colored header + body.
        // Matches templates/macros/cards.html alert_card macro so the
        // JS-rendered alerts blend with server-rendered ones.
        //
        // Per-warning cards (not aggregated) — each warning carries its
        // own title + message so the header describes the specific
        // condition ("Rent setting might be too low") and the body
        // carries the detailed prose ("The entered rent of $X is lower
        // than the recommended minimum of $Y..."). Backends that emit
        // only `message` (no `title`) fall back to a generic level title.
        const genericTitle = {
            danger: 'Critical Issue',
            warning: 'Warning',
            success: 'Looks Good',
            info: 'Recommendations',
        };
        const iconForLevel = {
            danger: 'error',
            warning: 'info',
            success: 'check_circle',
            info: 'lightbulb',
        };
        const alertCard = (level, title, icon, bodyHtml) => {
            const textClass = level === 'warning' ? 'text-dark' : 'text-white';
            return (
                `<div class="card shadow-sm mb-3">` +
                    `<div class="card-header bg-${level} ${textClass} py-3">` +
                        `<h6 class="mb-0 fw-semibold ${textClass}">` +
                            `<span class="material-symbols-outlined me-2" style="vertical-align: text-bottom;">${icon}</span>` +
                            title +
                        `</h6>` +
                    `</div>` +
                    `<div class="card-body">${bodyHtml}</div>` +
                `</div>`
            );
        };

        const renderWarningCards = (items, level) => {
            items.forEach(w => {
                const title = w.title || genericTitle[level] || 'Notice';
                const icon = w.icon || iconForLevel[level] || 'info';
                html += alertCard(level, title, icon, `<div>${w.message}</div>`);
            });
        };

        if (critical.length > 0) {
            renderWarningCards(critical, 'danger');
        }
        if (warning.length > 0) {
            renderWarningCards(warning, 'warning');
        }
        if (success.length > 0 && critical.length === 0 && warning.length === 0) {
            renderWarningCards(success, 'success');
        }

        // Display recommendations (skipped on pages that already show a
        // proactive CWI recommendation elsewhere, per suppressRecommendationsEcho).
        if (recommendations && Object.keys(recommendations).length > 0) {
            let bodyHtml = '';

            if (!this.suppressRecommendationsEcho &&
                recommendations.min !== undefined && recommendations.max !== undefined) {
                bodyHtml += `<div class="recommendation-range">`;
                bodyHtml += `<strong>Recommended Range:</strong> $${recommendations.min} - $${recommendations.max}`;
                if (recommendations.frequency) {
                    bodyHtml += ` <span class="text-muted">per ${recommendations.frequency}</span>`;
                }
                if (recommendations.recommended) {
                    bodyHtml += `<br><strong>Ideal:</strong> $${recommendations.recommended}`;
                    if (recommendations.frequency) {
                        bodyHtml += ` <span class="text-muted">per ${recommendations.frequency}</span>`;
                    }
                }
                if (recommendations.frequency && recommendations.frequency !== 'weekly' &&
                    recommendations.min_weekly !== undefined) {
                    bodyHtml += `<br><small class="text-muted">Weekly equivalent: $${recommendations.min_weekly} - $${recommendations.max_weekly}</small>`;
                }
                bodyHtml += `</div>`;
            }

            if (recommendations.tiers) {
                bodyHtml += '<div class="pricing-tiers mt-2">';
                bodyHtml += '<strong>Store Item Pricing Tiers:</strong>';
                bodyHtml += '<div class="row mt-1">';
                Object.entries(recommendations.tiers).forEach(([tier, range]) => {
                    bodyHtml += `<div class="col-6 col-md-3 mb-1">`;
                    bodyHtml += `<span class="badge bg-secondary">${tier.toUpperCase()}</span><br>`;
                    bodyHtml += `<small>$${range.min} - $${range.max}</small>`;
                    bodyHtml += `</div>`;
                });
                bodyHtml += '</div></div>';
            }

            if (bodyHtml.trim()) {
                html += alertCard('info', 'Recommendations', 'lightbulb', bodyHtml);
            }
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
    async validate(feature, value, frequency = 'weekly', additionalParams = {}) {
        try {
            const requestBody = {
                value: value,
                frequency: frequency,
                ...additionalParams
                // Note: expected_weekly_hours is read from payroll_settings by the backend
            };

            const response = await fetch(`${this.apiBaseUrl}/validate/${feature}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(requestBody)
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
        try {
            const requestBody = {};

            // expected_weekly_hours is read from EconomicEngine by the backend.
            // If explicitly provided (simulator), include it for override.
            if (expectedWeeklyHours !== null) {
                requestBody.expected_weekly_hours = expectedWeeklyHours;
            }

            const response = await fetch(`${this.apiBaseUrl}/analyze`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify(requestBody)
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

        const fmt = (v) => (typeof v === 'number' ? `$${v.toFixed(2)}` : '—');
        const rec = cwiData.recommendations || {};
        const rentMonthly = rec.rent || {};
        const rentWeekly = rec.rent_weekly || {};

        // Frequency-aware selection: derive the correct band for whatever
        // rent-frequency the teacher has picked. The payload only carries
        // weekly and monthly buckets; other frequencies are converted
        // proportionally from weekly (the smaller unit — avoids
        // compounding month-length approximation).
        const freqEl = document.getElementById('frequency_type');
        const freq = (freqEl && freqEl.value) || 'monthly';
        const customValueEl = document.getElementById('custom_frequency_value');
        const customUnitEl = document.getElementById('custom_frequency_unit');
        const customValue = customValueEl ? parseFloat(customValueEl.value) : NaN;
        const customUnit = customUnitEl ? customUnitEl.value : '';

        const scale = (band, factor) => (band && band.min != null ? {
            min: band.min * factor,
            max: band.max * factor,
            recommended: band.recommended * factor,
        } : {});

        let rentBand = rentMonthly;
        let periodLabel = 'per month';
        let showNote = false;

        if (freq === 'weekly') {
            rentBand = rentWeekly;
            periodLabel = 'per week';
        } else if (freq === 'daily') {
            rentBand = scale(rentWeekly, 1 / 7);
            periodLabel = 'per day';
        } else if (freq === 'biweekly') {
            rentBand = scale(rentWeekly, 2);
            periodLabel = 'every 2 weeks';
        } else if (freq === 'custom') {
            // Custom = <value> <unit>. Convert from weekly for days/weeks,
            // from monthly for months (natural unit alignment).
            if (Number.isFinite(customValue) && customValue > 0) {
                if (customUnit === 'days') {
                    rentBand = scale(rentWeekly, customValue / 7);
                    periodLabel = `every ${customValue} day${customValue === 1 ? '' : 's'}`;
                } else if (customUnit === 'weeks') {
                    rentBand = scale(rentWeekly, customValue);
                    periodLabel = `every ${customValue} week${customValue === 1 ? '' : 's'}`;
                } else if (customUnit === 'months') {
                    rentBand = scale(rentMonthly, customValue);
                    periodLabel = `every ${customValue} month${customValue === 1 ? '' : 's'}`;
                } else {
                    // Unit not set yet — show monthly with a hint.
                    showNote = true;
                }
            } else {
                showNote = true;
            }
        }
        // (else: monthly — the default.)

        // Percent-of-CWI derivation for the calculation-details line.
        // rent bands are computed as cwi × ratio; the ratio is not exposed
        // in the payload, so recover it here from the weekly band (weekly
        // is the base unit — closest to CWI itself which is a weekly value).
        const cwiValue = typeof cwiData.cwi === 'number' ? cwiData.cwi : null;
        const pctLow = (cwiValue && rentWeekly.min != null)
            ? ((rentWeekly.min / cwiValue) * 100).toFixed(0)
            : null;
        const pctHigh = (cwiValue && rentWeekly.max != null)
            ? ((rentWeekly.max / cwiValue) * 100).toFixed(0)
            : null;

        // Top-level card visual: dark-green header (bg-primary, role-scoped),
        // white body with the recommendation prose + collapsed calculation
        // details. Mirrors templates/macros/cards.html top_card structure.
        let html = '<div class="card shadow-sm">';
        html += '<div class="card-header bg-primary text-white py-3">';
        html += '<h5 class="mb-0 fw-bold text-white">';
        html += '<span class="material-symbols-outlined me-2" style="vertical-align: text-bottom;">thumb_up</span>';
        html += 'Pricing Recommendation';
        html += '</h5>';
        html += '</div>';
        html += '<div class="card-body">';

        // Primary sentence: range recommendation.
        if (rentBand.min != null && rentBand.max != null) {
            html += `<p class="mb-2">Based on your current economic settings, we recommend setting <strong>rent</strong> between <strong>${fmt(rentBand.min)}</strong> and <strong>${fmt(rentBand.max)}</strong> ${periodLabel}`;
            if (showNote) {
                html += ` <span class="text-muted small">(shown as monthly — set your custom frequency to refine)</span>`;
            }
            html += '.</p>';
        } else {
            html += '<p class="mb-2 text-muted">Recommendation unavailable — insufficient data.</p>';
        }

        // Collapsed: how we got there.
        html += '<details class="mt-2">';
        html += '<summary style="cursor: pointer;" class="fw-semibold text-primary">Calculation details</summary>';
        html += '<div class="mt-2 small">';
        html += `<div>Your current Classroom Wage Index (CWI) is <strong>${fmt(cwiValue)}</strong> per week.</div>`;
        if (rec.policy_label) {
            html += `<div>You have selected the <strong>${rec.policy_label}</strong> economic policy.</div>`;
        }
        if (pctLow && pctHigh) {
            html += `<div>Under this policy, <strong>rent</strong> should fall between <strong>${pctLow}%</strong> and <strong>${pctHigh}%</strong> of your CWI.</div>`;
        }
        if (cwiData.cwi_breakdown || cwiData.breakdown) {
            const breakdown = cwiData.cwi_breakdown || cwiData.breakdown;
            html += '<hr class="my-2">';
            html += `<div class="text-muted">Pay rate: $${breakdown.pay_rate_per_hour?.toFixed(2) || 'N/A'} per hour</div>`;
            html += `<div class="text-muted">Expected hours: ${breakdown.expected_weekly_hours || 'N/A'} per week</div>`;
        }
        html += '</div></details>';

        html += '</div>';  // card-body
        html += '</div>';  // card

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
