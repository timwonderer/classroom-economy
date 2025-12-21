(function(window) {
  function initLoadingModal(userType, options) {
    const settings = Object.assign({
      formId: 'loginForm',
      modalId: 'loadingTipsModal',
      tipTextId: 'tipText',
      minimumDisplayTime: 2500,
      rotationInterval: 4000,
      tipsApiUrl: '/api/tips/' + userType
    }, options || {});

    const loginForm = document.getElementById(settings.formId);
    const modalElement = document.getElementById(settings.modalId);
    const tipTextElement = document.getElementById(settings.tipTextId);

    if (!loginForm || !modalElement || !tipTextElement) {
      return;
    }

    const loadingModal = new bootstrap.Modal(modalElement);
    let currentTipIndex = 0;
    let tipRotationInterval;
    let formSubmitted = false;
    let tips = [];

    // Fetch tips from API
    fetch(settings.tipsApiUrl)
      .then(function(response) {
        if (!response.ok) {
          throw new Error('Failed to fetch tips');
        }
        return response.json();
      })
      .then(function(data) {
        if (data.tips && Array.isArray(data.tips) && data.tips.length > 0) {
          tips = data.tips;
        }
      })
      .catch(function(error) {
        console.error('Error fetching tips:', error);
        // Fallback to a default tip if fetch fails
        tips = ['Loading...'];
      });

    function showLoadingModal() {
      // Use default message if tips haven't loaded yet
      if (tips.length === 0) {
        tipTextElement.textContent = 'Loading...';
      } else {
        currentTipIndex = Math.floor(Math.random() * tips.length);
        tipTextElement.textContent = tips[currentTipIndex];
      }

      loadingModal.show();

      // Only rotate tips if we have them loaded
      if (tips.length > 0) {
        tipRotationInterval = setInterval(function() {
          currentTipIndex = (currentTipIndex + 1) % tips.length;
          tipTextElement.textContent = tips[currentTipIndex];
        }, settings.rotationInterval);
      }
    }

    loginForm.addEventListener('submit', function(e) {
      if (formSubmitted) {
        e.preventDefault();
        return;
      }

      e.preventDefault();

      if (typeof loginForm.reportValidity === 'function' && !loginForm.reportValidity()) {
        return;
      }

      formSubmitted = true;
      showLoadingModal();

      setTimeout(function() {
        // Use prototype to avoid conflict with form field named "submit"
        HTMLFormElement.prototype.submit.call(loginForm);
      }, settings.minimumDisplayTime);
    });

    window.addEventListener('beforeunload', function() {
      if (tipRotationInterval) {
        clearInterval(tipRotationInterval);
      }
    });
  }

  window.initLoadingModal = initLoadingModal;
})(window);
