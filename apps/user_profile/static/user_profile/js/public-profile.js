(() => {
  const root = document.querySelector('[data-public-profile]');
  if (!root) return;
  const form = root.querySelector('[data-member-filters]');
  const results = root.querySelector('[data-member-results]');
  const feedback = root.querySelector('[data-member-feedback]');
  const tabs = [...root.querySelectorAll('[data-member-tab]')];
  const indicator = root.querySelector('[data-member-indicator]');
  const fields = ['type', 'search', 'size', 'condition', 'distance', 'sort'];
  const defaultTab = root.dataset.defaultTab;
  let appliedURL = new URL(location.href);
  let controller;
  let sequence = 0;

  root.querySelector('[data-member-apply]').hidden = true;
  const selectTab = (name) => {
    indicator.classList.toggle('translate-x-[calc(100%_+_0.75rem)]', name === 'wardrobe');
    tabs.forEach((tab) => {
      const selected = tab.dataset.memberTab === name;
      document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
      tab.classList.toggle('text-neutral-10', selected);
      tab.classList.toggle('text-neutral-80', !selected);
      if (selected) tab.setAttribute('aria-current', 'page');
      else tab.removeAttribute('aria-current');
    });
  };
  const synchronize = (filters, url) => {
    fields.forEach((name) => {
      form.querySelectorAll(`[name="${name}"]`).forEach((input) => {
        input.value = filters[name] || (name === 'sort' ? 'recommended' : '');
      });
    });
    window.SwapDropdown?.sync(form);
    root.querySelectorAll('[data-member-category]').forEach((link) => {
      const value = link.dataset.memberCategory;
      const selected = value === (filters.type || '');
      link.classList.toggle('market-chip-active', selected);
      if (selected) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
      const target = new URL(url);
      target.searchParams.delete('wardrobe_page');
      target.searchParams.delete('reviews_page');
      target.searchParams.set('tab', 'wardrobe');
      if (value) target.searchParams.set('type', value);
      else target.searchParams.delete('type');
      link.href = target;
    });
  };
  const load = async (url, push = true) => {
    controller?.abort();
    controller = new AbortController();
    const activeController = controller;
    const current = ++sequence;
    const timeout = setTimeout(() => activeController.abort(), 15000);
    results.setAttribute('aria-busy', 'true');
    feedback.classList.add('sr-only');
    feedback.textContent = 'Updating this wardrobe…';
    try {
      const response = await fetch(url, {
        headers: { 'X-Member-Wardrobe': '1', Accept: 'application/json' },
        signal: activeController.signal,
      });
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (current !== sequence) return;
      results.innerHTML = data.html;
      if (!results.closest('[hidden]')) {
        results.firstElementChild?.classList.add('motion-safe:animate-profile-reveal', 'motion-safe:[animation-duration:420ms]');
      }
      synchronize(data.filters, url);
      appliedURL = new URL(url);
      if (push && url.href !== location.href) history.pushState(null, '', url);
      feedback.textContent = `${data.count} piece${data.count === 1 ? '' : 's'} found.`;
    } catch {
      if (current !== sequence) return;
      feedback.classList.remove('sr-only');
      feedback.textContent = 'Couldn’t update this wardrobe. Your previous results are still shown. Try the filters again.';
      synchronize(Object.fromEntries(appliedURL.searchParams), appliedURL);
    } finally {
      clearTimeout(timeout);
      if (current === sequence) results.setAttribute('aria-busy', 'false');
    }
  };
  const filterURL = () => {
    const url = new URL(location.pathname, location.origin);
    for (const [name, value] of new FormData(form)) {
      if (value) url.searchParams.set(name, value);
    }
    return url;
  };
  form.addEventListener('submit', (event) => { event.preventDefault(); load(filterURL()); });
  form.addEventListener('change', () => load(filterURL()));
  root.addEventListener('click', (event) => {
    const link = event.target.closest('a[data-member-tab], a[data-member-category], a[data-member-page]');
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const url = new URL(link.href);
    if (link.dataset.memberTab) {
      controller?.abort();
      sequence += 1;
      results.setAttribute('aria-busy', 'false');
      feedback.textContent = '';
      synchronize(Object.fromEntries(appliedURL.searchParams), appliedURL);
      const target = new URL(location.href);
      target.hash = '';
      target.searchParams.set('tab', link.dataset.memberTab);
      selectTab(link.dataset.memberTab);
      if (target.href !== location.href) history.pushState(null, '', target);
    } else load(url);
  });
  window.addEventListener('popstate', () => {
    const url = new URL(location.href);
    const name = url.searchParams.get('tab') || (url.searchParams.has('reviews_page') ? 'profile' : defaultTab);
    selectTab(name === 'profile' ? 'profile' : 'wardrobe');
    load(url, false);
  });
})();
