window.MarketplacePages.register((scope) => {
  const catalog = document.querySelector("[data-catalog]");
  if (!catalog) return;
  const results = document.getElementById("catalog-results");
  const feedback = document.getElementById("catalog-feedback");
  const status = feedback.querySelector("[data-catalog-status]");
  const retry = feedback.querySelector("[data-catalog-retry]");
  const search = document.getElementById("market-search");
  const searchForm = search.form;
  const fields = ["search", "type", "size", "condition", "distance", "sort"];
  let appliedURL = new URL(window.location.href);
  let pendingURL = appliedURL;
  let requestSequence = 0;
  let controller;
  let debounce;
  let composing = false;

  search.setAttribute("aria-controls", "catalog-results");
  search.setAttribute("autocomplete", "off");
  document.querySelectorAll("[data-filter-apply]").forEach((button) => { button.hidden = true; });

  const canonicalURL = (url, state) => {
    const target = new URL(url);
    target.search = "";
    fields.forEach((name) => {
      const value = state[name] || "";
      if (value && !(name === "sort" && value === "recommended")) target.searchParams.set(name, value);
    });
    const page = new URL(url).searchParams.get("page");
    if (page && page !== "1") target.searchParams.set("page", page);
    return target;
  };

  const synchronize = (state, url) => {
    // Reassigning a focused sticky input can make the browser reveal its
    // original position in the document. Keep the user's draft and caret intact.
    if (document.activeElement !== search && search.value !== (state.search || "")) search.value = state.search || "";
    document.querySelectorAll("[data-catalog-form], form[role='search']").forEach((form) => {
      fields.forEach((name) => {
        const value = state[name] || (name === "sort" ? "recommended" : "");
        form.querySelectorAll(`[name="${name}"]`).forEach((input) => {
          if (input === search) return;
          input.value = value;
          if (input.tagName === "INPUT") input.defaultValue = value;
        });
      });
    });
    window.SwapDropdown?.sync(document);
    document.querySelectorAll("[data-catalog-category]").forEach((link) => {
      const type = link.dataset.catalogCategory;
      const selected = (state.type || "") === type;
      link.classList.toggle("market-chip-active", selected);
      if (selected) link.setAttribute("aria-current", "true");
      else link.removeAttribute("aria-current");
      const target = new URL(url);
      target.searchParams.delete("page");
      if (type) target.searchParams.set("type", type);
      else target.searchParams.delete("type");
      target.hash = "finds";
      link.href = target;
    });
    document.querySelectorAll("[data-catalog-reset]").forEach((link) => {
      const target = new URL(url);
      ["size", "condition", "distance", "page"].forEach((name) => target.searchParams.delete(name));
      target.hash = "finds";
      link.href = target;
    });
  };

  const invalidatePending = () => {
    scope.clearTimeout(debounce);
    controller?.abort();
    requestSequence += 1;
  };
  scope.cleanup(invalidatePending);

  const load = async (url, { history = "push", scroll = false, preserveLayout = false } = {}) => {
    invalidatePending();
    const sequence = requestSequence;
    controller = new AbortController();
    const activeController = controller;
    pendingURL = new URL(url);
    results.setAttribute("aria-busy", "true");
    status.textContent = "Updating finds…";
    feedback.classList.remove("invisible");
    retry.hidden = true;
    const timeout = scope.timeout(() => activeController.abort("timeout"), 15000);
    try {
      const response = await scope.fetch(url, {
        headers: { "X-Catalog-Request": "results", "Accept": "application/json" },
        credentials: "same-origin",
        signal: activeController.signal,
      });
      if (!response.ok) throw new Error("Catalog request failed");
      const data = await response.json();
      if (sequence !== requestSequence) return;
      const target = canonicalURL(url, data.filters);
      // Shrinking the document beneath a focused sticky input can move the
      // viewport. Keep the results area stable throughout live typing.
      if (preserveLayout) results.style.minHeight = `${results.getBoundingClientRect().height}px`;
      else results.style.removeProperty("min-height");
      results.innerHTML = data.html;
      window.SwapifyMotion?.reveal(results, { duration: 420 });
      synchronize(data.filters, target);
      document.getElementById("catalog-filter-errors").hidden = Object.keys(data.errors).length === 0;
      if (history === "push" && target.href !== window.location.href) window.history.pushState(null, "", target);
      else if (history === "replace") window.history.replaceState(null, "", target);
      appliedURL = target;
      scope.locationChanged();
      feedback.classList.add("invisible");
      if (scroll) catalog.scrollIntoView({ block: "start" });
    } catch {
      if (sequence !== requestSequence) return;
      status.textContent = "We couldn’t update your finds. Your previous results are still shown.";
      retry.hidden = false;
    } finally {
      scope.clearTimeout(timeout);
      if (sequence === requestSequence) results.setAttribute("aria-busy", "false");
    }
  };

  const formURL = (form) => {
    const target = new URL(form.action);
    target.search = "";
    target.hash = "finds";
    for (const [name, value] of new FormData(form)) {
      if (fields.includes(name) && value) target.searchParams.set(name, value);
    }
    if (search.value.trim()) target.searchParams.set("search", search.value.trim());
    else target.searchParams.delete("search");
    return target;
  };
  const searchURL = () => {
    const target = new URL(appliedURL);
    target.searchParams.delete("page");
    if (search.value.trim()) target.searchParams.set("search", search.value.trim());
    else target.searchParams.delete("search");
    return target;
  };
  const queueSearch = () => {
    invalidatePending();
    results.setAttribute("aria-busy", "false");
    if (composing) return;
    debounce = scope.timeout(() => load(searchURL(), { history: "replace", preserveLayout: true }), 250);
  };
  scope.on(search, "input", queueSearch);
  scope.on(search, "compositionstart", () => { composing = true; invalidatePending(); });
  scope.on(search, "compositionend", () => { composing = false; queueSearch(); });
  scope.on(searchForm, "submit", (event) => {
    event.preventDefault();
    load(searchURL(), { history: "push", scroll: true });
  });
  scope.on(document, "change", (event) => {
    const input = event.target.closest("[data-auto-submit]");
    if (input?.form?.matches("[data-catalog-form]")) load(formURL(input.form));
  });
  scope.on(document, "submit", (event) => {
    const form = event.target.closest("[data-catalog-form]");
    if (!form) return;
    event.preventDefault();
    const target = formURL(form);
    const dialog = form.closest("dialog");
    if (dialog?.open) dialog.close();
    load(target);
  });
  scope.on(document, "click", (event) => {
    const link = event.target.closest("a[data-catalog-link]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const target = new URL(link.href);
    // Keep an unfinished search when a category is chosen before its debounce.
    if (link.hasAttribute("data-catalog-category")) {
      if (search.value.trim()) target.searchParams.set("search", search.value.trim());
      else target.searchParams.delete("search");
    }
    const dialog = link.closest("dialog");
    if (dialog?.open) dialog.close();
    load(target, { scroll: link.hasAttribute("data-catalog-page") });
  });
  scope.on(retry, "click", () => load(pendingURL));
  scope.on(window, "popstate", () => load(new URL(window.location.href), { history: "none" }));
});
