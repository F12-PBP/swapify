(() => {
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const running = new Set();
  const byElement = new WeakMap();
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
  const reveal = (element, options = {}) => play(element, [
    { opacity: 0, transform: "translateY(10px)" },
    { opacity: 1, transform: "translateY(0)" },
  ], options);
  window.SwapifyMotion = { play, reveal };
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) running.forEach((animation) => animation.cancel());
  });

  document.querySelectorAll("main > *").forEach((element, index) => {
    if (element.matches("script, style, dialog") ||
        element.matches('[class*="animate-profile-reveal"], [class*="animate-landing"]') ||
        element.querySelector('[class*="animate-profile-reveal"], [class*="animate-landing"]')) return;
    if (element.querySelector("[data-chat-root]")) {
      element.querySelectorAll(".chat-pane, .chat-sidebar, .chat-placeholder").forEach((pane) => reveal(pane));
      return;
    }
    reveal(element, { duration: 560, delay: Math.min(index * 45, 135) });
  });
})();
