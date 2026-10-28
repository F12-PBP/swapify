(() => {
  document.querySelectorAll('[data-clothing-photo]').forEach((image) => {
    const showFallback = () => {
      image.src = image.dataset.fallback;
      image.classList.replace('object-cover', 'object-contain');
      image.closest('figure').querySelector('[data-photo-note]').hidden = false;
    };
    image.addEventListener('error', showFallback, { once: true });
    if (image.complete && !image.naturalWidth) showFallback();
  });
  const scene = document.querySelector('[data-hero-scene]');
  if (!scene) return;
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const finePointer = window.matchMedia('(pointer: fine)');
  const reset = () => {
    scene.style.removeProperty('--pointer-x');
    scene.style.removeProperty('--pointer-y');
  };
  scene.addEventListener('pointermove', (event) => {
    if (motion.matches || !finePointer.matches) return;
    const bounds = scene.getBoundingClientRect();
    scene.style.setProperty('--pointer-x', `${(event.clientX - bounds.left - bounds.width / 2) / 60}px`);
    scene.style.setProperty('--pointer-y', `${(event.clientY - bounds.top - bounds.height / 2) / 60}px`);
  });
  scene.addEventListener('pointerleave', reset);
  motion.addEventListener('change', reset);
})();
