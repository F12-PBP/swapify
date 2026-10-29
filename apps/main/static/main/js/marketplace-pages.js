(() => {
  const main = document.getElementById("main-content");
  const assets = document.getElementById("market-page-assets");
  const dialogs = document.getElementById("market-page-dialogs");
  const navbar = document.querySelector("[data-market-navbar]");
  if (!main || !assets || !dialogs || !navbar) return;

  const definitions = new Map();
  const loaded = new Set([...document.scripts].filter((script) => script.src).map((script) => new URL(script.src).pathname));
  const loadingScripts = new Map();
  let navigation;
  let revision = 0;
  let pagePath = location.pathname;
  let currentURL = new URL(location.href);
  let ready = document.readyState === "complete";
  document.addEventListener("DOMContentLoaded", () => { ready = true; }, { once: true });

  const createPage = () => {
    const lifecycle = new AbortController();
    const cleanups = [];
    const waits = [];
    const timers = new Set();
    return {
      signal: lifecycle.signal,
      on(target, type, handler, options = {}) {
        target?.addEventListener(type, handler, { ...options, signal: lifecycle.signal });
      },
      cleanup(callback) { cleanups.push(callback); },
      beforeLeave(callback) { waits.push(callback); },
      locationChanged() { currentURL = new URL(location.href); pagePath = location.pathname; },
      whenIdle() { return Promise.all(waits.map((callback) => callback())); },
      timeout(callback, delay) {
        const id = setTimeout(() => { timers.delete(id); callback(); }, delay);
        timers.add(id);
        return id;
      },
      clearTimeout(id) { timers.delete(id); clearTimeout(id); },
      async fetch(url, options = {}) {
        const controller = new AbortController();
        const signals = [lifecycle.signal, options.signal].filter(Boolean);
        const abort = () => controller.abort();
        signals.forEach((signal) => {
          if (signal.aborted) abort();
          else signal.addEventListener("abort", abort, { once: true });
        });
        const release = () => signals.forEach((signal) => signal.removeEventListener("abort", abort));
        try {
          const response = await fetch(url, { ...options, signal: controller.signal });
          // Retain cancellation through response-body parsing, too.
          for (const method of ["json", "text"]) {
            const read = response[method].bind(response);
            response[method] = async () => {
              try {
                const value = await read();
                if (controller.signal.aborted) throw new DOMException("Request cancelled", "AbortError");
                return value;
              } finally { release(); }
            };
          }
          return response;
        } catch (error) { release(); throw error; }
      },
      destroy() {
        if (lifecycle.signal.aborted) return;
        lifecycle.abort();
        timers.forEach(clearTimeout);
        window.SwapifyMotion?.reset(main);
        window.SwapifyMotion?.reset(dialogs);
        window.SwapLocation?.destroy(main);
        window.SwapLocation?.destroy(dialogs);
        cleanups.reverse().forEach((cleanup) => cleanup());
      },
    };
  };
  let page = createPage();
  const restoration = history.scrollRestoration;
  history.scrollRestoration = "manual";
  window.addEventListener("pagehide", () => { history.scrollRestoration = restoration; });
  window.addEventListener("pageshow", () => { history.scrollRestoration = "manual"; });
  window.MarketplacePages = {
    register(initialize) {
      const key = new URL(document.currentScript.src).pathname;
      definitions.set(key, initialize);
      if (document.currentScript.dataset.marketDynamic !== "true") initialize(page);
    },
  };

  const notify = (name, url) => document.dispatchEvent(new CustomEvent(`marketplace:${name}`, { detail: { url } }));
  const status = document.createElement("p");
  status.className = "sr-only";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  main.before(status);
  const notice = document.createElement("p");
  notice.className = "market-container py-3 text-b8 text-red-base";
  notice.setAttribute("role", "alert");
  notice.hidden = true;
  main.before(notice);

  const loadScript = async (source) => {
    const url = new URL(source, location.href);
    if (url.origin !== location.origin) throw new Error("External page script");
    if (loaded.has(url.pathname)) return;
    if (loadingScripts.has(url.pathname)) return loadingScripts.get(url.pathname);
    const loading = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.dataset.marketDynamic = "true";
      script.src = url.href;
      script.onload = resolve;
      script.onerror = () => { script.remove(); reject(new Error("Page script unavailable")); };
      assets.append(script);
    }).then(() => loaded.add(url.pathname)).finally(() => loadingScripts.delete(url.pathname));
    loadingScripts.set(url.pathname, loading);
    return loading;
  };

  const syncHeader = (document) => {
    const nextLinks = [...document.querySelectorAll("[data-market-tabs] .market-nav")];
    navbar.querySelectorAll(".market-nav").forEach((link, index) => {
      const next = nextLinks[index];
      link.className = next.className;
      link.href = next.href;
      if (next.hasAttribute("aria-current")) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    const form = navbar.querySelector('form[role="search"]');
    const next = document.querySelector('[data-market-navbar] form[role="search"]');
    form.action = next.action;
    const input = form.querySelector("#market-search");
    const nextInput = next.querySelector("#market-search");
    input.value = nextInput.value;
    input.placeholder = nextInput.placeholder;
    input.removeAttribute("aria-controls");
    form.querySelector("label").textContent = next.querySelector("label").textContent;
    form.querySelector("button").setAttribute("aria-label", next.querySelector("button").getAttribute("aria-label"));
    form.querySelectorAll('input[type="hidden"]').forEach((field) => field.remove());
    next.querySelectorAll('input[type="hidden"]').forEach((field) => form.append(field.cloneNode(true)));
  };

  const navigate = async (url, { push = true, focus = false } = {}) => {
    navigation?.abort();
    const request = ++revision;
    const controller = new AbortController();
    navigation = controller;
    const previousURL = new URL(location.href);
    let committed = false;
    const timeout = setTimeout(() => controller.abort(), 15000);
    notice.hidden = true;
    status.textContent = "Opening page…";
    main.setAttribute("aria-busy", "true");
    notify("pending", url);
    try {
      await page.whenIdle();
      if (request !== revision) return;
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store", signal: controller.signal, headers: { Accept: "text/html" } });
      if (request !== revision) return;
      if (response.redirected || [401, 403, 404].includes(response.status)) {
        location.assign(response.redirected ? response.url : url);
        return;
      }
      if (!response.ok) throw new Error("Page unavailable");
      const nextDocument = new DOMParser().parseFromString(await response.text(), "text/html");
      const nextMain = nextDocument.getElementById("main-content");
      const nextAssets = nextDocument.getElementById("market-page-assets");
      const nextDialogs = nextDocument.getElementById("market-page-dialogs");
      if (!nextMain || !nextAssets || !nextDialogs) { location.assign(url); return; }
      const scripts = [...nextAssets.querySelectorAll("script[src]")].map((script) => script.src);
      {
        for (const source of scripts) await loadScript(source);
        for (const nextLink of nextDocument.querySelectorAll('head link[rel="stylesheet"]')) {
          const href = new URL(nextLink.getAttribute("href"), url).href;
          if ([...document.querySelectorAll('link[rel="stylesheet"]')].some((link) => link.href === href)) continue;
          await new Promise((resolve, reject) => {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = href;
            link.onload = resolve;
            link.onerror = () => { link.remove(); reject(new Error("Page styles unavailable")); };
            document.head.append(link);
          });
        }
      }
      if (request !== revision) return;
      await page.whenIdle();
      if (request !== revision) return;
      committed = true;
      page.destroy();
      dialogs.querySelectorAll("dialog[open]").forEach((dialog) => dialog.close());
      document.documentElement.classList.remove("market-dialog-open");
      page = createPage();
      if (push) history.pushState(null, "", url);
      currentURL = new URL(url);
      pagePath = url.pathname;
      syncHeader(nextDocument);
      main.className = nextMain.className;
      main.replaceChildren(...nextMain.childNodes);
      dialogs.replaceChildren(...nextDialogs.childNodes);
      document.title = nextDocument.title;
      window.SwapDropdown?.init(main);
      window.SwapDropdown?.init(dialogs);
      window.SwapLocation?.init();
      for (const source of scripts) definitions.get(new URL(source, url).pathname)?.(page);
      window.SwapifyMotion?.page(main);
      const anchor = url.hash && document.getElementById(url.hash.slice(1));
      if (anchor && main.contains(anchor)) anchor.scrollIntoView({ block: "start", behavior: "instant" });
      else window.scrollTo({ top: 0, behavior: "instant" });
      notify("ready", url);
      status.textContent = document.title;
      if (focus) {
        const heading = main.querySelector("h1");
        if (heading) { heading.setAttribute("tabindex", "-1"); heading.focus({ preventScroll: true }); }
      }
    } catch (error) {
      if (request !== revision) return;
      console.error("Marketplace navigation failed", error);
      if (committed || page.signal.aborted) { location.assign(url); return; }
      notice.textContent = "We couldn’t open that page. Your current page is still available; select the tab again to retry.";
      notice.hidden = false;
      status.textContent = "Page could not be loaded.";
      if (!push) history.replaceState(null, "", currentURL);
      else currentURL = previousURL;
      notify("error", currentURL);
    } finally {
      clearTimeout(timeout);
      if (request === revision) main.removeAttribute("aria-busy");
    }
  };

  document.addEventListener("click", (event) => {
    if (!ready) return;
    const link = event.target.closest(".market-nav");
    if (!link || !navbar.contains(link) || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin) return;
    event.preventDefault();
    if (url.href !== location.href) navigate(url, { focus: event.detail === 0 });
  });
  document.addEventListener("submit", (event) => {
    if (!ready) return;
    if (event.defaultPrevented || event.target !== navbar.querySelector('form[role="search"]')) return;
    event.preventDefault();
    const url = new URL(event.target.action);
    url.search = new URLSearchParams(new FormData(event.target));
    navigate(url);
  });
  window.addEventListener("popstate", (event) => {
    if (location.pathname === pagePath) return;
    if (main.querySelector("[data-chat-root]") && /^\/chat\/(\d+\/)?$/.test(location.pathname)) return;
    event.stopImmediatePropagation();
    navigate(new URL(location.href), { push: false });
  }, { capture: true });
})();
