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
})();
