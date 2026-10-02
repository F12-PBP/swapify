(() => {
    const navbar = document.querySelector('[data-navbar]');
    if (!navbar) return;

    const toggle = navbar.querySelector('[data-navbar-toggle]');
    const menu = navbar.querySelector('[data-navbar-menu]');
    const desktop = window.matchMedia('(min-width: 1280px)');

    function setOpen(open, restoreFocus = false) {
        menu.classList.toggle('hidden', !open);
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Close navigation menu' : 'Open navigation menu');
        if (restoreFocus) toggle.focus();
    }

    toggle.addEventListener('click', () => {
        setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });
    menu.addEventListener('click', (event) => {
        if (event.target.closest('a')) setOpen(false);
    });
    document.addEventListener('click', (event) => {
        if (!navbar.contains(event.target)) setOpen(false);
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
            setOpen(false, true);
        }
    });
    navbar.addEventListener('focusout', (event) => {
        if (!navbar.contains(event.relatedTarget)) setOpen(false);
    });
    desktop.addEventListener('change', () => setOpen(false));
})();
