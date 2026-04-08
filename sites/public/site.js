const apiBase = 'https://api.tajvpn.com';
const plansGrid = document.getElementById('plans-grid');

async function loadPlans() {
  if (!plansGrid) {
    return;
  }

  try {
    const response = await fetch(`${apiBase}/plans`, {
      headers: { Accept: 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const plans = await response.json();
    renderPlans(plans);
  } catch (error) {
    plansGrid.innerHTML = `
      <article class="plan-card">
        <h3>Тарифы пока недоступны</h3>
        <p>Не удалось получить список тарифов с api.tajvpn.com. Проверь backend, CORS и запуск контейнеров.</p>
      </article>
    `;
    console.error(error);
  }
}

function renderPlans(plans) {
  if (!Array.isArray(plans) || plans.length === 0) {
    plansGrid.innerHTML = `
      <article class="plan-card">
        <h3>Нет активных тарифов</h3>
        <p>Добавь или активируй тарифы в backend seed-данных, и они появятся здесь автоматически.</p>
      </article>
    `;
    return;
  }

  plansGrid.innerHTML = plans
    .map((plan) => {
      const benefits = Array.isArray(plan.benefits)
        ? plan.benefits.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
        : '';

      return `
        <article class="plan-card ${plan.isFeatured ? 'plan-card--featured' : ''}">
          <div class="plan-card__title">
            <h3>${escapeHtml(plan.title)}</h3>
            ${plan.badge ? `<span class="badge">${escapeHtml(plan.badge)}</span>` : ''}
          </div>
          <p class="price">${Number(plan.amountRub).toLocaleString('ru-RU')} ₽</p>
          <p>${escapeHtml(plan.description || '')}</p>
          ${benefits ? `<ul>${benefits}</ul>` : ''}
        </article>
      `;
    })
    .join('');
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

loadPlans();
