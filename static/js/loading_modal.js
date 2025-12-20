(function(window) {
  function initLoadingModal(tips, options) {
    if (!Array.isArray(tips) || tips.length === 0) {
      return;
    }

    const settings = Object.assign({
      formId: 'loginForm',
      modalId: 'loadingTipsModal',
      tipTextId: 'tipText',
      minimumDisplayTime: 2500,
      rotationInterval: 4000
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

    function showLoadingModal() {
      currentTipIndex = Math.floor(Math.random() * tips.length);
      tipTextElement.textContent = tips[currentTipIndex];

      loadingModal.show();

      tipRotationInterval = setInterval(function() {
        currentTipIndex = (currentTipIndex + 1) % tips.length;
        tipTextElement.textContent = tips[currentTipIndex];
      }, settings.rotationInterval);
    }

    loginForm.addEventListener('submit', function(e) {
      if (formSubmitted) {
        e.preventDefault();
        return;
      }

      e.preventDefault();
      formSubmitted = true;

      showLoadingModal();

      setTimeout(function() {
        loginForm.submit();
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
