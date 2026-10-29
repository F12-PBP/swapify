(() => {
  const openDialog = (dialog) => {
    if (!dialog || dialog.open) return;
    dialog.showModal();
    document.documentElement.classList.add("market-dialog-open");
  };
  window.SwapDialogs = { open: openDialog };
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
      if (dialog.open) return;
      document.documentElement.classList.remove("market-dialog-open");
      dialog.querySelector("form")?.reset();
    });
  });

  const swapDialog = document.getElementById("propose-swap");
  if (!swapDialog) return;
  const content = swapDialog.querySelector("[data-swap-content]");
  const status = swapDialog.querySelector("[data-swap-status]");
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
  const showFormErrors = () => {
    const error = content.querySelector('[role="alert"]');
    if (error) {
      error.tabIndex = -1;
      error.focus();
    }
  };
  swapDialog.addEventListener("close", () => { loadSequence += 1; });
  document.addEventListener("click", async (event) => {
    const link = event.target.closest("a[data-swap-link]");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const sequence = ++loadSequence;
    content.replaceChildren();
    const heading = document.createElement("h2");
    heading.id = "swap-title";
    heading.className = "font-display text-h4 text-primary-base";
    heading.textContent = "Propose a swap";
    content.append(heading);
    status.textContent = "Finding your available pieces…";
    openDialog(swapDialog);
    try {
      const response = await request(link.href);
      if (sequence !== loadSequence || !swapDialog.open || followSignIn(response)) return;
      if (!response.ok) {
        status.textContent = response.status === 404
          ? "This piece is no longer available for a new swap. Please choose another."
          : "We couldn’t load this swap. Close this window and try again.";
        return;
      }
      const html = await response.text();
      if (sequence !== loadSequence || !swapDialog.open) return;
      content.innerHTML = html;
      window.SwapDropdown?.init(content);
      status.textContent = "";
      content.querySelector("summary, select, a")?.focus();
    } catch {
      if (sequence === loadSequence && swapDialog.open) status.textContent = "We couldn’t connect. Close this window and try again.";
    }
  });
  swapDialog.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-swap-form]");
    if (!form) return;
    event.preventDefault();
    if (swapDialog.dataset.submitting === "true") return;
    swapDialog.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");
    const button = form.querySelector('button[type="submit"]');
    const closeButton = swapDialog.querySelector("[data-dialog-close]");
    button.disabled = true;
    closeButton.disabled = true;
    status.textContent = "Sending your swap request…";
    try {
      const response = await request(form.action, { method: "POST", body: new FormData(form) });
      if (followSignIn(response)) return;
      if (response.status === 201) {
        const result = await response.json();
        window.location.assign(result.redirect);
        return;
      }
      if (response.status === 400) {
        content.innerHTML = await response.text();
        window.SwapDropdown?.init(content);
        status.textContent = "Please review the highlighted details.";
        showFormErrors();
      } else {
        status.textContent = response.status === 404
          ? "This piece is no longer available. Close this window and choose another."
          : "We couldn’t confirm your request. Check My swaps before trying again.";
      }
    } catch {
      status.textContent = "We couldn’t confirm your request. Check My swaps before trying again.";
    } finally {
      swapDialog.dataset.submitting = "false";
      form.removeAttribute("aria-busy");
      button.disabled = false;
      closeButton.disabled = false;
    }
  });
})();
