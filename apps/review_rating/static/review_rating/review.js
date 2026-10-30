(() => {
  const dialog = document.querySelector('[data-review-dialog]');
  if (!dialog) return;
  const content = dialog.querySelector('[data-review-dialog-content]');
  const close = dialog.querySelector('[data-review-close]');
  let loading;
  let trigger;
  let revision = 0;

  const drawStars = (form, preview) => {
    const selected = Number(form.querySelector('[name="rating"]:checked')?.value || 0);
    const value = preview ?? selected;
    form.querySelectorAll('[data-review-star]').forEach((label) => {
      label.querySelector('svg').style.fill = Number(label.dataset.reviewStar) <= value
        ? 'var(--color-secondary-base)' : 'transparent';
    });
  };
  const render = (html) => {
    content.innerHTML = html;
    const form = content.querySelector('[data-review-form]');
    if (form) drawStars(form);
    (content.querySelector('[role="alert"], #review-form-title'))?.focus();
  };
  document.querySelectorAll('[data-review-form]').forEach((form) => drawStars(form));
  document.addEventListener('pointerover', (event) => {
    if (event.pointerType === 'touch') return;
    const star = event.target.closest('[data-review-star]');
    if (star) drawStars(star.closest('form'), Number(star.dataset.reviewStar));
  });
  document.addEventListener('pointerout', (event) => {
    const stars = event.target.closest('[data-review-stars]');
    if (stars && !stars.contains(event.relatedTarget)) drawStars(stars.closest('form'));
  });
  document.addEventListener('change', (event) => {
    const form = event.target.closest('[data-review-form]');
    if (!form || event.target.name !== 'rating') return;
    drawStars(form);
    form.querySelector('[data-review-rating-status]').textContent = `${event.target.value} out of 5 stars selected.`;
  });
  document.addEventListener('click', async (event) => {
    const link = event.target.closest('[data-review-link]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    trigger = link;
    const current = ++revision;
    loading?.abort();
    loading = new AbortController();
    render('<h2 id="review-form-title" tabindex="-1" class="font-display text-h3 text-primary-base">How was your swap</h2><p role="status" class="mt-4 text-b8 text-neutral-80">Opening your review…</p>');
    dialog.showModal();
    document.documentElement.classList.add('market-dialog-open');
    try {
      const response = await fetch(link.href, { headers: { 'X-Review-Dialog': '1' }, signal: loading.signal });
      if (current !== revision || !dialog.open) return;
      if (response.redirected) { window.location.assign(response.url); return; }
      if (!response.ok) throw new Error();
      const html = await response.text();
      if (current === revision && dialog.open) render(html);
    } catch (error) {
      if (error.name === 'AbortError' || current !== revision) return;
      dialog.close();
      window.location.assign(link.href);
    }
  });
  dialog.addEventListener('cancel', (event) => {
    if (dialog.dataset.submitting === 'true') event.preventDefault();
  });
  dialog.addEventListener('click', (event) => {
    if (dialog.dataset.submitting === 'true') return;
    if (event.target.closest('[data-review-close]')) dialog.close();
    if (event.target === dialog) {
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    }
  });
  dialog.addEventListener('close', () => {
    revision += 1;
    loading?.abort();
    if (!document.querySelector('dialog[open]')) document.documentElement.classList.remove('market-dialog-open');
    trigger?.focus();
  });
  dialog.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-review-form]');
    if (!form) return;
    event.preventDefault();
    if (dialog.dataset.submitting === 'true') return;
    const current = revision;
    const button = form.querySelector('[type="submit"]');
    const status = form.querySelector('[data-review-status]');
    const action = form.action;
    dialog.dataset.submitting = 'true';
    button.disabled = close.disabled = true;
    form.setAttribute('aria-busy', 'true');
    status.hidden = false;
    status.textContent = 'Sharing your review…';
    try {
      const response = await fetch(action, { method: 'POST', body: new FormData(form), headers: { 'X-Review-Dialog': '1' } });
      if (current !== revision || !dialog.open) return;
      if (response.redirected) { window.location.assign(response.url); return; }
      if (response.status === 422) { render(await response.text()); return; }
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (current !== revision || !dialog.open) return;
      dialog.close();
      document.querySelectorAll('[data-review-link]').forEach((link) => {
        if (link.href !== action) return;
        const message = document.createElement('p');
        message.className = 'text-b8 text-neutral-80';
        message.textContent = 'Review submitted. Thank you for sharing your experience.';
        link.replaceWith(message);
        if (link === trigger) { message.tabIndex = -1; message.focus(); }
      });
      window.SwapToast?.show(result.message, { type: 'success' });
      document.dispatchEvent(new CustomEvent('swap:changed'));
    } catch {
      if (current !== revision || !dialog.open) return;
      status.textContent = 'Your review could not be shared. Please try again.';
      window.SwapToast?.show(status.textContent, { type: 'error' });
    } finally {
      dialog.dataset.submitting = 'false';
      button.disabled = close.disabled = false;
      form.removeAttribute('aria-busy');
    }
  });
})();
