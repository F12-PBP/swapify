(() => {
  const root = document.querySelector("[data-my-swaps]");
  const search = document.getElementById("swap-search");
  if (!root || !search) return;
  const results = document.getElementById("swap-results");
  const feedback = document.getElementById("swap-feedback");
  const status = feedback.querySelector("[data-swap-status]");
  const retry = feedback.querySelector("[data-swap-retry]");
  const announcer = root.querySelector("[data-swap-announce]");
  const filterErrors = document.getElementById("swap-filter-errors");
  const fields = ["search", "role", "status"];
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let appliedURL = new URL(window.location.href);
  let pendingURL = appliedURL;
  let requestSequence = 0;
  let controller;
  let debounce;
  let composing = false;

  document.querySelectorAll("[data-swap-filter-apply]").forEach((button) => { button.hidden = true; });

  const canonicalURL = (state, page) => {
    const target = new URL(window.location.pathname, window.location.origin);
    fields.forEach((name) => { if (state[name]) target.searchParams.set(name, state[name]); });
    if (page > 1) target.searchParams.set("page", page);
    return target;
  };
  const withChanges = (changes) => {
    const target = new URL(appliedURL);
    target.searchParams.delete("page");
    Object.entries(changes).forEach(([name, value]) => {
      if (value) target.searchParams.set(name, value);
      else target.searchParams.delete(name);
    });
    return target;
  };

  const synchronize = (state) => {
    // Rewriting a focused input moves the caret; keep the visitor's draft as typed.
    if (document.activeElement !== search && search.value !== state.search) search.value = state.search;
    root.querySelectorAll("[data-swap-filter-form] [name='status']").forEach((input) => {
      input.value = state.status;
      if (input.tagName === "INPUT") input.defaultValue = state.status;
    });
    window.SwapDropdown?.sync(root);
    root.querySelectorAll("[data-swap-role]").forEach((chip) => {
      const selected = chip.dataset.swapRole === state.role;
      chip.classList.toggle("market-chip-active", selected);
      if (selected) chip.setAttribute("aria-current", "true");
      else chip.removeAttribute("aria-current");
      chip.href = canonicalURL({ ...state, role: chip.dataset.swapRole }, 1);
    });
  };

  const invalidatePending = () => {
    clearTimeout(debounce);
    controller?.abort();
    requestSequence += 1;
  };

  const load = async (url, { history = "push", scroll = false, preserveLayout = false, quiet = false } = {}) => {
    invalidatePending();
    const sequence = requestSequence;
    controller = new AbortController();
    const activeController = controller;
    pendingURL = new URL(url);
    results.setAttribute("aria-busy", "true");
    retry.hidden = true;
    if (!quiet) {
      status.textContent = "Updating your swaps…";
      feedback.classList.remove("invisible");
    }
    const timeout = setTimeout(() => activeController.abort(), 15000);
    try {
      const response = await fetch(url, {
        headers: { "X-Swap-Request": "results", "Accept": "application/json" },
        credentials: "same-origin",
        signal: activeController.signal,
      });
      if (response.redirected) {
        window.location.assign(response.url);
        return;
      }
      if (!response.ok) throw new Error("My swaps request failed");
      const data = await response.json();
      if (sequence !== requestSequence) return;
      // While typing, hold the current height so the page under the search box
      // doesn't jump while the result count changes.
      if (preserveLayout) results.style.minHeight = `${results.getBoundingClientRect().height}px`;
      else results.style.removeProperty("min-height");
      results.innerHTML = data.html;
      synchronize(data.filters);
      filterErrors.hidden = !data.has_errors;
      const target = canonicalURL(data.filters, data.page);
      if (history === "push" && target.href !== window.location.href) window.history.pushState(null, "", target);
      else if (history === "replace" && target.href !== window.location.href) window.history.replaceState(null, "", target);
      appliedURL = target;
      status.textContent = "";
      feedback.classList.add("invisible");
      announcer.textContent = `${data.count} swap${data.count === 1 ? "" : "s"} shown`;
      if (scroll) root.scrollIntoView({ block: "start", behavior: reduceMotion.matches ? "auto" : "smooth" });
    } catch {
      if (sequence !== requestSequence) return;
      status.textContent = "We couldn’t update your swaps. Your previous results are still shown.";
      feedback.classList.remove("invisible");
      retry.hidden = false;
    } finally {
      clearTimeout(timeout);
      if (sequence === requestSequence) results.setAttribute("aria-busy", "false");
    }
  };

  const queueSearch = () => {
    invalidatePending();
    results.setAttribute("aria-busy", "false");
    if (composing) return;
    debounce = setTimeout(() => {
      load(withChanges({ search: search.value.trim() }), { history: "replace", preserveLayout: true });
    }, 300);
  };
  search.addEventListener("input", queueSearch);
  search.addEventListener("compositionstart", () => { composing = true; invalidatePending(); });
  search.addEventListener("compositionend", () => { composing = false; queueSearch(); });
  search.form.addEventListener("submit", (event) => {
    event.preventDefault();
    load(withChanges({ search: search.value.trim() }));
  });

  root.addEventListener("change", (event) => {
    const input = event.target.closest("[data-auto-submit]");
    if (!input?.closest("[data-swap-filter-form]")) return;
    load(withChanges({ status: input.value, search: search.value.trim() }));
  });
  root.addEventListener("submit", (event) => {
    const form = event.target.closest("[data-swap-filter-form]");
    if (!form) return;
    event.preventDefault();
    load(withChanges({ status: new FormData(form).get("status"), search: search.value.trim() }));
  });
  root.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-swap-filter-link]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const target = new URL(link.href);
    // Keep an unfinished search when a direction is chosen before its debounce.
    if (link.hasAttribute("data-swap-role")) {
      if (search.value.trim()) target.searchParams.set("search", search.value.trim());
      else target.searchParams.delete("search");
    }
    load(target, { scroll: link.hasAttribute("data-swap-page") });
  });
  retry.addEventListener("click", () => load(pendingURL));
  window.addEventListener("popstate", () => load(new URL(window.location.href), { history: "none" }));
  // Accepting, rejecting, or resending in the dialog updates the cards behind it.
  document.addEventListener("swap:changed", () => {
    load(appliedURL, { history: "none", preserveLayout: true, quiet: true });
  });
})();
