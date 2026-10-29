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

  const tabs = navbar.querySelector("[data-market-tabs]");
  const links = [...tabs.querySelectorAll(".market-nav")];
  const active = tabs.querySelector('[aria-current="page"]');
  if (active) {
    const indicator = document.createElement("span");
    indicator.className = "pointer-events-none absolute bottom-0 left-0 h-0.5 bg-primary-base";
    indicator.setAttribute("aria-hidden", "true");
    tabs.append(indicator);
    tabs.dataset.indicatorReady = "true";
    const position = (link) => ({ x: link.offsetLeft, width: link.offsetWidth });
    const place = () => {
      const target = position(active);
      indicator.style.width = `${target.width}px`;
      indicator.style.transform = `translateX(${target.x}px)`;
      if (target.x < tabs.scrollLeft) tabs.scrollLeft = target.x;
      else if (target.x + target.width > tabs.scrollLeft + tabs.clientWidth) {
        tabs.scrollLeft = target.x + target.width - tabs.clientWidth;
      }
    };
    place();
    try {
      const previous = JSON.parse(sessionStorage.getItem("swapify:market-tab") || "null");
      sessionStorage.removeItem("swapify:market-tab");
      if (previous?.path === location.pathname && Date.now() - previous.time < 10000 && links[previous.index]) {
        const from = position(links[previous.index]);
        const to = position(active);
        window.SwapifyMotion?.play(indicator, [
          { transform: `translateX(${from.x}px)`, width: `${from.width}px` },
          { transform: `translateX(${to.x}px)`, width: `${to.width}px` },
        ]);
      }
    } catch { /* Navigation also works without browser storage. */ }
    tabs.addEventListener("click", (event) => {
      const link = event.target.closest(".market-nav");
      if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      try {
        sessionStorage.setItem("swapify:market-tab", JSON.stringify({
          index: links.indexOf(active), path: new URL(link.href).pathname, time: Date.now(),
        }));
      } catch { /* Keep ordinary links usable when storage is blocked. */ }
    });
    new ResizeObserver(place).observe(tabs);
    document.fonts?.ready.then(place);
    window.addEventListener("pageshow", (event) => { if (event.persisted) place(); });
  }

  const signInDialog = document.querySelector("#add-item-signin");
  navbar.querySelector("[data-add-item-signin]")?.addEventListener("click", (event) => {
    if (!signInDialog?.showModal || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    signInDialog.showModal();
  });

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
