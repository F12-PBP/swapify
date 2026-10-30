(() => {
    const visitor = document.querySelector('[data-auth-swapy]');
    if (!visitor || !window.gsap || !window.Swapy) return;

    const motion = gsap.matchMedia();
    const positions = ['bottom-left', 'right', 'top-right', 'left', 'bottom-right'];

    motion.add('(prefers-reduced-motion: no-preference) and (min-width: 640px)', () => {
        let position = 0;
        visitor.dataset.position = positions[position];
        const timeline = Swapy.createGreeting(visitor, {
            hideAt: 4.2,
            delay: 1.5,
            repeatDelay: 3,
            onRepeat() {
                position = (position + 1) % positions.length;
                visitor.dataset.position = positions[position];
            },
        });
        visitor.hidden = false;

        function updatePlayback() {
            if (document.hidden) timeline.pause();
            else timeline.play();
        }

        updatePlayback();
        document.addEventListener('visibilitychange', updatePlayback);

        return () => {
            timeline.kill();
            visitor.hidden = true;
            document.removeEventListener('visibilitychange', updatePlayback);
        };
    });
})();
