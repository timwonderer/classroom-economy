/**
 * Centralized Timezone Utility
 * 
 * Provides consistent timezone handling across all pages with:
 * - Browser timezone detection
 * - PST (America/Los_Angeles) fallback
 * - Consistent timestamp formatting
 * - Optional server synchronization
 */

(function() {
    'use strict';

    // Default timezone if detection fails
    const DEFAULT_TIMEZONE = 'America/Los_Angeles';

    /**
     * Detect user's timezone from browser
     * Falls back to PST if detection fails
     * @note Requires Intl.DateTimeFormat API with timeZone support (IE not supported)
     * @returns {string} IANA timezone name (e.g., 'America/New_York', 'America/Los_Angeles')
     */
    function detectTimezone() {
        try {
            // Try to get timezone from browser
            const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            if (timezone && timezone.length > 0) {
                return timezone;
            }
        } catch (e) {
            console.warn('Timezone detection failed, using PST:', e);
        }
        
        // Fallback to PST
        return DEFAULT_TIMEZONE;
    }

    /**
     * Get timezone abbreviation (e.g., 'PST', 'EDT')
     * @param {Date} date - The date to get timezone abbreviation for
     * @param {string} timezoneName - IANA timezone name
     * @returns {string} Timezone abbreviation
     */
    function getTimezoneAbbreviation(date, timezoneName) {
        try {
            // Get the formatted string with timezone
            const formatted = date.toLocaleString('en-US', {
                timeZone: timezoneName,
                timeZoneName: 'short'
            });
            
            // Extract timezone abbreviation (last part after last space)
            const parts = formatted.split(' ');
            return parts[parts.length - 1];
        } catch (e) {
            // Fallback to showing timezone abbreviation; return empty string for consistency
            return '';
        }
    }

    /**
     * Format a UTC timestamp to local time with consistent formatting
     * Format: "Dec 3, 2025, 2:30 PM PST"
     * @param {string} utcString - ISO 8601 UTC timestamp (e.g., '2025-12-03T14:30:00Z')
     * @param {string|null} timezoneName - Optional timezone override
     * @returns {string} Formatted timestamp
     */
    function formatTimestamp(utcString, timezoneName = null) {
        if (!utcString) {
            return '—';
        }

        try {
            // Parse the UTC timestamp
            const date = new Date(utcString);
            
            // Check if date is valid
            if (isNaN(date.getTime())) {
                return '—';
            }

            // Use provided timezone or detect automatically
            const tz = timezoneName || detectTimezone();

            // Format the date/time
            const options = {
                timeZone: tz,
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: 'numeric',
                hour12: true
            };

            const formatted = date.toLocaleString('en-US', options);
            
            // Add timezone abbreviation
            const tzAbbr = getTimezoneAbbreviation(date, tz);
            
            return `${formatted} ${tzAbbr}`;
        } catch (e) {
            console.error('Error formatting timestamp:', e);
            return utcString; // Return original on error
        }
    }

    /**
     * Format timestamp as date only
     * Format: "Dec 3, 2025"
     */
    function formatDate(utcString, timezoneName = null) {
        if (!utcString) return '—';
        
        try {
            const date = new Date(utcString);
            if (isNaN(date.getTime())) return '—';
            
            const tz = timezoneName || detectTimezone();
            const options = {
                timeZone: tz,
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            };
            
            return date.toLocaleString('en-US', options);
        } catch (e) {
            console.error('Error formatting date:', e);
            return utcString;
        }
    }

    /**
     * Format timestamp as time only
     * Format: "2:30 PM PST"
     */
    function formatTime(utcString, timezoneName = null) {
        if (!utcString) return '—';
        
        try {
            const date = new Date(utcString);
            if (isNaN(date.getTime())) return '—';
            
            const tz = timezoneName || detectTimezone();
            const options = {
                timeZone: tz,
                hour: 'numeric',
                minute: 'numeric',
                hour12: true
            };
            
            const formatted = date.toLocaleString('en-US', options);
            const tzAbbr = getTimezoneAbbreviation(date, tz);
            
            return `${formatted} ${tzAbbr}`;
        } catch (e) {
            console.error('Error formatting time:', e);
            return utcString;
        }
    }

    /**
     * Convert all elements with class 'local-timestamp' on the page
     * Elements should have data-timestamp attribute with UTC ISO 8601 timestamp
     * Optional data-format attribute: 'date', 'time', or default (full timestamp)
     */
    function convertAllTimestamps() {
        const elements = document.querySelectorAll('.local-timestamp');
        elements.forEach(element => {
            const utcString = element.dataset.timestamp;
            const format = element.dataset.format || 'full';
            
            if (utcString) {
                if (format === 'date') {
                    element.textContent = formatDate(utcString);
                } else if (format === 'time') {
                    element.textContent = formatTime(utcString);
                } else {
                    element.textContent = formatTimestamp(utcString);
                }
            } else {
                element.textContent = '—';
            }
        });
    }

    /**
     * Sync detected timezone to server via /api/set-timezone
     * This stores the timezone in the user's session
     * @returns {Promise<boolean>} Success status
     */
    async function syncTimezoneToServer() {
        try {
            const timezone = detectTimezone();
            
            // Validate timezone before sending to prevent malicious data
            // Check if Intl.supportedValuesOf is available (modern browsers)
            if (typeof Intl.supportedValuesOf === 'function') {
                try {
                    const validTimezones = Intl.supportedValuesOf('timeZone');
                    if (!validTimezones.includes(timezone)) {
                        console.warn('Invalid timezone detected, not syncing to server:', timezone);
                        return false;
                    }
                } catch (e) {
                    // If supportedValuesOf fails, proceed anyway (timezone was already detected successfully)
                    console.debug('Could not validate timezone, proceeding anyway:', e);
                }
            }
            
            const response = await fetch('/api/set-timezone', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ timezone: timezone })
            });

            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success') {
                    console.log(`Timezone synced to server: ${timezone}`);
                    return true;
                }
            }
            
            console.warn('Failed to sync timezone to server');
            return false;
        } catch (e) {
            console.warn('Error syncing timezone to server:', e);
            return false;
        }
    }

    /**
     * Initialize timezone utility
     * - Converts all timestamps on page load
     * - Optionally syncs timezone to server
     */
    function init(options = {}) {
        const { syncToServer = false } = options;

        // Convert timestamps on DOM ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', convertAllTimestamps);
        } else {
            convertAllTimestamps();
        }

        // Optionally sync timezone to server
        if (syncToServer) {
            syncTimezoneToServer();
        }
    }

    // Expose public API
    window.TimezoneUtils = {
        detectTimezone: detectTimezone,
        formatTimestamp: formatTimestamp,
        formatDate: formatDate,
        formatTime: formatTime,
        convertAllTimestamps: convertAllTimestamps,
        syncTimezoneToServer: syncTimezoneToServer,
        init: init
    };

    // Auto-initialize with default options
    init({ syncToServer: true });
})();
