document.querySelectorAll("details.swap-dropdown").forEach((dropdown) => {
  const trigger = dropdown.querySelector("summary");
  const label = dropdown.querySelector(".swap-dropdown-value");
  const valueInput = dropdown.querySelector('input[type="hidden"]');
  const options = Array.from(dropdown.querySelectorAll(".swap-dropdown-option"));

  if (!trigger || !label || !valueInput || options.length === 0) return;

  options.forEach((option) => {
    option.addEventListener("click", () => {
      label.textContent = option.textContent.trim();
      valueInput.value = option.dataset.value;
      dropdown.classList.add("is-filled");
      options.forEach((item) => {
        item.setAttribute("aria-selected", String(item === option));
      });
      if (trigger.hasAttribute("aria-label")) {
        trigger.setAttribute("aria-label", `Kategori: ${label.textContent}`);
      }
      dropdown.open = false;
      valueInput.dispatchEvent(new Event("change", { bubbles: true }));
      trigger.focus();
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
    if (event.key === "Escape") {
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

document.addEventListener("click", (event) => {
  document.querySelectorAll("details.swap-dropdown[open]").forEach((dropdown) => {
    if (!dropdown.contains(event.target)) dropdown.open = false;
  });
});
