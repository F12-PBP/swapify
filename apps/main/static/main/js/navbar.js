(() => {
    const navbar = document.querySelector('[data-navbar]');
    if (!navbar) return;

    const toggle = navbar.querySelector('[data-navbar-toggle]');
    const menu = navbar.querySelector('[data-navbar-menu]');
    const desktop = window.matchMedia('(min-width: 1280px)');

    function setOpen(open, restoreFocus = false) {
        if (!open && menu.contains(document.activeElement)) toggle.focus();
        menu.inert = !open;
        menu.setAttribute('aria-hidden', String(!open));
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
    const sectionLinks = [...navbar.querySelectorAll('[data-landing-link]')];
    const sections = [...new Set(sectionLinks.map((link) => document.getElementById(new URL(link.href).hash.slice(1))).filter(Boolean))];
    if (sections.length) {
        let frame;
        const updateSection = () => {
            frame = undefined;
            const offset = navbar.getBoundingClientRect().bottom + 48;
            const active = sections.filter((section) => section.getBoundingClientRect().top <= offset).at(-1) || sections[0];
            sectionLinks.forEach((link) => {
                if (link.hash === `#${active.id}`) link.setAttribute('aria-current', 'location');
                else link.removeAttribute('aria-current');
            });
        };
        window.addEventListener('scroll', () => {
            if (!frame) frame = requestAnimationFrame(updateSection);
        }, { passive: true });
        window.addEventListener('resize', updateSection);
        updateSection();
    }
    desktop.addEventListener('change', () => setOpen(false));
})();
