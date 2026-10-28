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

(() => {
  const demo = document.querySelector('[data-swap-demo]');
  if (!demo) return;
  const pieces = JSON.parse(document.getElementById('landing-pieces').textContent);
  const yours = demo.querySelector('[name="your_piece"]');
  const theirs = demo.querySelector('[name="their_piece"]');
  const button = demo.querySelector('[data-demo-swap]');
  const reset = demo.querySelector('[data-demo-reset]');
  const result = demo.querySelector('[data-demo-result]');
  const figures = [...demo.querySelectorAll('[data-demo-piece]')];
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let animations = [];
  let busy = false;
  const render = () => {
    [yours, theirs].forEach((input, index) => {
      const piece = pieces.find((item) => item.key === input.value);
      const image = figures[index].querySelector('img');
      image.src = piece.image;
      image.alt = `${index === 0 ? 'Your' : 'Their'} demo piece: ${piece.label}`;
    });
    window.SwapDropdown?.sync(demo);
  };
  const celebrate = (complete) => {
    demo.querySelector('[data-demo-ready]').hidden = complete;
    demo.querySelector('[data-demo-celebrate]').hidden = !complete;
    reset.hidden = !complete;
  };
  demo.addEventListener('change', () => {
    if (busy) return;
    render();
    celebrate(false);
    result.textContent = 'Ready for a different little swap?';
  });
  reset.addEventListener('click', () => {
    yours.value = 'knit';
    theirs.value = 'jacket';
    render();
    celebrate(false);
    result.textContent = 'Demo reset. Choose two pieces to try again.';
    button.focus({ preventScroll: true });
  });
  button.disabled = false;
  button.addEventListener('click', async () => {
    if (busy) return;
    busy = true;
    button.disabled = true;
    demo.querySelectorAll('[data-demo-picker]').forEach((picker) => { picker.inert = true; });
    reset.hidden = true;
    const bounds = figures.map((figure) => figure.getBoundingClientRect());
    if (!motion.matches) {
      animations = figures.map((figure, index) => {
        const destination = bounds[1 - index];
        return figure.animate([
          { transform: 'translate(0, 0) rotate(0)' },
          { transform: `translate(${destination.x - bounds[index].x}px, ${destination.y - bounds[index].y}px) rotate(${index ? -8 : 8}deg)` },
        ], { duration: 650, easing: 'cubic-bezier(.45, 0, .2, 1)', fill: 'forwards' });
      });
      await Promise.allSettled(animations.map((animation) => animation.finished));
    }
    [yours.value, theirs.value] = [theirs.value, yours.value];
    render();
    animations.forEach((animation) => animation.cancel());
    animations = [];
    celebrate(true);
    const received = pieces.find((piece) => piece.key === yours.value).label;
    const given = pieces.find((piece) => piece.key === theirs.value).label;
    result.textContent = `Demo complete! You now have the ${received.toLowerCase()}; they have the ${given.toLowerCase()}.`;
    demo.querySelectorAll('[data-demo-picker]').forEach((picker) => { picker.inert = false; });
    busy = false;
    button.disabled = false;
  });
  motion.addEventListener('change', () => {
    if (motion.matches) animations.forEach((animation) => animation.finish());
  });
})();

(() => {
  const story = document.querySelector('[data-map-story]');
  if (!story) return;
  const scene = story.querySelector('.map-story-scene');
  const route = story.querySelector('[data-map-route]');
  const car = story.querySelector('[data-map-car]');
  const steps = [...story.querySelectorAll('[data-story-step]')];
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const desktop = window.matchMedia('(min-width: 1024px)');
  let visible = false;
  let frame;
  const update = () => {
    frame = null;
    const animated = desktop.matches && !motion.matches;
    const centers = steps.map((step) => {
      const bounds = step.getBoundingClientRect();
      return bounds.top + bounds.height / 2;
    });
    const progress = animated ? Math.max(0, Math.min(1, (innerHeight * .55 - centers[0]) / (centers[2] - centers[0]))) : 1;
    const connection = progress;
    route.style.strokeDasharray = '1';
    route.style.strokeDashoffset = String(1 - connection);
    const point = route.getPointAtLength(route.getTotalLength() * connection);
    car.style.left = `${point.x / 880 * 100}%`;
    car.style.top = `${(point.y + 35) / 650 * 100}%`;
    scene.style.setProperty('--map-drift', `${animated ? progress * -18 : 0}px`);
    steps.forEach((step, index) => { step.dataset.active = String(!animated || index === Math.round(progress * 2)); });
  };
  const schedule = () => {
    if (visible && !frame) frame = requestAnimationFrame(update);
  };
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (visible) update();
  }).observe(story);
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', update, { passive: true });
  motion.addEventListener('change', update);
  desktop.addEventListener('change', update);
  update();
})();

(() => {
  const journey = document.querySelector('[data-landing-journey]');
  if (!journey) return;
  const observer = new IntersectionObserver(([entry]) => {
    if (!entry.isIntersecting) return;
    journey.querySelectorAll('.journey-step').forEach((step) => { step.dataset.arrived = 'true'; });
    observer.disconnect();
  }, { threshold: .2 });
  observer.observe(journey);
})();
