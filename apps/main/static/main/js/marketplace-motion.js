(() => {
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const running = new Set();
  const byElement = new WeakMap();
  const reveals = new Map();
  const play = (element, frames, options = {}) => {
    if (!element || reducedMotion.matches || !element.animate) return;
    byElement.get(element)?.cancel();
    const animation = element.animate(frames, {
      duration: 420,
      easing: "cubic-bezier(.22, 1, .36, 1)",
      ...options,
    });
    running.add(animation);
    byElement.set(element, animation);
    animation.finished.catch(() => {}).finally(() => running.delete(animation));
    return animation;
  };
  const reveal = (element, { duration = 560, delay = 0 } = {}) => {
    if (!element || reducedMotion.matches) return;
    reveals.get(element)?.();
    const previous = element.style.animationDuration;
    const previousDelay = element.style.animationDelay;
    element.classList.remove("motion-safe:animate-profile-reveal");
    void element.offsetWidth;
    element.style.animationDuration = `${duration}ms`;
    element.style.animationDelay = `${delay}ms`;
    element.classList.add("motion-safe:animate-profile-reveal");
    const cleanup = () => {
      element.classList.remove("motion-safe:animate-profile-reveal");
      element.style.animationDuration = previous;
      element.style.animationDelay = previousDelay;
      element.removeEventListener("animationend", finish);
      reveals.delete(element);
    };
    const finish = (event) => { if (event.target === element) cleanup(); };
    reveals.set(element, cleanup);
    element.addEventListener("animationend", finish);
  };

  const page = (main) => {
    if (!main) return;
    if (main.querySelector('[class*="animate-profile-reveal"], [class*="animate-landing"]')) return;
    let groups;
    if (main.querySelector("[data-chat-root]")) {
      groups = main.querySelectorAll(".chat-sidebar > h1, .chat-sidebar > div, [data-chat-rooms], .chat-pane > header, [data-messages], .chat-composer, .chat-placeholder");
    } else if (main.querySelector("[data-catalog]")) {
      const catalog = main.querySelector("[data-catalog]");
      const introduction = catalog.previousElementSibling;
      groups = [...(introduction?.children || []), ...catalog.children,
        ...[...main.children].filter((element) => element !== introduction && element !== catalog)];
    } else if (main.querySelector("[data-my-swaps]")) {
      groups = main.querySelector("[data-my-swaps]").children;
    } else {
      groups = main.children;
    }
    [...groups].filter((element) => !element.hidden && !element.matches('script, style, dialog, [role="status"]')).forEach((element, index) => {
      reveal(element, { delay: Math.min(index * 60, 180) });
    });
  };
  const reset = (root = null) => {
    running.forEach((animation) => {
      if (!root || root.contains(animation.effect.target)) animation.cancel();
    });
    reveals.forEach((cleanup, element) => { if (!root || root.contains(element)) cleanup(); });
  };
  window.SwapifyMotion = { play, reveal, page, reset };
  reducedMotion.addEventListener("change", () => { if (reducedMotion.matches) reset(); });
  const enter = () => {
    document.querySelectorAll('[data-market-entrance]').forEach((element, index) => {
      reveal(element, { delay: index * 60 });
    });
    page(document.querySelector("main"));
  };
  // Initialize after page modules so their layout is ready for the first reveal.
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enter, { once: true });
  else enter();
})();
