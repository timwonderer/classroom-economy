function initializePasskeyLogin(buttonId, startUrl, finishUrl, dashboardUrl) {
    const passkeyButton = document.getElementById(buttonId);
    if (!passkeyButton) return;

    passkeyButton.addEventListener('click', async function() {
        const button = this;
        const originalText = button.innerHTML;

        try {
            button.disabled = true;
            button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Authenticating...';

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
            if (!csrfToken) {
                throw new Error('CSRF token not found or is empty. Please refresh the page and try again.');
            }

            const usernameInput = document.querySelector('input[name="username"]');
            if (!usernameInput || !usernameInput.value.trim()) {
                throw new Error('Please enter your username first');
            }
            const username = usernameInput.value.trim();

            const startResponse = await fetch(startUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ username: username })
            });

            if (!startResponse.ok) {
                let error = {};
                try {
                    error = await startResponse.json();
                } catch (e) {
                    // Non-JSON response; proceed with generic error
                }
                throw new Error(error.error || 'Failed to start authentication');
            }

            const { apiKey } = await startResponse.json();

            if (typeof Passwordless === 'undefined') {
                throw new Error('Passkey library failed to load. Please refresh the page and try again. If the problem persists, try clearing your browser cache.');
            }

            const p = new Passwordless.Client({ apiKey: apiKey });
            const { token, error } = await p.signinWithAlias(username);

            if (error) {
                console.error('Passwordless.dev error:', error);
                throw new Error(error.title || 'Authentication failed');
            }

            if (!token) {
                throw new Error('Authentication was cancelled or failed');
            }

            const finishResponse = await fetch(finishUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ token: token })
            });

            if (!finishResponse.ok) {
                let error = {};
                try {
                    error = await finishResponse.json();
                } catch (e) {
                    // Non-JSON response; proceed with generic error
                }
                throw new Error(error.error || 'Authentication failed');
            }

            const result = await finishResponse.json();
            window.location.href = result.redirect || dashboardUrl;
        } catch (error) {
            console.error('Passkey authentication error:', error);

            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger border-0 shadow-sm mb-4';
            errorDiv.textContent = error.message || 'Passkey authentication failed. Please try again or use TOTP.';

            const form = document.querySelector('form');
            if (form) {
                form.parentNode.insertBefore(errorDiv, form);
                setTimeout(() => errorDiv.remove(), 5000);
            }

            button.disabled = false;
            button.innerHTML = originalText;
        }
    });
}

function initializeAuthMethodSwitch({ authContainerId, totpContainerId, authenticatorButtonId, backButtonId, totpInputId }) {
    const authContainer = document.getElementById(authContainerId);
    const totpContainer = document.getElementById(totpContainerId);
    const authenticatorButton = document.getElementById(authenticatorButtonId);
    const backButton = document.getElementById(backButtonId);
    const totpInput = totpInputId ? document.getElementById(totpInputId) : null;

    if (!authContainer || !totpContainer) return;

    authenticatorButton?.addEventListener('click', () => {
        authContainer.style.display = 'none';
        totpContainer.style.display = 'block';
        totpInput?.focus();
    });

    backButton?.addEventListener('click', () => {
        totpContainer.style.display = 'none';
        authContainer.style.display = 'block';
        if (totpInput) {
            totpInput.value = '';
        }
    });
}

function setupPasskeyAuthFlow({
    buttonId,
    usernameFieldId,
    startUrl,
    finishUrl,
    dashboardUrl,
    useCsrf = false,
    authContainerId,
    totpContainerId,
    errorContainerId
}) {
    const passkeyButton = document.getElementById(buttonId);
    const usernameField = document.getElementById(usernameFieldId);
    const authContainer = document.getElementById(authContainerId);
    const totpContainer = document.getElementById(totpContainerId);
    const errorContainer = document.getElementById(errorContainerId);

    if (!passkeyButton || !usernameField) return;

    const showError = (message) => {
        if (!errorContainer) return;
        errorContainer.textContent = message;
        errorContainer.classList.remove('d-none');
    };

    const clearError = () => {
        if (!errorContainer) return;
        errorContainer.classList.add('d-none');
        errorContainer.textContent = '';
    };

    passkeyButton.addEventListener('click', async () => {
        clearError();

        const username = usernameField.value.trim();
        if (!username) {
            showError('Please enter your username first');
            usernameField.focus();
            return;
        }

        const originalContent = passkeyButton.innerHTML;
        passkeyButton.disabled = true;
        passkeyButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Authenticating...';

        const headers = { 'Content-Type': 'application/json' };
        const csrfToken = document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content');
        if (useCsrf && csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        try {
            const startResponse = await fetch(startUrl, {
                method: 'POST',
                headers,
            });

            const options = await startResponse.json();
            if (!startResponse.ok || options.error) {
                throw new Error(options.error || 'Failed to start authentication');
            }

            if (typeof Passwordless === 'undefined') {
                throw new Error('Passkey library failed to load. Please refresh the page and try again.');
            }

            const client = new Passwordless.Client({ apiUrl: 'https://v4.passwordless.dev' });
            const token = await client.signinWithDiscoverable(options);

            if (!token) {
                throw new Error('Authentication was cancelled or failed');
            }

            const finishResponse = await fetch(finishUrl, {
                method: 'POST',
                headers,
                body: JSON.stringify({ token })
            });

            const result = await finishResponse.json();
            if (!finishResponse.ok || !result.success) {
                throw new Error(result.error || 'Authentication failed');
            }

            window.location.href = dashboardUrl;
        } catch (error) {
            console.error('Passkey authentication error:', error);
            showError(error.message || 'Passkey authentication failed. Please try again or use TOTP.');

            if (authContainer && totpContainer) {
                authContainer.style.display = 'none';
                totpContainer.style.display = 'block';
                const totpInput = totpContainer.querySelector('input');
                totpInput?.focus();
            }
        } finally {
            passkeyButton.disabled = false;
            passkeyButton.innerHTML = originalContent;
        }
    });
}
