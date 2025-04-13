const periodState = {
  a: { seconds: 0, interval: null, active: false, done: false },
  b: { seconds: 0, interval: null, active: false, done: false }
};

function openTapIn(period) {
  if (periodState[period].done) return alert("This period is already closed for the day.");
  document.getElementById('currentPeriod').value = period;
  document.getElementById('tapInPin').value = '';
  new bootstrap.Modal(document.getElementById('tapInModal')).show();
}

function openTapOut(period) {
  if (periodState[period].done) return alert("This period is already closed for the day.");
  document.getElementById('tapOutPeriod').value = period;
  document.getElementById('tapOutPin').value = '';
  document.getElementById('tapOutReason').value = 'restroom';
  new bootstrap.Modal(document.getElementById('tapOutModal')).show();
}

function confirmTapIn() {
  const period = document.getElementById('currentPeriod').value;
  const pin = document.getElementById('tapInPin').value.trim();
  if (!pin) return alert("PIN required.");
  bootstrap.Modal.getInstance(document.getElementById('tapInModal')).hide();

  if (!periodState[period].interval) {
    periodState[period].interval = setInterval(() => {
      if (periodState[period].seconds < 4500) {
        periodState[period].seconds++;
        updateTimerDisplay(period);
      } else {
        clearInterval(periodState[period].interval);
        periodState[period].interval = null;
        alert(`Period ${period.toUpperCase()} time cap reached.`);
      }
    }, 1000);
  }

  periodState[period].active = true;
  document.getElementById(`status-${period}`).textContent = 'Active';
}

function confirmTapOut() {
  const period = document.getElementById('tapOutPeriod').value;
  const reason = document.getElementById('tapOutReason').value;
  const pin = document.getElementById('tapOutPin').value.trim();
  if (!pin) return alert("PIN required.");
  bootstrap.Modal.getInstance(document.getElementById('tapOutModal')).hide();

  if (periodState[period].interval) {
    clearInterval(periodState[period].interval);
    periodState[period].interval = null;
  }

  periodState[period].active = false;
  document.getElementById(`status-${period}`).textContent = 'Inactive';

  if (reason === 'done') {
    periodState[period].done = true;
    console.log(`Period ${period} closed for the day.`);
  } else {
    const timestamp = new Date().toLocaleTimeString();
    console.log(`Hall pass: ${period}, reason: ${reason}, time: ${timestamp}, returned: pending`);
  }
}

function updateTimerDisplay(period) {
  const secs = periodState[period].seconds;
  const min = String(Math.floor(secs / 60)).padStart(2, '0');
  const sec = String(secs % 60).padStart(2, '0');
  document.getElementById(`timer-${period}`).textContent = `${min}:${sec}`;
}
