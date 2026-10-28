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
  const mascot = demo.querySelector('[data-demo-mascot]');
  const figures = [...demo.querySelectorAll('[data-demo-piece]')];
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let animations = [];
  let busy = false;

  const render = () => {
    [yours, theirs].forEach((input, index) => {
      const piece = pieces.find((item) => item.key === input.value);
      const image = figures[index].querySelector('img');
      if (image.getAttribute('src') !== piece.image) image.src = piece.image;
      image.alt = `${index === 0 ? 'Your' : 'Their'} demo piece: ${piece.label}`;
    });
    window.SwapDropdown?.sync(demo);
  };
  const celebrate = (complete) => {
    mascot.dataset.complete = String(complete);
    reset.disabled = !complete;
  };
  const finish = () => animations.forEach((animation) => animation.finish());

  demo.addEventListener('change', () => {
    if (busy) return;
    render();
    celebrate(false);
    result.textContent = 'Demo choices updated.';
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
    celebrate(false);
    demo.querySelectorAll('[data-demo-picker]').forEach((picker) => { picker.inert = true; });
    const images = figures.map((figure) => figure.querySelector('img'));
    const before = images.map((image) => image.getBoundingClientRect());

    [yours.value, theirs.value] = [theirs.value, yours.value];
    figures[0].replaceChildren(images[1]);
    figures[1].replaceChildren(images[0]);
    render();

    if (!motion.matches) {
      animations = images.map((image, index) => {
        const after = image.getBoundingClientRect();
        const x = before[index].left - after.left;
        const y = before[index].top - after.top;
        const scaleX = before[index].width / after.width;
        const scaleY = before[index].height / after.height;
        return image.animate([
          { transform: `translate(${x}px, ${y}px) scale(${scaleX}, ${scaleY})` },
          { transform: `translate(${x / 2}px, ${y / 2 + (index ? 28 : -28)}px) rotate(${index ? -4 : 4}deg)`, offset: .5 },
          { transform: 'translate(0, 0) scale(1) rotate(0)' },
        ], { duration: 950, easing: 'cubic-bezier(.4, 0, .2, 1)', fill: 'both' });
      });
      await Promise.allSettled(animations.map((animation) => animation.finished));
    }

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
    if (motion.matches) finish();
  });
  window.addEventListener('resize', finish, { passive: true });
})();

(() => {
  const story = document.querySelector('[data-map-story]');
  if (!story) return;
  const scene = story.querySelector('[data-map-scene]');
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
    const point = route.getPointAtLength(route.getTotalLength() * (.08 + connection * .84));
    car.style.left = `${point.x / 880 * 100}%`;
    car.style.top = `${(point.y + 70) / 650 * 100}%`;
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
    journey.querySelectorAll('[data-journey-step]').forEach((step) => { step.dataset.arrived = 'true'; });
    observer.disconnect();
  }, { threshold: .2 });
  observer.observe(journey);
})();

(() => {
  const items = [...document.querySelectorAll('[data-faq-item]')];
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const running = new Map();

  const expand = (item, expanded) => {
    const summary = item.querySelector('summary');
    const answer = item.querySelector('[data-faq-answer]');
    const from = item.getBoundingClientRect().height;
    const opacity = getComputedStyle(answer).opacity;
    const previous = running.get(item);
    previous?.height.cancel();
    previous?.content.cancel();
    running.delete(item);
    item.open = true;
    item.dataset.expanded = String(expanded);
    summary.setAttribute('aria-expanded', String(expanded));

    if (motion.matches) {
      item.open = expanded;
      return;
    }

    const border = getComputedStyle(item);
    const collapsed = summary.getBoundingClientRect().height + parseFloat(border.borderTopWidth) + parseFloat(border.borderBottomWidth);
    const to = expanded ? item.getBoundingClientRect().height : collapsed;
    const height = item.animate([{ height: `${from}px` }, { height: `${to}px` }], {
      duration: 360, easing: 'cubic-bezier(.25, .8, .25, 1)', fill: 'both',
    });
    const content = answer.animate([{ opacity }, { opacity: expanded ? 1 : 0 }], {
      duration: 240, easing: 'ease-out', fill: 'both',
    });
    running.set(item, { height, content });
    height.finished.then(() => {
      if (running.get(item)?.height !== height) return;
      item.open = expanded;
      height.cancel();
      content.cancel();
      running.delete(item);
    }).catch(() => {});
  };

  items.forEach((item) => {
    item.dataset.expanded = String(item.open);
    const summary = item.querySelector('summary');
    summary.setAttribute('aria-expanded', String(item.open));
    summary.addEventListener('click', (event) => {
      event.preventDefault();
      const expanded = item.dataset.expanded !== 'true';
      if (expanded) {
        items.filter((other) => other !== item && other.dataset.expanded === 'true').forEach((other) => expand(other, false));
      }
      expand(item, expanded);
    });
  });
  const finish = () => running.forEach(({ height, content }) => {
    height.finish();
    content.finish();
  });
  window.addEventListener('resize', finish, { passive: true });
  motion.addEventListener('change', () => {
    if (motion.matches) finish();
  });
})();
