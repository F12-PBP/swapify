(() => {
  const region = document.querySelector('[data-toast-region]');
  if (!region) return;
  const template = region.querySelector('[data-toast-template]');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const active = new Map();
  const variants = {
    success: ['bg-green-10', 'text-green-70', 'All set'],
    error: ['bg-red-10', 'text-red-70', 'Something went wrong'],
    warning: ['bg-yellow-10', 'text-yellow-70', 'Please check'],
    info: ['bg-primary-10', 'text-primary-base', 'Swapify'],
  };
  const show = (message, { type = 'info', title } = {}) => {
    const text = String(message || '').trim();
    if (!text) return;
    if (!Object.hasOwn(variants, type)) type = 'info';
    const heading = title || variants[type][2];
    const key = `${type}:${heading}:${text}`;
    if (active.has(key)) return active.get(key).element;
    const element = template.content.firstElementChild.cloneNode(true);
    element.querySelector('[data-toast-icon]').classList.add(...variants[type].slice(0, 2));
    element.querySelector(`[data-toast-symbol="${type}"]`).hidden = false;
    const live = element.querySelector('[data-toast-announcement]');
    live.setAttribute('role', type === 'error' ? 'alert' : 'status');
    live.setAttribute('aria-atomic', 'true');
    let timer;
    let started;
    let remaining = type === 'error' || type === 'warning' ? 0 : 7000;
    let closing = false;
    const pause = () => {
      if (!timer) return;
      clearTimeout(timer);
      timer = undefined;
      remaining -= Date.now() - started;
    };
    const close = () => {
      if (closing) return;
      closing = true;
      pause();
      active.delete(key);
      const finish = () => {
        element.remove();
        if (!region.querySelector('[data-toast]')) {
          if (region.hidePopover && region.matches(':popover-open')) region.hidePopover();
          region.hidden = true;
        }
      };
      if (reducedMotion.matches) finish();
      else element.animate([{ opacity: 1, transform: 'translateY(0)' }, { opacity: 0, transform: 'translateY(-8px)' }], { duration: 160, easing: 'ease-in' }).finished.then(finish, finish);
    };
    const resume = () => {
      if (closing || timer || !remaining || document.hidden || element.matches(':hover') || element.contains(document.activeElement)) return;
      started = Date.now();
      timer = setTimeout(close, Math.max(remaining, 0));
    };
    element.addEventListener('pointerenter', pause);
    element.addEventListener('pointerleave', resume);
    element.addEventListener('focusin', pause);
    element.addEventListener('focusout', () => queueMicrotask(resume));
    element.querySelector('[data-toast-close]').addEventListener('click', close);
    active.set(key, { element, pause, resume });
    region.hidden = false;
    region.append(element);
    if (region.showPopover) {
      if (region.matches(':popover-open')) region.hidePopover();
      region.showPopover();
    }
    element.querySelector('[data-toast-title]').textContent = heading;
    element.querySelector('[data-toast-text]').textContent = text;
    if (!reducedMotion.matches) element.animate([{ opacity: 0, transform: 'translateY(-12px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 300, easing: 'cubic-bezier(.22,1,.36,1)' });
    resume();
    return element;
  };
  const consume = (root = document) => {
    root.querySelectorAll('template[data-toast-messages]').forEach((source) => {
      source.content.querySelectorAll('[data-toast-type]').forEach((message) => show(message.textContent, { type: message.dataset.toastType }));
      source.remove();
    });
  };
  document.addEventListener('visibilitychange', () => active.forEach((toast) => document.hidden ? toast.pause() : toast.resume()));
  window.SwapToast = { show, consume };
  consume();
})();
