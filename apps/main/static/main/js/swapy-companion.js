(() => {
  const companion = document.querySelector("[data-swapy-companion]");
  const toggle = document.querySelector("[data-swapy-toggle]");
  if (!companion || !toggle || companion.dataset.ready) return;
  companion.dataset.ready = "true";

  const flying = companion.querySelector("[data-swapy-flying]");
  const greeting = companion.querySelector("[data-swapy-greeting]");
  const facing = companion.querySelector("[data-swapy-facing]");
  const finePointer = matchMedia("(any-hover: hover) and (any-pointer: fine)");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const preferenceKey = "swapify:swapy-hidden";
  let optedOut = false;
  try {
    optedOut = localStorage.getItem(preferenceKey) === "true";
  } catch {
    // The companion still works when browser storage is unavailable.
  }

  let enabled = false;
  let visible = false;
  let frame = 0;
  let lastFrame = 0;
  let lastMove = 0;
  let idleTimer = 0;
  let fadeTimer = 0;
  let x = 0;
  let y = 0;
  let targetX = 0;
  let targetY = 0;
  let pointerX = null;
  let pointerY = null;
  let direction = 1;

  const setFlying = (moving) => {
    flying.style.opacity = moving ? "1" : "0";
    greeting.style.opacity = moving ? "0" : "1";
  };

  const stop = () => {
    visible = false;
    pointerX = null;
    pointerY = null;
    cancelAnimationFrame(frame);
    frame = 0;
    clearTimeout(idleTimer);
    clearTimeout(fadeTimer);
    companion.style.opacity = "0";
    fadeTimer = setTimeout(() => {
      companion.hidden = true;
      flying.removeAttribute("src");
      greeting.removeAttribute("src");
    }, 200);
  };

  const updateAvailability = () => {
    const available = finePointer.matches && !reducedMotion.matches;
    enabled = available && !optedOut;
    toggle.hidden = !available;
    toggle.textContent = optedOut ? "Show Swapy" : "Hide Swapy";
    toggle.setAttribute("aria-pressed", String(!optedOut));
    if (!enabled) stop();
  };

  const updateTarget = () => {
    const width = companion.offsetWidth;
    const height = companion.offsetHeight;
    const desiredX = pointerX < innerWidth / 2
      ? pointerX + 8
      : pointerX - width - 8;
    targetX = Math.max(8, Math.min(innerWidth - width - 8, desiredX));
    targetY = Math.max(8, Math.min(innerHeight - height - 8, pointerY + 1));
  };

  const animate = (now) => {
    const elapsed = Math.min(now - lastFrame, 64);
    lastFrame = now;
    const blend = 1 - Math.exp(-elapsed / 110);
    x += (targetX - x) * blend;
    y += (targetY - y) * blend;
    companion.style.transform = `translate3d(${x}px, ${y}px, 0)`;

    const settled = Math.hypot(targetX - x, targetY - y) < 0.25;
    if (!settled) {
      frame = requestAnimationFrame(animate);
      return;
    }

    frame = 0;
    const idleDelay = Math.max(0, 220 - (now - lastMove));
    idleTimer = setTimeout(() => setFlying(false), idleDelay);
  };

  const startFollowing = () => {
    clearTimeout(idleTimer);
    setFlying(true);
    if (!frame) {
      lastFrame = performance.now();
      frame = requestAnimationFrame(animate);
    }
  };

  document.addEventListener("pointermove", (event) => {
    if (!enabled || document.hidden || event.pointerType !== "mouse") return;
    const now = performance.now();
    const deltaX = pointerX === null ? 0 : event.clientX - pointerX;
    if (Math.abs(deltaX) > 2) {
      direction = deltaX > 0 ? 1 : -1;
      facing.style.transform = `scaleX(${direction})`;
    }
    pointerX = event.clientX;
    pointerY = event.clientY;
    lastMove = now;

    if (!visible) {
      clearTimeout(fadeTimer);
      companion.hidden = false;
      flying.src = companion.dataset.flyingSrc;
      greeting.src = companion.dataset.greetingSrc;
      visible = true;
      updateTarget();
      x = targetX;
      y = targetY;
      companion.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      companion.style.opacity = "1";
    } else {
      updateTarget();
    }
    startFollowing();
  }, { passive: true });

  document.documentElement.addEventListener("pointerleave", stop);
  document.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "touch") stop();
  }, { passive: true });
  window.addEventListener("blur", stop);
  window.addEventListener("pagehide", stop);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
  });
  window.addEventListener("resize", () => {
    if (!visible) return;
    updateTarget();
    startFollowing();
  });

  toggle.addEventListener("click", () => {
    optedOut = !optedOut;
    try {
      localStorage.setItem(preferenceKey, String(optedOut));
    } catch {
      // Keep the selection for this page if persistence is blocked.
    }
    updateAvailability();
  });
  window.addEventListener("storage", (event) => {
    if (event.key !== preferenceKey && event.key !== null) return;
    optedOut = event.newValue === "true";
    updateAvailability();
  });
  finePointer.addEventListener("change", updateAvailability);
  reducedMotion.addEventListener("change", updateAvailability);
  updateAvailability();
})();
