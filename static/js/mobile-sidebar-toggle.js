/**
 * Mobile Sidebar Toggle with Accessibility Features
 * Handles slide-out navigation for mobile and PWA users
 * 
 * Features:
 * - Smooth slide-out animation
 * - Focus management and trapping
 * - Escape key support
 * - ARIA attribute updates
 * - Responsive viewport handling
 */

(function() {
    'use strict';

    // Breakpoint for desktop layout in pixels (matches CSS media query: 992px)
    const DESKTOP_BREAKPOINT_PX = 992;

    document.addEventListener('DOMContentLoaded', function() {
        // Get elements - works with both admin and student layouts
        const sidebar = document.querySelector('.sidebar, .student-sidebar');
        const backdrop = document.getElementById('sidebarBackdrop');
        const toggle = document.getElementById('mobileMenuToggle');
        
        if (!sidebar || !toggle) {
            return; // Exit if required elements not found
        }

        let previouslyFocusedElement = null;

        /**
         * Trap focus within the sidebar when it's open
         */
        function trapFocus(event) {
            if (!sidebar.contains(event.target) && event.target !== toggle) {
                event.preventDefault();
                const focusableElements = getFocusableElements();
                if (focusableElements.length > 0) {
                    focusableElements[0].focus();
                }
            }
        }

        /**
         * Get all focusable elements within the sidebar
         */
        function getFocusableElements() {
            const focusableSelector = [
                'a[href]',
                'button:not([disabled])',
                'input:not([disabled])',
                'select:not([disabled])',
                'textarea:not([disabled])',
                '[tabindex]:not([tabindex="-1"])'
            ].join(', ');
            
            return Array.from(sidebar.querySelectorAll(focusableSelector));
        }

        /**
         * Handle Escape key to close sidebar
         */
        function handleKeydown(event) {
            if (event.key === 'Escape' || event.key === 'Esc') {
                if (sidebar.classList.contains('show')) {
                    closeSidebar();
                }
            }
        }

        /**
         * Open the sidebar with accessibility features
         */
        function openSidebar() {
            // Store currently focused element
            previouslyFocusedElement = document.activeElement instanceof HTMLElement 
                ? document.activeElement 
                : null;

            // Show sidebar and backdrop
            sidebar.classList.add('show');
            sidebar.removeAttribute('inert');
            backdrop?.classList.add('show');
            document.body.style.overflow = 'hidden';

            // Update ARIA attributes
            toggle.setAttribute('aria-expanded', 'true');
            sidebar.setAttribute('aria-hidden', 'false');
            if (backdrop) {
                backdrop.setAttribute('aria-hidden', 'false');
            }

            // Move focus to sidebar
            const focusableElements = getFocusableElements();
            if (focusableElements.length > 0) {
                focusableElements[0].focus();
            } else {
                // If no focusable elements, make sidebar itself focusable
                if (!sidebar.hasAttribute('tabindex')) {
                    sidebar.setAttribute('tabindex', '-1');
                }
                sidebar.focus();
            }

            // Add event listeners
            document.addEventListener('keydown', handleKeydown);
            document.addEventListener('focusin', trapFocus);
        }

        /**
         * Close the sidebar and restore focus
         */
        function closeSidebar() {
            // Hide sidebar and backdrop
            sidebar.classList.remove('show');
            sidebar.setAttribute('inert', '');
            backdrop?.classList.remove('show');
            document.body.style.overflow = '';

            // Update ARIA attributes
            toggle.setAttribute('aria-expanded', 'false');
            sidebar.setAttribute('aria-hidden', 'true');
            if (backdrop) {
                backdrop.setAttribute('aria-hidden', 'true');
            }

            // Remove event listeners
            document.removeEventListener('keydown', handleKeydown);
            document.removeEventListener('focusin', trapFocus);

            // Restore focus
            if (previouslyFocusedElement && typeof previouslyFocusedElement.focus === 'function') {
                previouslyFocusedElement.focus();
            } else {
                toggle.focus();
            }
            previouslyFocusedElement = null;
        }

        /**
         * Attach click handlers to sidebar links for mobile
         */
        function attachMobileSidebarLinkHandlers() {
            if (!sidebar) return;
            
            const sidebarLinks = sidebar.querySelectorAll('a[href], a.nav-link');
            sidebarLinks.forEach(link => {
                // Remove first to avoid duplicates
                link.removeEventListener('click', closeSidebar);
                link.addEventListener('click', closeSidebar);
            });
        }

        /**
         * Remove click handlers from sidebar links
         */
        function detachMobileSidebarLinkHandlers() {
            if (!sidebar) return;
            
            const sidebarLinks = sidebar.querySelectorAll('a[href], a.nav-link');
            sidebarLinks.forEach(link => {
                link.removeEventListener('click', closeSidebar);
            });
        }

        /**
         * Handle viewport changes between mobile and desktop
         */
        function handleViewportChange(event) {
            if (event.matches) {
                // Mobile view - attach handlers
                attachMobileSidebarLinkHandlers();
            } else {
                // Desktop view - detach handlers and close sidebar if open
                detachMobileSidebarLinkHandlers();
                if (sidebar.classList.contains('show')) {
                    closeSidebar();
                }
            }
        }

        // Set up toggle button
        toggle.addEventListener('click', function() {
            if (sidebar.classList.contains('show')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });

        // Set up backdrop click
        backdrop?.addEventListener('click', closeSidebar);

        // Set up responsive viewport handling
        // Keep behavior aligned with the shell CSS: the sidebar becomes a
        // slide-out navigation below the 992px desktop breakpoint.
        const mobileMediaQuery = window.matchMedia('(max-width: 991.98px)');
        
        // Initial setup
        if (mobileMediaQuery.matches) {
            attachMobileSidebarLinkHandlers();
        }

        // Listen for viewport changes
        if (typeof mobileMediaQuery.addEventListener === 'function') {
            mobileMediaQuery.addEventListener('change', handleViewportChange);
        } else if (typeof mobileMediaQuery.addListener === 'function') {
            // Fallback for older browsers
            mobileMediaQuery.addListener(handleViewportChange);
        }

        // Initialize ARIA attributes based on viewport
        toggle.setAttribute('aria-expanded', 'false');
        
        // Set aria-hidden based on viewport: only hide on mobile (matches CSS breakpoint)
        const desktopMediaQuery = window.matchMedia(`(min-width: ${DESKTOP_BREAKPOINT_PX}px)`);
        if (desktopMediaQuery.matches) {
            // Desktop: sidebar always visible, so not hidden from screen readers
            sidebar.removeAttribute('aria-hidden');
            sidebar.removeAttribute('inert');
        } else {
            // Mobile: sidebar hidden by default
            sidebar.setAttribute('aria-hidden', 'true');
            sidebar.setAttribute('inert', '');
        }
        
        if (backdrop) {
            backdrop.setAttribute('aria-hidden', 'true');
        }
        
        // Update aria-hidden on viewport resize
        const updateSidebarAriaOnResize = (e) => {
            if (e.matches) {
                // Desktop: sidebar visible
                sidebar.removeAttribute('aria-hidden');
                sidebar.removeAttribute('inert');
                // If sidebar was open on mobile, close it
                if (sidebar.classList.contains('show')) {
                    closeSidebar();
                }
            } else {
                // Mobile: sidebar hidden unless explicitly shown
                if (!sidebar.classList.contains('show')) {
                    sidebar.setAttribute('aria-hidden', 'true');
                    sidebar.setAttribute('inert', '');
                }
            }
        };
        
        if (typeof desktopMediaQuery.addEventListener === 'function') {
            desktopMediaQuery.addEventListener('change', updateSidebarAriaOnResize);
        } else if (typeof desktopMediaQuery.addListener === 'function') {
            desktopMediaQuery.addListener(updateSidebarAriaOnResize);
        }
    });
})();
