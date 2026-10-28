(() => {
    const stage = document.querySelector('[data-swapy-stage]');
    if (!stage || !window.gsap || !window.Swapy) return;

    const motion = gsap.matchMedia();

    motion.add('(prefers-reduced-motion: no-preference)', () => {
        const timeline = Swapy.createGreeting(stage);

        let visible = false;

        function updatePlayback() {
            if (visible && !document.hidden) timeline.play();
            else timeline.pause();
        }

        const observer = new IntersectionObserver(([entry]) => {
            visible = entry.isIntersecting;
            updatePlayback();
        });

        observer.observe(stage);
        document.addEventListener('visibilitychange', updatePlayback);

        return () => {
            observer.disconnect();
            document.removeEventListener('visibilitychange', updatePlayback);
        };
    });
})();
