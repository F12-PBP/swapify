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
  };
  scene.addEventListener('pointermove', (event) => {
    if (motion.matches || !finePointer.matches) return;
    const bounds = scene.getBoundingClientRect();
    scene.style.setProperty('--pointer-x', `${(event.clientX - bounds.left - bounds.width / 2) / 30}px`);
  });
  scene.addEventListener('pointerleave', reset);
  let greetingAnimation = null;
  motion.addEventListener('change', () => { reset(); if (motion.matches) greetingAnimation?.finish(); });
  const greeting = scene.querySelector('[data-hero-greet]');
  greeting.addEventListener('click', async () => {
    scene.querySelector('[data-hero-status]').textContent = "Swapy says hello! Ready to find your next favourite?";
    if (motion.matches) return;
    greeting.disabled = true;
    const mascot = scene.querySelector('[data-hero-mascot]');
    const shadow = scene.querySelector('[data-hero-shadow]');
    const loops = [...mascot.getAnimations({ subtree: true }), ...shadow.getAnimations()];
    loops.forEach((animation) => animation.pause());
    const resting = getComputedStyle(mascot).transform;
    const animation = mascot.animate([
      { transform: resting },
      { transform: 'translateY(-22%) rotate(-5deg)', offset: .4 },
      { transform: 'translateY(0) scale(1.035, .965)', offset: .75 },
      { transform: resting },
    ], { duration: 900, easing: 'cubic-bezier(.4, 0, .2, 1)' });
    const shadowResting = getComputedStyle(shadow);
    const shadowAnimation = shadow.animate([
      { transform: shadowResting.transform, opacity: shadowResting.opacity },
      { transform: 'scale(.65, .75)', opacity: .4, offset: .4 },
      { transform: 'scale(1)', opacity: 1, offset: .75 },
      { transform: shadowResting.transform, opacity: shadowResting.opacity },
    ], { duration: 900, easing: 'cubic-bezier(.4, 0, .2, 1)' });
    greetingAnimation = animation;
    await animation.finished.catch(() => {});
    shadowAnimation.cancel();
    const bounds = scene.getBoundingClientRect();
    if (!motion.matches && !document.hidden && bounds.bottom > 0 && bounds.top < innerHeight) loops.forEach((loop) => loop.play());
    greetingAnimation = null;
    greeting.disabled = false;
  });
})();

(() => {
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const reveals = new Set();
  const revealObserver = new IntersectionObserver((entries) => {
    entries.filter((entry) => entry.isIntersecting).forEach(({ target }) => {
      revealObserver.unobserve(target);
      if (motion.matches) return;
      const siblings = [...target.parentElement.children].filter((node) => node.hasAttribute('data-reveal'));
      const animation = target.animate([
        { opacity: 0, transform: 'translateY(20px)' },
        { opacity: 1, transform: 'translateY(0)' },
      ], { duration: 650, delay: Math.max(0, siblings.indexOf(target)) * 65, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'both' });
      reveals.add(animation);
      animation.finished.then(() => { animation.cancel(); reveals.delete(animation); }).catch(() => reveals.delete(animation));
    });
  }, { threshold: .05 });
  document.querySelectorAll('[data-reveal]').forEach((node) => revealObserver.observe(node));

  const sections = [...document.querySelectorAll('main section')].map((section) => ({
    section, visible: false, nodes: [...section.querySelectorAll('[data-ambient], [class*="animate-journey-"]')],
  })).filter(({ nodes }) => nodes.length);
  const playback = ({ visible, nodes }) => nodes.forEach((node) => {
    node.style.animationPlayState = visible && !document.hidden ? 'running' : 'paused';
  });
  const ambientObserver = new IntersectionObserver((entries) => entries.forEach((entry) => {
    const record = sections.find(({ section }) => section === entry.target);
    record.visible = entry.isIntersecting;
    playback(record);
  }));
  sections.forEach((record) => { playback(record); ambientObserver.observe(record.section); });
  document.addEventListener('visibilitychange', () => sections.forEach(playback));
  motion.addEventListener('change', () => { if (motion.matches) reveals.forEach((animation) => animation.finish()); });

  document.querySelectorAll('[data-journey-action]').forEach((button) => {
    button.addEventListener('click', () => {
      if (!motion.matches) {
        button.querySelector('svg').getAnimations({ subtree: true }).forEach((animation) => {
          const duration = animation.effect.getTiming().duration;
          if (typeof duration === 'number' && duration > 1000) animation.currentTime = duration * Number(button.dataset.journeyAction);
        });
      }
      document.querySelector('[data-journey-status]').textContent = `${button.getAttribute('aria-label')}. This is a demonstration of the process.`;
    });
  });
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
  const routeLength = route.getTotalLength();
  let mapWidth = scene.clientWidth;
  let mapHeight = scene.clientHeight;
  let visible = false;
  let frame = null;
  let current = 0;
  let target = 0;
  let lastTime = 0;
  const animated = () => desktop.matches && !motion.matches;

  const render = () => {
    const depth = animated() ? current - .5 : 0;
    scene.style.setProperty('--map-x', `${depth * -36}px`);
    scene.style.setProperty('--map-y', `${depth * -80}px`);
    const worldX = depth * 16;
    const worldY = depth * -28;
    const worldScale = animated() ? 1 + current * .025 : 1;
    scene.style.setProperty('--world-x', `${worldX}px`);
    scene.style.setProperty('--world-y', `${worldY}px`);
    scene.style.setProperty('--world-scale', String(worldScale));
    scene.style.setProperty('--landmark-x', `${depth * 32}px`);
    scene.style.setProperty('--landmark-y', `${depth * -112}px`);
    scene.style.setProperty('--card-drift', `${depth * -36}px`);
    route.style.strokeDasharray = '1';
    route.style.strokeDashoffset = String(1 - current);
    const point = route.getPointAtLength(routeLength * current);
    const x = ((point.x / 880 - .5) * worldScale + .5) * mapWidth + worldX;
    const y = ((point.y / 650 - .5) * worldScale + .5) * mapHeight + worldY;
    car.style.setProperty('--car-x', `${x}px`);
    car.style.setProperty('--car-y', `${y}px`);
    steps.forEach((step, index) => {
      const active = String(!animated() || index === Math.round(current * (steps.length - 1)));
      if (step.dataset.active !== active) step.dataset.active = active;
    });
  };
  const tick = (time) => {
    const elapsed = Math.min(64, lastTime ? time - lastTime : 16);
    lastTime = time;
    current += (target - current) * (1 - Math.exp(-elapsed / 120));
    if (Math.abs(target - current) < .0001) current = target;
    render();
    frame = current !== target && visible ? requestAnimationFrame(tick) : null;
  };
  const update = () => {
    if (animated()) {
      const centers = steps.map((step) => {
        const bounds = step.getBoundingClientRect();
        return bounds.top + bounds.height / 2;
      });
      target = Math.max(0, Math.min(1, (innerHeight * .55 - centers[0]) / (centers[centers.length - 1] - centers[0])));
    } else {
      target = 1;
    }
    if (!animated() || !visible) {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      current = target;
      render();
    } else if (frame === null) {
      lastTime = 0;
      frame = requestAnimationFrame(tick);
    }
  };
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    update();
  }).observe(story);
  window.addEventListener('scroll', () => { if (visible) update(); }, { passive: true });
  const resize = () => {
    mapWidth = scene.clientWidth;
    mapHeight = scene.clientHeight;
    scene.style.setProperty('--map-width', `${mapWidth}px`);
    update();
  };
  window.addEventListener('resize', resize, { passive: true });
  motion.addEventListener('change', update);
  desktop.addEventListener('change', update);
  resize();
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
