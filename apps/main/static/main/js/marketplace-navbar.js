(() => {
  const navbar = document.querySelector("[data-market-navbar]");
  if (!navbar) return;

  // Keep anchor navigation and catalog pagination below the sticky navbar,
  // including when the search and navigation rows wrap on smaller screens.
  const updateOffset = () => {
    document.documentElement.style.setProperty("--market-navbar-height", `${navbar.getBoundingClientRect().height}px`);
  };
  updateOffset();
  new ResizeObserver(updateOffset).observe(navbar);

  const search = navbar.querySelector("#market-search");
  search?.addEventListener("pointerdown", (event) => {
    if (document.activeElement === search || event.button !== 0) return;
    event.preventDefault();
    search.focus({ preventScroll: true });
  });

  const marquee = navbar.querySelector("[data-market-marquee]");
  const toggle = marquee?.querySelector("[data-marquee-toggle]");
  if (toggle) {
    toggle.hidden = false;
    toggle.addEventListener("click", () => {
      const paused = toggle.getAttribute("aria-pressed") !== "true";
      toggle.setAttribute("aria-pressed", String(paused));
      toggle.setAttribute("aria-label", paused ? "Resume announcements" : "Pause announcements");
      marquee.dataset.paused = String(paused);
      toggle.querySelector("[data-marquee-pause]").hidden = paused;
      toggle.querySelector("[data-marquee-play]").hidden = !paused;
    });
  }
})();
