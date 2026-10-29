(() => {
  const openDialog = (dialog) => {
    if (!dialog || dialog.open) return;
    dialog.showModal();
    document.documentElement.classList.add("market-dialog-open");
  };
  document.querySelectorAll("[data-dialog-open]").forEach((button) => {
    button.hidden = false;
    button.addEventListener("click", () => openDialog(document.getElementById(button.dataset.dialogOpen)));
  });
  document.querySelectorAll(".market-dialog").forEach((dialog) => {
    dialog.addEventListener("cancel", (event) => {
      if (dialog.dataset.submitting === "true") event.preventDefault();
    });
    dialog.addEventListener("click", (event) => {
      if (dialog.dataset.submitting === "true") return;
      if (event.target.closest("[data-dialog-close]")) dialog.close();
      if (event.target === dialog) {
        const bounds = dialog.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
      }
    });
    dialog.addEventListener("close", () => {
      document.documentElement.classList.remove("market-dialog-open");
      dialog.querySelector("form")?.reset();
    });
  });

  // The swap dialog shows proposals, swap details, and their follow-up steps.
  // Every link and form inside it still works as a normal page without script.
  const swapDialog = document.getElementById("propose-swap");
  if (!swapDialog) return;
  const content = swapDialog.querySelector("[data-swap-content]");
  const status = swapDialog.querySelector("[data-swap-status]");
  const closeButton = swapDialog.querySelector("[data-dialog-close]");
  let loadSequence = 0;
  const request = async (url, options = {}) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      return await fetch(url, {
        ...options,
        credentials: "same-origin",
        signal: controller.signal,
        headers: { "X-Requested-With": "XMLHttpRequest", ...options.headers },
      });
    } finally {
      clearTimeout(timeout);
    }
  };
  const followSignIn = (response) => {
    if (!response.redirected) return false;
    window.location.assign(response.url);
    return true;
  };
  const announceChange = () => document.dispatchEvent(new CustomEvent("swap:changed"));
  const render = (html, { focusField = false } = {}) => {
    content.innerHTML = html;
    window.SwapDropdown?.init(content);
    const field = focusField && content.querySelector("[data-swap-form] summary, [data-swap-form] select");
    (field || content.querySelector("#swap-title"))?.focus();
  };
  const showFormErrors = () => {
    const error = content.querySelector('[role="alert"]');
    if (error) {
      error.tabIndex = -1;
      error.focus();
    }
  };
  const VIEWS = {
    propose: {
      title: "Propose a swap",
      loading: "Finding your available pieces…",
      missing: "This piece is no longer available for a new swap. Please choose another.",
    },
    detail: {
      title: "Swap Detail",
      loading: "Opening this swap…",
      missing: "This swap is no longer available. Refresh My swaps to see the latest updates.",
    },
  };

  const load = async (url, view, { message = "" } = {}) => {
    const sequence = ++loadSequence;
    // Moving between steps keeps the current step visible until the next one
    // arrives, so the dialog never collapses to an empty frame.
    if (swapDialog.open) {
      content.inert = true;
    } else {
      content.replaceChildren();
      const heading = document.createElement("h2");
      heading.id = "swap-title";
      heading.className = "font-display text-h4 text-primary-base";
      heading.textContent = view.title;
      content.append(heading);
    }
    status.textContent = message || view.loading;
    openDialog(swapDialog);
    try {
      const response = await request(url);
      if (sequence !== loadSequence || !swapDialog.open || followSignIn(response)) return;
      if (!response.ok && response.status !== 409) {
        status.textContent = response.status === 404 ? view.missing : "We couldn’t load this swap. Close this window and try again.";
        return;
      }
      const html = await response.text();
      if (sequence !== loadSequence || !swapDialog.open) return;
      render(html, { focusField: view === VIEWS.propose && response.ok });
      status.textContent = message;
    } catch {
      if (sequence === loadSequence && swapDialog.open) status.textContent = "We couldn’t connect. Close this window and try again.";
    } finally {
      if (sequence === loadSequence) content.inert = false;
    }
  };

  swapDialog.addEventListener("close", () => {
    loadSequence += 1;
    content.inert = false;
  });
  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-swap-link], a[data-swap-detail]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    load(link.href, link.hasAttribute("data-swap-detail") ? VIEWS.detail : VIEWS.propose);
  });
  swapDialog.addEventListener("click", (event) => {
    // On the discovery page, keep the visitor's place instead of reloading it.
    if (event.target.closest("[data-swap-keep-discovering]") && document.querySelector("[data-catalog]")) {
      event.preventDefault();
      swapDialog.close();
    }
  });

  const setSubmitting = (form, submitting) => {
    swapDialog.dataset.submitting = String(submitting);
    if (submitting) form.setAttribute("aria-busy", "true");
    else form.removeAttribute("aria-busy");
    form.querySelectorAll('button[type="submit"]').forEach((button) => { button.disabled = submitting; });
    closeButton.disabled = submitting;
  };
  const submitAction = async (form) => {
    const detailURL = form.closest("[data-swap-detail-url]")?.dataset.swapDetailUrl;
    status.textContent = "Updating this swap…";
    const response = await request(form.action, { method: "POST", body: new FormData(form) });
    if (followSignIn(response)) return;
    const result = await response.json().catch(() => null);
    if (!result || !detailURL) {
      status.textContent = "We couldn’t update this swap. Refresh My swaps and try again.";
      return;
    }
    announceChange();
    await load(detailURL, VIEWS.detail, { message: result.message });
  };
  const submitProposal = async (form) => {
    status.textContent = "Sending your swap request…";
    const response = await request(form.action, { method: "POST", body: new FormData(form) });
    if (followSignIn(response)) return;
    if (response.status === 201) {
      const result = await response.json();
      render(result.html);
      status.textContent = "";
      announceChange();
    } else if (response.status === 400 || response.status === 409) {
      render(await response.text());
      status.textContent = response.status === 400 ? "Please review the highlighted details." : "";
      showFormErrors();
    } else {
      status.textContent = response.status === 404
        ? VIEWS.propose.missing
        : "We couldn’t confirm your request. Check My swaps before trying again.";
    }
  };
  swapDialog.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-swap-form], [data-swap-action]");
    if (!form) return;
    event.preventDefault();
    if (swapDialog.dataset.submitting === "true") return;
    setSubmitting(form, true);
    try {
      if (form.hasAttribute("data-swap-action")) await submitAction(form);
      else await submitProposal(form);
    } catch {
      status.textContent = "We couldn’t confirm this change. Check My swaps before trying again.";
    } finally {
      setSubmitting(form, false);
    }
  });
})();
