

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
  document.querySelectorAll(".tap-btn").forEach(button => {
    button.addEventListener("click", () => {
      const period = button.dataset.period;
      const action = button.dataset.action;
      const pin = prompt("Enter your PIN to confirm:");

      if (!pin) return;

      button.disabled = true;
      fetch("/api/tap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period, action, pin })
      })
        .then(r => r.json())
        .then(data => {
          if (data.status === "ok") {
            updateBlockUI(period, data.active, data.duration);
            createToast(`Tap ${action === "tap_in" ? "In" : "Out"} successful`);
          } else {
            createToast("Tap failed: " + (data.error || "Unknown error"), true);
          }
        })
        .catch(err => {
          console.error("Tap error:", err);
          createToast("Network error. Try again.", true);
        })
        .finally(() => {
          button.disabled = false;
        });
    });
  });
});

// Poll the server every 15 seconds to refresh block status
setInterval(() => {
  fetch("/api/student-status")
    .then(r => r.json())
    .then(data => {
      Object.keys(data).forEach(period => {
        updateBlockUI(period, data[period].active, data[period].duration);
      });
    })
    .catch(err => console.error("Status polling error:", err));
}, 15000);

function updateBlockUI(period, isActive, duration) {
  const row = document.querySelector(`[data-block-row="${period}"]`);
  if (!row) return;

  const statusCell = row.querySelector(".block-status");
  const durationCell = row.querySelector(".block-duration");
  const tapInBtn = row.querySelector(`#tapIn-${period}`);
  const tapOutBtn = row.querySelector(`#tapOut-${period}`);

  statusCell.textContent = isActive ? "Active" : "Inactive";
  statusCell.classList.toggle("text-success", isActive);
  statusCell.classList.toggle("fw-bold", isActive);
  statusCell.classList.toggle("text-muted", !isActive);

  durationCell.textContent = formatDuration(duration);

  if (tapInBtn) tapInBtn.disabled = isActive;
  if (tapOutBtn) tapOutBtn.disabled = !isActive;
}

function formatDuration(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}h ${m}m ${s}s`;
}