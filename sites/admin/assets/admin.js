const apiBase = 'https://api.tajvpn.com';
const tokenKey = 'tajvpn_admin_token';

const tokenInput = document.getElementById('token-input');
const saveTokenButton = document.getElementById('save-token-button');
const refreshButton = document.getElementById('refresh-button');
const loginStatus = document.getElementById('login-status');
const paymentsBody = document.getElementById('payments-body');
const devicesBody = document.getElementById('devices-body');
const statsGrid = document.getElementById('stats-grid');

tokenInput.value = localStorage.getItem(tokenKey) || '';

saveTokenButton.addEventListener('click', () => {
  const token = tokenInput.value.trim();
  if (!token) {
    loginStatus.textContent = 'Введи ADMIN_TOKEN из backend/.env.';
    return;
  }

  localStorage.setItem(tokenKey, token);
  loginStatus.textContent = 'Токен сохранен локально. Загружаем данные...';
  loadDashboard();
});

refreshButton.addEventListener('click', () => {
  loadDashboard();
});

async function loadDashboard() {
  const token = localStorage.getItem(tokenKey);
  if (!token) {
    loginStatus.textContent = 'Сначала сохрани ADMIN_TOKEN.';
    return;
  }

  try {
    const [overview, payments, devices] = await Promise.all([
      fetchJson('/admin/overview', token),
      fetchJson('/admin/payments', token),
      fetchJson('/admin/devices', token),
    ]);

    renderStats(overview.stats);
    renderPayments(payments);
    renderDevices(devices);
    loginStatus.textContent = 'Данные актуальны.';
  } catch (error) {
    loginStatus.textContent = error.message || 'Не удалось загрузить данные.';
    console.error(error);
  }
}

async function fetchJson(path, token, options = {}) {
  const response = await fetch(`${apiBase}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-Admin-Token': token,
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (_) {
      // ignore JSON parsing error
    }
    throw new Error(detail);
  }

  return response.json();
}

function renderStats(stats) {
  statsGrid.innerHTML = `
    <article class="stat-card"><span>Устройства</span><strong>${number(stats.totalDevices)}</strong></article>
    <article class="stat-card"><span>Активные</span><strong>${number(stats.activeSubscriptions)}</strong></article>
    <article class="stat-card"><span>Pending</span><strong>${number(stats.pendingPayments)}</strong></article>
    <article class="stat-card"><span>Выручка</span><strong>${number(stats.revenueRub)} ₽</strong></article>
  `;
}

function renderPayments(payments) {
  if (!payments.length) {
    paymentsBody.innerHTML = '<tr><td colspan="6">Платежей пока нет.</td></tr>';
    return;
  }

  paymentsBody.innerHTML = payments
    .map(
      (payment) => `
        <tr>
          <td><code>${escapeHtml(payment.paymentId)}</code></td>
          <td>${escapeHtml(payment.deviceId)}</td>
          <td>${escapeHtml(payment.planTitle)}</td>
          <td>${number(payment.amountRub)} ₽</td>
          <td><span class="badge badge--${badgeTone(payment.status)}">${escapeHtml(payment.status)}</span></td>
          <td>${formatDate(payment.createdAt)}</td>
        </tr>
      `,
    )
    .join('');
}

function renderDevices(devices) {
  if (!devices.length) {
    devicesBody.innerHTML = '<tr><td colspan="6">Устройств пока нет.</td></tr>';
    return;
  }

  devicesBody.innerHTML = devices
    .map((device) => {
      const isBanned = device.accessStatus === 'banned';
      return `
        <tr>
          <td><code>${escapeHtml(device.deviceId)}</code></td>
          <td>${escapeHtml(device.platform || '-')}</td>
          <td><span class="badge badge--${badgeTone(device.accessStatus)}">${escapeHtml(device.accessStatus)}</span></td>
          <td>${escapeHtml(device.activePlanTitle || '—')}</td>
          <td>${formatDate(device.subscriptionEndsAt)}</td>
          <td>
            <div class="device-actions">
              <button
                class="action ${isBanned ? 'action--safe' : 'action--danger'}"
                type="button"
                data-device-id="${escapeHtml(device.deviceId)}"
                data-action="${isBanned ? 'unban' : 'ban'}"
              >
                ${isBanned ? 'Разблокировать' : 'Заблокировать'}
              </button>
            </div>
          </td>
        </tr>
      `;
    })
    .join('');

  for (const button of devicesBody.querySelectorAll('button[data-device-id]')) {
    button.addEventListener('click', onDeviceAction);
  }
}

async function onDeviceAction(event) {
  const button = event.currentTarget;
  const token = localStorage.getItem(tokenKey);
  const deviceId = button.getAttribute('data-device-id');
  const action = button.getAttribute('data-action');
  if (!token || !deviceId || !action) {
    return;
  }

  button.disabled = true;
  try {
    await fetchJson(`/admin/devices/${encodeURIComponent(deviceId)}/${action}`, token, {
      method: 'POST',
      body: '{}',
    });
    await loadDashboard();
  } catch (error) {
    loginStatus.textContent = error.message || 'Не удалось выполнить действие.';
    console.error(error);
  } finally {
    button.disabled = false;
  }
}

function badgeTone(status) {
  switch (status) {
    case 'active':
    case 'paid':
      return 'active';
    case 'failed':
      return 'failed';
    case 'banned':
      return 'banned';
    default:
      return 'pending';
  }
}

function formatDate(value) {
  if (!value) {
    return '—';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }

  return date.toLocaleString('ru-RU');
}

function number(value) {
  return Number(value || 0).toLocaleString('ru-RU');
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

if (tokenInput.value.trim()) {
  loadDashboard();
}
