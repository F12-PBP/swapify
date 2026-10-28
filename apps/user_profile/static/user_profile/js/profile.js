(() => {
  const initPhoto = (root) => {
    const input = root.querySelector('[data-profile-photo]');
    if (!input) return;
    const preview = root.querySelector('[data-profile-photo-preview]');
    const prompt = root.querySelector('[data-profile-photo-prompt]');
    const status = root.querySelector('[data-profile-photo-status]');
    let url;
    const update = () => {
      const file = input.files[0];
      input.setCustomValidity('');
      if (!file) return;
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
        const error = 'Choose a JPG, PNG, or WebP image up to 5 MB.';
        input.setCustomValidity(error);
        status.textContent = error;
        input.reportValidity();
        return;
      }
      if (url) URL.revokeObjectURL(url);
      url = URL.createObjectURL(file);
      preview.src = url;
      preview.hidden = false;
      prompt.hidden = true;
      status.textContent = `${file.name} — save changes to update your profile.`;
    };
    input.addEventListener('change', update);
    const drop = root.querySelector('[data-profile-photo-drop]');
    drop.addEventListener('dragover', (event) => event.preventDefault());
    drop.addEventListener('drop', (event) => {
      event.preventDefault();
      if (event.dataTransfer.files.length !== 1) {
        status.textContent = 'Choose one profile photo.';
        return;
      }
      input.files = event.dataTransfer.files;
      update();
    });
    return () => { if (url) URL.revokeObjectURL(url); };
  };

  const dialog = document.querySelector('#profile-edit-dialog');
  let releasePhoto = initPhoto(document);
  if (dialog) {
    const content = dialog.querySelector('[data-profile-dialog-content]');
    let loading;
    const initialize = () => {
      releasePhoto?.();
      releasePhoto = initPhoto(content);
      window.SwapLocation?.init();
      const target = content.querySelector('[role="alert"], input:not([type="hidden"]), button, a');
      if (target?.getAttribute('role') === 'alert') target.tabIndex = -1;
      target?.focus();
    };
    document.querySelectorAll('[data-profile-edit]').forEach((link) => {
      link.addEventListener('click', async (event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        loading?.abort();
        loading = new AbortController();
        content.innerHTML = '<h2 id="profile-edit-title" class="font-display text-h4 text-primary-base">Loading…</h2><p role="status" class="text-b8 text-neutral-80">Opening your profile settings.</p>';
        dialog.showModal();
        try {
          const response = await fetch(link.href, {
            headers: { 'X-Profile-Dialog': '1' }, signal: loading.signal,
          });
          if (response.redirected) { window.location.assign(response.url); return; }
          if (!response.ok) throw new Error();
          const html = await response.text();
          if (!dialog.open) return;
          content.innerHTML = html;
          initialize();
        } catch (error) {
          if (error.name === 'AbortError') return;
          dialog.close();
          window.location.assign(link.href);
        }
      });
    });
    content.addEventListener('click', (event) => {
      if (event.target.closest('[data-profile-cancel]')) {
        event.preventDefault();
        dialog.close();
      }
    });
    content.addEventListener('submit', async (event) => {
      const form = event.target.closest('[data-profile-form]');
      if (!form) return;
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      if (button.disabled) return;
      button.disabled = true;
      form.setAttribute('aria-busy', 'true');
      const status = form.querySelector('[data-profile-form-status]');
      status.hidden = false;
      status.textContent = 'Saving your changes…';
      try {
        const response = await fetch(form.action, {
          method: 'POST', body: new FormData(form),
          headers: { 'X-Profile-Dialog': '1' },
        });
        if (response.redirected) { window.location.assign(response.url); return; }
        if (response.status === 422) {
          content.innerHTML = await response.text();
          initialize();
          return;
        }
        if (!response.ok) throw new Error();
        const result = await response.json();
        window.location.assign(result.redirect);
      } catch {
        status.textContent = 'Your changes could not be saved. Please try again.';
        button.disabled = false;
        form.removeAttribute('aria-busy');
      }
    });
    dialog.addEventListener('close', () => {
      loading?.abort();
      releasePhoto?.();
      content.replaceChildren();
    });
  }

  const mapElement = document.querySelector('[data-profile-map]');
  if (mapElement && window.L) {
    const latitude = Number(mapElement.dataset.latitude);
    const longitude = Number(mapElement.dataset.longitude);
    if (Number.isFinite(latitude) && Number.isFinite(longitude) && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180) {
      const area = [Number(latitude.toFixed(2)), Number(longitude.toFixed(2))];
      const map = window.L.map(mapElement, { scrollWheelZoom: false }).setView(area, 13);
      window.L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19, referrerPolicy: 'strict-origin-when-cross-origin',
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).on('tileerror', () => {
        document.querySelector('[data-map-status]').textContent = 'Some map tiles could not load. Your saved area is unchanged.';
      }).addTo(map);
      const color = getComputedStyle(document.documentElement).getPropertyValue('--color-primary-base').trim();
      window.L.circle(area, { radius: 1000, color, weight: 1, fillOpacity: 0.12 }).addTo(map);
      window.L.circleMarker(area, { radius: 5, color: '#fff', weight: 2, fillColor: color, fillOpacity: 1 }).addTo(map);
      new ResizeObserver(() => map.invalidateSize({ pan: false })).observe(mapElement);
    }
  }

  const reviews = document.querySelector('[data-profile-reviews]');
  if (reviews) {
    const results = reviews.querySelector('[data-review-results]');
    const error = reviews.querySelector('[data-review-error]');
    let request;
    const load = async (url, push = true) => {
      request?.abort();
      const controller = new AbortController();
      request = controller;
      results.setAttribute('aria-busy', 'true');
      error.textContent = '';
      try {
        const response = await fetch(url, { headers: { 'X-Profile-Reviews': '1' }, signal: controller.signal });
        if (response.redirected) { window.location.assign(response.url); return; }
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (request !== controller) return;
        results.innerHTML = data.html;
        const rating = new URL(url).searchParams.get('rating') || '';
        reviews.querySelectorAll('[data-review-filter]').forEach((link) => {
          const selected = link.dataset.reviewFilter === rating;
          link.classList.toggle('market-chip-active', selected);
          if (selected) link.setAttribute('aria-current', 'true');
          else link.removeAttribute('aria-current');
        });
        if (push) history.pushState(null, '', url);
      } catch (reason) {
        if (reason.name !== 'AbortError') error.textContent = 'Reviews could not be loaded. Please try again.';
      } finally {
        if (request === controller) results.removeAttribute('aria-busy');
      }
    };
    reviews.addEventListener('click', (event) => {
      const link = event.target.closest('[data-review-filter], [data-review-page]');
      if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      load(link.href);
    });
    window.addEventListener('popstate', () => load(window.location.href, false));
  }
})();
