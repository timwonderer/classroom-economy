/**
 * Passwordless.dev Frontend Integration
 * Official JavaScript SDK Implementation
 * https://docs.passwordless.dev/guide/frontend/javascript.html
 */

/**
 * Register a new passkey
 * Official SDK Pattern: Get token from backend → call p.register(token)
 */
async function registerPasskey(startUrl, finishUrl, authenticatorName) {
    try {
        // Step 1: Get registration token from backend
        const startResponse = await fetch(startUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        });

        if (!startResponse.ok) {
            const error = await startResponse.json();
            throw new Error(error.error || 'Failed to start registration');
        }

        const { token, apiKey } = await startResponse.json();

        // Step 2: Initialize Passwordless.dev client (Official SDK)
        const p = new Passwordless.Client({ apiKey });

        // Step 3: Perform WebAuthn registration (Official SDK)
        const result = await p.register(token);

        if (!result || result.error) {
            throw new Error(result?.error || 'Registration failed');
        }

        // Step 4: Send registration result to backend
        const finishResponse = await fetch(finishUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                token: result.token,
                authenticatorName: authenticatorName
            })
        });

        if (!finishResponse.ok) {
            const error = await finishResponse.json();
            throw new Error(error.error || 'Failed to save passkey');
        }

        return { success: true };

    } catch (error) {
        console.error('Passkey registration error:', error);
        throw error;
    }
}

/**
 * Sign in with passkey
 * Official SDK Pattern: call p.signinWithAlias(username) → send token to backend
 */
async function signinWithPasskey(username, startUrl, finishUrl) {
    try {
        // Step 1: Get public API key from backend
        const startResponse = await fetch(startUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ username })
        });

        if (!startResponse.ok) {
            const error = await startResponse.json();
            throw new Error(error.error || 'Authentication failed');
        }

        const { apiKey } = await startResponse.json();

        // Step 2: Initialize Passwordless.dev client (Official SDK)
        const p = new Passwordless.Client({ apiKey });

        // Step 3: Perform WebAuthn authentication (Official SDK)
        const result = await p.signinWithAlias(username);

        if (!result || result.error) {
            throw new Error(result?.error || 'Authentication failed');
        }

        // Step 4: Send authentication token to backend for verification
        const finishResponse = await fetch(finishUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                token: result.token
            })
        });

        if (!finishResponse.ok) {
            const error = await finishResponse.json();
            throw new Error(error.error || 'Authentication failed');
        }

        const finishData = await finishResponse.json();
        return finishData;

    } catch (error) {
        console.error('Passkey signin error:', error);
        throw error;
    }
}

/**
 * Sign in with discoverable credential (no username required)
 * Official SDK Pattern: call p.signinWithDiscoverable()
 */
async function signinWithDiscoverable(finishUrl) {
    try {
        // For discoverable signin, we need the public API key
        // This should be provided in the page or fetched first
        const apiKey = window.PASSWORDLESS_PUBLIC_KEY;
        if (!apiKey) {
            throw new Error('Public API key not configured');
        }

        // Initialize Passwordless.dev client (Official SDK)
        const p = new Passwordless.Client({ apiKey });

        // Perform WebAuthn authentication with discoverable credential
        const result = await p.signinWithDiscoverable();

        if (!result || result.error) {
            throw new Error(result?.error || 'Authentication failed');
        }

        // Send authentication token to backend for verification
        const finishResponse = await fetch(finishUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                token: result.token
            })
        });

        if (!finishResponse.ok) {
            const error = await finishResponse.json();
            throw new Error(error.error || 'Authentication failed');
        }

        const finishData = await finishResponse.json();
        return finishData;

    } catch (error) {
        console.error('Passkey discoverable signin error:', error);
        throw error;
    }
}

/**
 * Get CSRF token from meta tag
 */
function getCsrfToken() {
    const token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.getAttribute('content') : '';
}

/**
 * Setup passkey registration button
 */
function setupPasskeyRegistration(config) {
    const button = document.getElementById(config.buttonId);
    if (!button) return;

    button.addEventListener('click', async function() {
        const originalHTML = this.innerHTML;
        const authenticatorName = config.authenticatorName || prompt('Name this passkey (e.g., "YubiKey", "Touch ID"):');

        if (!authenticatorName) {
            window.AppCore?.toast('Name is required.', 'error');
            return;
        }

        try {
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Registering...';

            await registerPasskey(config.startUrl, config.finishUrl, authenticatorName);

            // Success - reload page
            window.location.reload();

        } catch (error) {
            window.AppCore?.toast('Error: ' + error.message, 'error');
            this.disabled = false;
            this.innerHTML = originalHTML;
        }
    });
}

/**
 * Setup passkey signin button
 */
function setupPasskeySignin(config) {
    const button = document.getElementById(config.buttonId);
    const usernameField = document.getElementById(config.usernameFieldId);

    if (!button || !usernameField) return;

    button.addEventListener('click', async function() {
        const username = usernameField.value.trim();

        if (!username) {
            window.AppCore?.toast('Please enter your username.', 'error');
            return;
        }

        const originalHTML = this.innerHTML;

        try {
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Authenticating...';

            const result = await signinWithPasskey(username, config.startUrl, config.finishUrl);

            if (result.success && result.redirect) {
                window.location.href = result.redirect;
            }

        } catch (error) {
            window.AppCore?.toast('Error: ' + error.message, 'error');
            this.disabled = false;
            this.innerHTML = originalHTML;
        }
    });
}
