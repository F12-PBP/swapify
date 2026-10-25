(() => {
    if (!window.gsap) return;

    document.querySelectorAll('[data-hero-scene]').forEach((scene) => {
        const mascot = scene.querySelector('[data-hero-mascot]');
        const shadow = scene.querySelector('[data-hero-shadow]');
        const normal = scene.querySelector('[data-hero-normal]');
        const wink = scene.querySelector('[data-hero-wink]');
        const cards = [...scene.querySelectorAll('[data-hero-card]')];
        const motion = gsap.matchMedia();

        motion.add('(prefers-reduced-motion: no-preference)', () => {
            gsap.set(mascot, { transformOrigin: '50% 100%' });

            const bounce = gsap.timeline({ paused: true, repeat: -1, repeatDelay: 0.26 });
            bounce
                .to(mascot, { y: -64, duration: 0.6, ease: 'power2.out' }, 0)
                .to(shadow, { scaleX: 0.68, scaleY: 0.78, opacity: 0.45, filter: 'blur(1.5px)', duration: 0.6, ease: 'power2.out' }, 0)
                .to(mascot, { y: 0, duration: 0.5, ease: 'power2.in' }, 0.6)
                .to(shadow, { scaleX: 1, scaleY: 1, opacity: 1, filter: 'blur(0px)', duration: 0.5, ease: 'power2.in' }, 0.6)
                .set(normal, { opacity: 0 }, 1.1)
                .set(wink, { opacity: 1 }, 1.1)
                .to(mascot, { scaleX: 1.035, scaleY: 0.965, duration: 0.1, ease: 'power1.out' }, 1.1)
                .to(mascot, { scaleX: 1, scaleY: 1, duration: 0.14, ease: 'power1.out' }, 1.2)
                .set(normal, { opacity: 1 }, 1.34)
                .set(wink, { opacity: 0 }, 1.34);

            const floats = cards.map((card, index) => gsap.to(card, {
                y: -[14, 10, 12][index],
                duration: 1.5 + index * 0.35,
                repeat: -1,
                yoyo: true,
                ease: 'sine.inOut',
                paused: true,
            }));
            const animations = [bounce, ...floats];
            let visible = false;

            function updatePlayback() {
                const playing = visible && scene.clientWidth > 0 && !document.hidden;
                animations.forEach((animation) => {
                    if (playing) animation.play();
                    else animation.pause();
                });
            }

            const observer = new IntersectionObserver(([entry]) => {
                visible = entry.isIntersecting;
                updatePlayback();
            });

            observer.observe(scene);
            document.addEventListener('visibilitychange', updatePlayback);

            return () => {
                observer.disconnect();
                document.removeEventListener('visibilitychange', updatePlayback);
            };
        });
    });
})();
