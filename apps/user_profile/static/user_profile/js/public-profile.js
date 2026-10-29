window.MarketplacePages.register((scope) => {
  const root = document.querySelector('[data-public-profile]');
  if (!root) return;
  const form = root.querySelector('[data-member-filters]');
  const results = root.querySelector('[data-member-results]');
  const feedback = root.querySelector('[data-member-feedback]');
  const tabs = [...root.querySelectorAll('[data-member-tab]')];
  const indicator = root.querySelector('[data-member-indicator]');
  const search = document.getElementById('market-search');
  const searchForm = search.form;
  const searchLabel = searchForm.querySelector('label[for="market-search"]');
  const searchButton = searchForm.querySelector('button[type="submit"]');
  const fields = ['type', 'search', 'size', 'condition', 'distance', 'sort'];
  const defaultTab = root.dataset.defaultTab;
  let appliedURL = new URL(location.href);
  let controller;
  let sequence = 0;
  let debounce;
  let composing = false;
  let searchScope;
  let wardrobeSearch = form.elements.search.value;
  let discoverSearch = '';
  const invalidatePending = () => {
    scope.clearTimeout(debounce);
    controller?.abort();
    sequence += 1;
  };
  scope.cleanup(invalidatePending);
  const configureSearch = (name) => {
    if (searchScope === 'wardrobe') wardrobeSearch = search.value;
    else if (searchScope) discoverSearch = search.value;
    searchScope = name;
    const local = name === 'wardrobe';
    search.value = local ? wardrobeSearch : discoverSearch;
    searchForm.action = local ? location.pathname : searchForm.dataset.discoveryAction;
    searchForm.elements.tab.disabled = !local;
    searchLabel.textContent = local ? 'Search this wardrobe' : 'Search clothing';
    searchButton.setAttribute('aria-label', searchLabel.textContent);
    search.placeholder = local ? 'Search this wardrobe...' : 'Find your next favourite...';
    if (local) {
      search.setAttribute('aria-controls', results.id);
      search.setAttribute('autocomplete', 'off');
    } else {
      search.removeAttribute('aria-controls');
      search.removeAttribute('autocomplete');
    }
  };

  root.querySelector('[data-member-apply]').hidden = true;
  const selectTab = (name) => {
    configureSearch(name);
    results.style.removeProperty('min-height');
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
  const synchronize = (filters, url, restoreSearch = false) => {
    wardrobeSearch = filters.search || '';
    if (searchScope === 'wardrobe' && (restoreSearch || document.activeElement !== search) && search.value !== wardrobeSearch) {
      search.value = wardrobeSearch;
    }
    fields.forEach((name) => {
      document.querySelectorAll(`[data-member-filters] [name="${name}"], [role="search"] input[type="hidden"][name="${name}"]`).forEach((input) => {
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
  const load = async (url, { historyMode = 'push', preserveLayout = false } = {}) => {
    invalidatePending();
    controller = new AbortController();
    const activeController = controller;
    const current = sequence;
    const timeout = scope.timeout(() => activeController.abort(), 15000);
    results.setAttribute('aria-busy', 'true');
    feedback.classList.add('sr-only');
    feedback.textContent = 'Updating this wardrobe…';
    try {
      const response = await scope.fetch(url, {
        headers: { 'X-Member-Wardrobe': '1', Accept: 'application/json' },
        signal: activeController.signal,
      });
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (current !== sequence) return;
      if (preserveLayout) results.style.minHeight = `${results.getBoundingClientRect().height}px`;
      else results.style.removeProperty('min-height');
      results.innerHTML = data.html;
      if (!results.closest('[hidden]')) {
        results.firstElementChild?.classList.add('motion-safe:animate-profile-reveal', 'motion-safe:[animation-duration:420ms]');
      }
      synchronize(data.filters, url, historyMode === 'none');
      appliedURL = new URL(url);
      if (historyMode === 'push' && url.href !== location.href) history.pushState(null, '', url);
      else if (historyMode === 'replace') history.replaceState(null, '', url);
      scope.locationChanged();
      feedback.textContent = `${data.count} piece${data.count === 1 ? '' : 's'} found.`;
    } catch {
      if (current !== sequence) return;
      feedback.classList.remove('sr-only');
      feedback.textContent = 'Couldn’t update this wardrobe. Your previous results are still shown. Try searching or filtering again.';
      synchronize(Object.fromEntries(appliedURL.searchParams), appliedURL);
    } finally {
      scope.clearTimeout(timeout);
      if (current === sequence) results.setAttribute('aria-busy', 'false');
    }
  };
  const filterURL = () => {
    const url = new URL(location.pathname, location.origin);
    for (const [name, value] of new FormData(form)) {
      if (value) url.searchParams.set(name, value);
    }
    url.searchParams.set('tab', 'wardrobe');
    if (search.value.trim()) url.searchParams.set('search', search.value.trim());
    else url.searchParams.delete('search');
    return url;
  };
  const queueSearch = () => {
    if (searchScope !== 'wardrobe') return;
    invalidatePending();
    results.setAttribute('aria-busy', 'false');
    feedback.textContent = '';
    if (composing) return;
    debounce = scope.timeout(() => load(filterURL(), { historyMode: 'replace', preserveLayout: true }), 250);
  };
  scope.on(search, 'input', queueSearch);
  scope.on(search, 'compositionstart', () => {
    composing = true;
    queueSearch();
  });
  scope.on(search, 'compositionend', () => { composing = false; queueSearch(); });
  scope.on(searchForm, 'submit', (event) => {
    if (searchScope !== 'wardrobe') return;
    event.preventDefault();
    if (!composing) load(filterURL());
  });
  configureSearch(document.getElementById('member-wardrobe').hidden ? 'profile' : 'wardrobe');
  scope.on(form, 'submit', (event) => { event.preventDefault(); load(filterURL()); });
  scope.on(form, 'change', () => load(filterURL()));
  scope.on(root, 'click', (event) => {
    const link = event.target.closest('a[data-member-tab], a[data-member-category], a[data-member-page]');
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const url = new URL(link.href);
    if (link.dataset.memberTab) {
      const draft = searchScope === 'wardrobe' ? search.value : wardrobeSearch;
      invalidatePending();
      results.setAttribute('aria-busy', 'false');
      feedback.textContent = '';
      synchronize(Object.fromEntries(appliedURL.searchParams), appliedURL);
      wardrobeSearch = draft;
      if (searchScope === 'wardrobe') search.value = draft;
      const target = new URL(location.href);
      target.hash = '';
      target.searchParams.set('tab', link.dataset.memberTab);
      selectTab(link.dataset.memberTab);
      if (target.href !== location.href) history.pushState(null, '', target);
      scope.locationChanged();
      if (searchScope === 'wardrobe' && search.value.trim() !== form.elements.search.value) {
        load(filterURL(), { historyMode: 'replace', preserveLayout: true });
      }
    } else if (link.hasAttribute('data-member-category')) {
      const target = filterURL();
      if (link.dataset.memberCategory) target.searchParams.set('type', link.dataset.memberCategory);
      else target.searchParams.delete('type');
      load(target);
    } else load(url);
  });
  scope.on(window, 'popstate', () => {
    const url = new URL(location.href);
    const name = url.searchParams.get('tab') || (url.searchParams.has('reviews_page') ? 'profile' : defaultTab);
    selectTab(name === 'profile' ? 'profile' : 'wardrobe');
    load(url, { historyMode: 'none' });
  });
});
