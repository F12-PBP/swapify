(() => {
  const region = document.querySelector('[data-toast-region]');
  if (!region) return;
  const template = region.querySelector('[data-toast-template]');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const active = new Map();
  const variants = {
    success: ['swap-alert-success', '✓'],
    error: ['swap-alert-error', '!'],
    warning: ['swap-alert-warning', '!'],
    info: ['swap-alert-info', 'i'],
  };
  const show = (message, { type = 'info' } = {}) => {
    const text = String(message || '').trim();
    if (!text) return;
    if (!Object.hasOwn(variants, type)) type = 'info';
    const key = `${type}:${text}`;
    if (active.has(key)) return active.get(key).element;
    const element = template.content.firstElementChild.cloneNode(true);
    element.classList.add(variants[type][0]);
    element.querySelector('[data-toast-icon]').textContent = variants[type][1];
    const live = element.querySelector('[data-toast-text]');
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
      else element.animate([{ opacity: 1, transform: 'translateY(0)' }, { opacity: 0, transform: 'translateY(8px)' }], { duration: 160, easing: 'ease-in' }).finished.then(finish, finish);
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
    live.textContent = text;
    if (!reducedMotion.matches) element.animate([{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 300, easing: 'cubic-bezier(.22,1,.36,1)' });
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
