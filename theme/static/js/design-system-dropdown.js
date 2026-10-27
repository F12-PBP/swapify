(() => {
  const synchronize = (dropdown) => {
    const trigger = dropdown.querySelector("summary");
    const label = dropdown.querySelector(".swap-dropdown-value");
    const input = dropdown.querySelector('input[type="hidden"]');
    if (!trigger || !label || !input) return;
    const options = Array.from(dropdown.querySelectorAll(".swap-dropdown-option"));
    const selected = options.find((option) => option.dataset.value === input.value)
      || options.find((option) => option.dataset.value === "");
    if (selected) {
      input.value = selected.dataset.value;
      label.textContent = selected.textContent.trim();
    }
    if (trigger.hasAttribute("aria-label")) {
      const prefix = trigger.getAttribute("aria-label").split(":")[0];
      trigger.setAttribute("aria-label", `${prefix}: ${label.textContent.trim()}`);
    }
    options.forEach((option) => {
      option.setAttribute("aria-selected", String(option === selected));
      option.tabIndex = option === selected ? 0 : -1;
    });
    dropdown.classList.toggle("is-filled", Boolean(input.value));
    trigger.setAttribute("aria-expanded", String(dropdown.open));
    const fallback = dropdown.closest("[data-dropdown-field]")?.querySelector("[data-dropdown-fallback]");
    if (fallback) fallback.value = input.value;
  };

  const init = (root = document) => {
    root.querySelectorAll("[data-dropdown-enhanced]").forEach((dropdown) => {
      dropdown.hidden = false;
      const fallback = dropdown.closest("[data-dropdown-field]")?.querySelector("[data-dropdown-fallback]");
      if (fallback) {
        fallback.hidden = true;
        fallback.disabled = true;
      }
      const input = dropdown.querySelector('input[type="hidden"]');
      if (input) input.disabled = false;
    });
    root.querySelectorAll("details.swap-dropdown").forEach((dropdown) => {
      if (dropdown.dataset.dropdownReady) return;
      const trigger = dropdown.querySelector("summary");
      const input = dropdown.querySelector('input[type="hidden"]');
      const options = Array.from(dropdown.querySelectorAll(".swap-dropdown-option"));
      if (!trigger || !input || options.length === 0) return;
      dropdown.dataset.dropdownReady = "true";
      input.dataset.dropdownDefault = input.value;
      synchronize(dropdown);
      options.forEach((option) => {
        option.addEventListener("click", () => {
          input.value = option.dataset.value;
          dropdown.open = false;
          synchronize(dropdown);
          trigger.focus();
          input.dispatchEvent(new Event("change", { bubbles: true }));
        });
      });
      input.addEventListener("change", () => synchronize(dropdown));
      dropdown.addEventListener("toggle", () => synchronize(dropdown));
      dropdown.closest("form")?.addEventListener("reset", () => {
        queueMicrotask(() => {
          input.value = input.dataset.dropdownDefault ?? input.defaultValue;
          dropdown.open = false;
          synchronize(dropdown);
        });
      });
      trigger.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
        event.preventDefault();
        dropdown.open = true;
        const selected = options.find((option) => option.getAttribute("aria-selected") === "true");
        (selected || options[event.key === "ArrowDown" ? 0 : options.length - 1]).focus();
      });
      dropdown.addEventListener("keydown", (event) => {
        if (event.key === "Tab") {
          setTimeout(() => {
            if (!dropdown.contains(document.activeElement)) dropdown.open = false;
          }, 0);
          return;
        }
        if (event.key === "Escape" && dropdown.open) {
          event.preventDefault();
          event.stopPropagation();
          dropdown.open = false;
          trigger.focus();
          return;
        }
        const index = options.indexOf(document.activeElement);
        if (index < 0) return;
        let next = index;
        if (event.key === "ArrowDown") next = (index + 1) % options.length;
        else if (event.key === "ArrowUp") next = (index - 1 + options.length) % options.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = options.length - 1;
        else return;
        event.preventDefault();
        options[next].focus();
      });
    });
  };
  document.addEventListener("click", (event) => {
    document.querySelectorAll("details.swap-dropdown[open]").forEach((dropdown) => {
      if (!dropdown.contains(event.target)) dropdown.open = false;
    });
  });
  window.SwapDropdown = {
    init,
    sync(root = document) {
      root.querySelectorAll("details.swap-dropdown").forEach((dropdown) => {
        const input = dropdown.querySelector('input[type="hidden"]');
        if (input) input.dataset.dropdownDefault = input.value;
        synchronize(dropdown);
      });
    },
  };
  init();
})();
