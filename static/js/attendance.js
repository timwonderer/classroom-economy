

// Helper function for Bootstrap toast messages
function createToast(message, isError = false) {
  window.AppCore.toast(message, isError ? "error" : "success");
}

document.addEventListener("DOMContentLoaded", () => {
  // Apply initial server-rendered state (for hall passes + timers) before polling kicks in
  const serverStateEl = document.getElementById('serverState');
  if (serverStateEl && serverStateEl.textContent) {
    try {
      const initialState = JSON.parse(serverStateEl.textContent);
      Object.entries(initialState || {}).forEach(([period, state]) => {
        updateBlockUI(
          period,
          state.active,
          state.duration,
          state.projected_pay,
          state.hall_pass
        );
      });
    } catch (e) {
      console.error('Failed to parse initial attendance state', e);
    }
  }

  // Handle contextual productivity actions.
  document.querySelectorAll(".attendance-action-btn").forEach(button => {
    button.addEventListener("click", () => {
      const period = button.dataset.period;
      const action = button.dataset.action;

      if (action === 'start_work') {
        const pin = prompt("Enter your PIN to Start Work:");
        if (!pin) return;
        performTap(period, action, pin);
        return;
      }

      if (action === 'break') {
        const buttonState = button.dataset.state || 'break';
        const state = getPeriodState(period);
        const hallPass = state ? state.hall_pass : null;
        if (buttonState === 'leave' && hallPass && hallPass.status === 'approved') {
          checkOutHallPass(hallPass.id, period);
          return;
        }
        if (buttonState === 'return' && hallPass && hallPass.status === 'left') {
          checkInHallPass(hallPass.id, period);
          return;
        }
        if (buttonState === 'pending') {
          createToast("Your hall pass request is pending approval.", true);
          return;
        }
        openBreakChoiceModal(period);
        return;
      }
    });
  });
});

const periodStateCache = {};
let selectedBreakPeriod = null;

function rememberPeriodState(period, state) {
  periodStateCache[period] = state || {};
}

function getPeriodState(period) {
  return periodStateCache[period] || {};
}

function performTap(period, action, pin, reason = null) {
  const tapButton = document.querySelector(`.attendance-action-btn[data-period='${period}'][data-action='${action}']`);
  if (tapButton) tapButton.disabled = true;

  // Map old action names to new API values
  let apiAction = action;
  if (action === 'break') apiAction = 'stop_work';

  const payload = { period, action: apiAction, pin };
  if (reason) {
    payload.reason = reason;
  }

  window.AppCore.csrfFetch("/api/tap", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(r => {
      // If session expired, redirect to login
      if (r.status === 401) {
        window.location.href = '/student/login?session_expired=1';
        return null;
      }
      return r.json();
    })
    .then(data => {
      if (!data) return; // Session expired, already redirecting
      if (data.status === "ok") {
        const state = { active: data.active, duration: data.duration, projected_pay: data.projected_pay, hall_pass: data.hall_pass };
        rememberPeriodState(period, state);
        updateBlockUI(period, state.active, state.duration, state.projected_pay, state.hall_pass);
        let message = `${action === "start_work" ? "Start Work" : "Break"} successful`;
        createToast(message);
      } else {
        createToast("Request failed: " + (data.error || "Unknown error"), true);
      }
      // The UI update function will correctly set the button states.
    })
    .catch(err => {
      console.error("Tap error:", err);
      createToast("Network error. Try again.", true);
      if (tapButton) tapButton.disabled = false; // Re-enable on error
    });
}

// Poll the server every 10 seconds to refresh block status
setInterval(() => {
  fetch("/api/student-status")
    .then(r => {
      // If session expired, redirect to login
      if (r.status === 401) {
        window.location.href = '/student/login?session_expired=1';
        return null;
      }
      return r.json();
    })
    .then(data => {
      if (!data) return; // Session expired, already redirecting
      if (data.status === 'ok' && data.periods) {
        Object.keys(data.periods).forEach(period => {
          const periodData = data.periods[period];
          rememberPeriodState(period, periodData);
          updateBlockUI(period, periodData.active, periodData.duration, periodData.projected_pay, periodData.hall_pass);
        });
      }
    })
    .catch(err => console.error("Status polling error:", err));

}, 10000);

function updateBlockUI(period, isActive, duration, projectedPay, hallPass = null) {
  const row = document.querySelector(`[data-block-row="${period}"]`);
  if (!row) return;

  const statusCell = row.querySelector(".block-status");
  const durationCell = row.querySelector(".block-duration");
  const payCell = row.querySelector(`.block-pay[data-period="${period}"]`);
  const startWorkBtn = row.querySelector(`#startWork-${period}`);
  const breakWorkBtn = row.querySelector(`#breakWork-${period}`);

  rememberPeriodState(period, { active: isActive, duration, projected_pay: projectedPay, hall_pass: hallPass });

  statusCell.textContent = isActive ? "Active" : "Inactive";
  statusCell.classList.toggle("text-success", isActive);
  statusCell.classList.toggle("fw-bold", isActive);
  statusCell.classList.toggle("text-muted", !isActive);

  durationCell.textContent = formatDuration(duration);
  if (payCell) {
    payCell.textContent = projectedPay.toFixed(2);
  }

  if (startWorkBtn) startWorkBtn.disabled = isActive;
  configureBreakButton(breakWorkBtn, isActive, hallPass);

  // Handle hall pass overlay
  updateHallPassOverlay(period, hallPass);
}

function configureBreakButton(button, isActive, hallPass) {
  if (!button) return;
  button.disabled = !isActive;
  button.classList.remove('btn-warning', 'btn-danger', 'btn-primary', 'btn-outline-warning');

  if (!isActive) {
    button.dataset.state = 'break';
    button.classList.add('btn-warning');
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1">pause_circle</span> Break';
    return;
  }

  if (hallPass && hallPass.status === 'approved') {
    button.dataset.state = 'leave';
    button.classList.add('btn-danger');
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1">logout</span> Leave';
    return;
  }

  if (hallPass && hallPass.status === 'left') {
    button.dataset.state = 'return';
    button.classList.add('btn-primary');
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1">login</span> Return';
    return;
  }

  if (hallPass && hallPass.status === 'pending') {
    button.dataset.state = 'pending';
    button.classList.add('btn-outline-warning');
    button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1">hourglass_top</span> Pending';
    return;
  }

  button.dataset.state = 'break';
  button.classList.add('btn-warning');
  button.innerHTML = '<span class="material-symbols-outlined align-bottom me-1">pause_circle</span> Break';
}

function openBreakChoiceModal(period) {
  selectedBreakPeriod = period;
  renderBreakDestinations([]);

  const modalEl = document.getElementById('breakChoiceModal');
  if (modalEl && window.bootstrap) {
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }

  fetch('/api/hall-pass/available-types')
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        renderBreakDestinations(data.pass_types || []);
      } else {
        renderBreakDestinationError(data.message || 'Unable to load hall-pass destinations.');
      }
    })
    .catch(err => {
      console.error('Hall pass destination load error:', err);
      renderBreakDestinationError('Unable to load hall-pass destinations.');
    });
}

function closeBreakChoiceModal() {
  const modalEl = document.getElementById('breakChoiceModal');
  if (modalEl && window.bootstrap) {
    bootstrap.Modal.getOrCreateInstance(modalEl).hide();
  }
}

function renderBreakDestinations(passTypes) {
  const list = document.getElementById('hallPassDestinationList');
  if (!list) return;
  list.textContent = '';

  if (!Array.isArray(passTypes) || passTypes.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'text-muted small';
    empty.textContent = 'No hall-pass destinations are currently available.';
    list.appendChild(empty);
    return;
  }

  passTypes.forEach(passType => {
    const destination = (passType && passType.name) ? String(passType.name) : '';
    if (!destination) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-outline-primary text-start';
    button.textContent = destination;
    button.addEventListener('click', () => {
      if (!selectedBreakPeriod) return;
      requestHallPass(selectedBreakPeriod, destination);
      closeBreakChoiceModal();
    });
    list.appendChild(button);
  });
}

function renderBreakDestinationError(message) {
  const list = document.getElementById('hallPassDestinationList');
  if (!list) return;
  list.textContent = '';
  const alert = document.createElement('div');
  alert.className = 'alert alert-danger mb-0';
  alert.textContent = message;
  list.appendChild(alert);
}

document.addEventListener('DOMContentLoaded', () => {
  const doneBtn = document.getElementById('doneForDayBreakBtn');
  if (!doneBtn) return;
  doneBtn.addEventListener('click', () => {
    if (!selectedBreakPeriod) return;
    const pin = prompt("Enter your PIN to mark done for the day:");
    if (!pin) return;
    closeBreakChoiceModal();
    performTap(selectedBreakPeriod, 'break', pin, "Done for the day");
  });
});

function updateHallPassOverlay(period, hallPass) {
  const passInfoDisplay = document.getElementById(`hallPassInfo-${period}`);

  if (!hallPass || hallPass.status === 'returned') {
    // No active hall pass - hide pass info
    if (passInfoDisplay) passInfoDisplay.style.display = 'none';
    return;
  }

  // Show pass info inline based on status
  if (passInfoDisplay) {
    passInfoDisplay.style.display = 'block';
    passInfoDisplay.textContent = ''; // Clear existing content

    const buildStatusLabel = (iconClass, text) => {
      const strong = document.createElement('strong');
      const icon = document.createElement('i');
      icon.className = `bi ${iconClass} me-1`;
      icon.setAttribute('aria-hidden', 'true');
      strong.appendChild(icon);
      strong.appendChild(document.createTextNode(text));
      return strong;
    };

    if (hallPass.status === 'pending') {
      const alertDiv = document.createElement('div');
      alertDiv.className = 'alert alert-warning mb-2';

      alertDiv.appendChild(buildStatusLabel('bi-hourglass-split', 'Hall Pass: Pending Approval'));
      alertDiv.appendChild(document.createElement('br'));

      const small = document.createElement('small');
      small.textContent = 'Destination: ' + (hallPass.reason || 'N/A');
      alertDiv.appendChild(small);
      alertDiv.appendChild(document.createElement('br'));

      const button = document.createElement('button');
      button.className = 'btn btn-sm btn-danger mt-1';
      button.textContent = 'Cancel';
      button.onclick = function () { cancelHallPass(hallPass.id, period); };
      alertDiv.appendChild(button);

      passInfoDisplay.appendChild(alertDiv);
    } else if (hallPass.status === 'approved') {
      const alertDiv = document.createElement('div');
      alertDiv.className = 'alert alert-success mb-2';

      alertDiv.appendChild(buildStatusLabel('bi-check-circle-fill', 'Hall Pass Approved!'));
      alertDiv.appendChild(document.createElement('br'));

      const small = document.createElement('small');
      small.textContent = 'Destination: ' + (hallPass.reason || 'N/A');
      alertDiv.appendChild(small);
      alertDiv.appendChild(document.createElement('br'));

      passInfoDisplay.appendChild(alertDiv);
    } else if (hallPass.status === 'left') {
      const alertDiv = document.createElement('div');
      alertDiv.className = 'alert alert-info mb-2';

      alertDiv.appendChild(buildStatusLabel('bi-geo-alt-fill', 'Currently Out'));
      alertDiv.appendChild(document.createElement('br'));

      const small = document.createElement('small');
      small.textContent = 'Destination: ' + (hallPass.reason || 'N/A');
      alertDiv.appendChild(small);
      alertDiv.appendChild(document.createElement('br'));

      passInfoDisplay.appendChild(alertDiv);
    } else if (hallPass.status === 'rejected') {
      const alertDiv = document.createElement('div');
      alertDiv.className = 'alert alert-danger mb-2';

      alertDiv.appendChild(buildStatusLabel('bi-x-circle-fill', 'Hall Pass Denied'));
      alertDiv.appendChild(document.createElement('br'));

      const small = document.createElement('small');
      small.textContent = 'Reason: ' + (hallPass.reason || 'N/A');
      alertDiv.appendChild(small);

      passInfoDisplay.appendChild(alertDiv);
    } else {
      passInfoDisplay.style.display = 'none';
    }
  }
}

function refreshUi(period) {
  fetch("/api/student-status")
    .then(r => r.json())
    .then(statusData => {
      if (statusData.status === 'ok' && statusData.periods && statusData.periods[period]) {
        const periodData = statusData.periods[period];
        rememberPeriodState(period, periodData);
        updateBlockUI(period, periodData.active, periodData.duration, periodData.projected_pay, periodData.hall_pass);
      }
    });
}

function cancelHallPass(passId, period) {
  if (!confirm('Are you sure you want to cancel this hall pass request?')) {
    return;
  }

  window.AppCore.csrfFetch(`/api/hall-pass/request/${passId}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        createToast('Hall pass request cancelled.');
        refreshUi(period);
      } else {
        createToast(data.message || 'Failed to cancel request.', true);
      }
    })
    .catch(err => {
      console.error('Cancel error:', err);
      createToast('Network error. Try again.', true);
    });
}

function requestHallPass(period, destination) {
  if (!destination || !destination.trim()) {
    return;
  }

  window.AppCore.csrfFetch('/api/hall-pass/request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ destination: destination.trim() })
  })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        createToast('Hall pass request sent.');
        refreshUi(period, true);
      } else {
        createToast(data.message || 'Failed to request hall pass.', true);
      }
    })
    .catch(err => {
      console.error('Hall pass request error:', err);
      createToast('Network error. Try again.', true);
    });
}

function checkOutHallPass(passId, period) {
  if (!confirm('Ready to check out? This will mark you as leaving the classroom.')) {
    return;
  }

  window.AppCore.csrfFetch('/api/hall-pass/checkout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pass_id: passId })
  })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        createToast(`Checked out for ${data.destination}. Have a safe trip!`);
        refreshUi(period, true);
      } else {
        createToast(data.message || 'Failed to check out.', true);
      }
    })
    .catch(err => {
      console.error('Checkout error:', err);
      createToast('Network error. Try again.', true);
    });
}

function checkInHallPass(passId, period) {
  if (!confirm('Ready to check in? This will mark you as returned to class.')) {
    return;
  }

  window.AppCore.csrfFetch('/api/hall-pass/checkin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pass_id: passId })
  })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        createToast('Welcome back! You have been checked in.');
        refreshUi(period, true);
      } else {
        createToast(data.message || 'Failed to check in.', true);
      }
    })
    .catch(err => {
      console.error('Checkin error:', err);
      createToast('Network error. Try again.', true);
    });
}

// Removed acknowledgeApproval - no longer needed with inline display

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}h ${m}m ${s}s`;
}
