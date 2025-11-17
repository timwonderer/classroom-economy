

// Helper function for Bootstrap toast messages
function createToast(message, isError = false) {
  const toastContainer = document.getElementById("toast-container");
  if (!toastContainer) return alert(message); // fallback if no toast container

  const toast = document.createElement("div");
  toast.className = `toast align-items-center text-white ${isError ? "bg-danger" : "bg-success"} border-0`;
  toast.role = "alert";
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  toastContainer.appendChild(toast);

  const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
  bsToast.show();
  toast.addEventListener("hidden.bs.toast", () => toast.remove());
}

document.addEventListener("DOMContentLoaded", () => {
    const hallPassModal = new bootstrap.Modal(document.getElementById('hallPassModal'));

    // Handle Tap In and Tap Out button clicks
    document.querySelectorAll(".tap-btn").forEach(button => {
        button.addEventListener("click", () => {
            const period = button.dataset.period;
            const action = button.dataset.action;

            if (action === 'tap_out') {
                // Show the modal for tap out
                document.getElementById('hallPassPeriod').value = period;
                document.getElementById('hallPassForm').reset(); // Clear previous entries
                hallPassModal.show();
            } else {
                // Keep the simple PIN prompt for tap in
                const pin = prompt("Enter your PIN to confirm:");
                if (!pin) return;
                performTap(period, action, pin);
            }
        });
    });

    // Handle the hall pass request from the modal
    document.getElementById('confirmHallPassBtn').addEventListener('click', () => {
        const period = document.getElementById('hallPassPeriod').value;
        const reason = document.getElementById('hallPassReason').value;
        const pin = document.getElementById('hallPassPin').value;
        const action = 'tap_out';

        if (!reason) {
            createToast("Please select a reason.", true);
            return;
        }
        if (!pin) {
            createToast("Please enter your PIN.", true);
            return;
        }

        performTap(period, action, pin, reason);
        hallPassModal.hide();
    });
});

function performTap(period, action, pin, reason = null) {
    const tapButton = document.querySelector(`.tap-btn[data-period='${period}'][data-action='${action}']`);
    if (tapButton) tapButton.disabled = true;

    const payload = { period, action, pin };
    if (reason) {
        payload.reason = reason;
    }

    fetch("/api/tap", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').getAttribute('content') },
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === "ok") {
            updateBlockUI(period, data.active, data.duration, data.projected_pay);
            let message = `Tap ${action === "tap_in" ? "In" : "Out"} successful`;
            if (action === 'tap_out') {
              message = "Hall pass request submitted!";
            }
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
    .then(r => r.json())
    .then(data => {
      Object.keys(data).forEach(period => {
        updateBlockUI(period, data[period].active, data[period].duration, data[period].projected_pay, data[period].hall_pass);
      });
    })
    .catch(err => console.error("Status polling error:", err));
}, 10000);

function updateBlockUI(period, isActive, duration, projectedPay, hallPass = null) {
  const row = document.querySelector(`[data-block-row="${period}"]`);
  if (!row) return;

  const statusCell = row.querySelector(".block-status");
  const durationCell = row.querySelector(".block-duration");
  const payCell = row.querySelector(`.block-pay[data-period="${period}"]`);
  const tapInBtn = row.querySelector(`#tapIn-${period}`);
  const tapOutBtn = row.querySelector(`#tapOut-${period}`);

  statusCell.textContent = isActive ? "Active" : "Inactive";
  statusCell.classList.toggle("text-success", isActive);
  statusCell.classList.toggle("fw-bold", isActive);
  statusCell.classList.toggle("text-muted", !isActive);

  durationCell.textContent = formatDuration(duration);
  if (payCell) {
    payCell.textContent = projectedPay.toFixed(2);
  }

  if (tapInBtn) tapInBtn.disabled = isActive;
  if (tapOutBtn) tapOutBtn.disabled = !isActive;

  // Handle hall pass overlay
  updateHallPassOverlay(period, hallPass);
}

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

    if (hallPass.status === 'pending') {
      passInfoDisplay.innerHTML = `
        <div class="alert alert-warning mb-2">
          <strong>🕐 Hall Pass: Pending Approval</strong><br>
          <small>Destination: ${hallPass.reason}</small><br>
          <button class="btn btn-sm btn-danger mt-1" onclick="cancelHallPass(${hallPass.id}, '${period}')">Cancel</button>
        </div>
      `;
    } else if (hallPass.status === 'approved') {
      passInfoDisplay.innerHTML = `
        <div class="alert alert-success mb-2">
          <strong>✅ Hall Pass Approved!</strong><br>
          <span class="badge bg-success" style="font-size: 1.2rem; letter-spacing: 0.1em;">Pass #${hallPass.pass_number}</span><br>
          <small>Go to terminal to check in</small>
        </div>
      `;
    } else if (hallPass.status === 'left') {
      passInfoDisplay.innerHTML = `
        <div class="alert alert-info mb-2">
          <strong>📍 Currently Out</strong><br>
          <span class="badge bg-info" style="font-size: 1.1rem;">Pass #${hallPass.pass_number}</span><br>
          <small>Destination: ${hallPass.reason}</small>
        </div>
      `;
    } else {
      passInfoDisplay.style.display = 'none';
    }
  }
}

function cancelHallPass(passId, period) {
  if (!confirm('Are you sure you want to cancel this hall pass request?')) {
    return;
  }

  fetch(`/api/hall-pass/cancel/${passId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
    }
  })
  .then(r => r.json())
  .then(data => {
    if (data.status === 'success') {
      createToast('Hall pass request cancelled.');
      // Refresh status immediately
      fetch("/api/student-status")
        .then(r => r.json())
        .then(statusData => {
          updateBlockUI(period, statusData[period].active, statusData[period].duration, statusData[period].projected_pay, statusData[period].hall_pass);
        });
    } else {
      createToast(data.message || 'Failed to cancel request.', true);
    }
  })
  .catch(err => {
    console.error('Cancel error:', err);
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