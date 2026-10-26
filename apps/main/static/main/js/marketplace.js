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
    dialog.addEventListener("click", (event) => {
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
  document.querySelectorAll("[data-auto-submit]").forEach((select) => {
    select.addEventListener("change", () => select.form.requestSubmit());
  });
})();
