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
  const indicator = document.createElement("span");
  indicator.className = "pointer-events-none absolute bottom-0 left-0 h-0.5 bg-primary-base";
  indicator.setAttribute("aria-hidden", "true");
  tabs.append(indicator);
  tabs.dataset.indicatorReady = "true";
  let target = tabs.querySelector('[aria-current="page"]');
  const place = (link = target, animate = false) => {
    indicator.hidden = !link;
    if (!link) return;
    const from = { transform: getComputedStyle(indicator).transform, width: getComputedStyle(indicator).width };
    target = link;
    const to = { transform: `translateX(${link.offsetLeft}px)`, width: `${link.offsetWidth}px` };
    indicator.style.transform = to.transform;
    indicator.style.width = to.width;
    if (animate) window.SwapifyMotion?.play(indicator, [from, to]);
    if (link.offsetLeft < tabs.scrollLeft) tabs.scrollLeft = link.offsetLeft;
    else if (link.offsetLeft + link.offsetWidth > tabs.scrollLeft + tabs.clientWidth) {
      tabs.scrollLeft = link.offsetLeft + link.offsetWidth - tabs.clientWidth;
    }
  };
  place();
  new ResizeObserver(() => place()).observe(tabs);
  document.fonts?.ready.then(() => place());
  document.addEventListener("marketplace:pending", (event) => {
    const link = links.find((link) => new URL(link.href).pathname === event.detail.url.pathname);
    if (link) place(link, true);
  });
  const settle = () => {
    const active = tabs.querySelector('[aria-current="page"]');
    place(active, active !== target);
  };
  document.addEventListener("marketplace:ready", settle);
  document.addEventListener("marketplace:error", settle);

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
