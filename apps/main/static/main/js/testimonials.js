(() => {
    const stage = document.querySelector('[data-swapy-stage]');
    if (!stage || !window.gsap) return;

    const mascot = stage.querySelector('[data-swapy]');
    const hand = stage.querySelector('[data-swapy-hand]');
    const head = stage.querySelector('[data-swapy-head]');
    const eyesOpen = stage.querySelector('[data-swapy-eyes-open]');
    const eyesClosed = stage.querySelector('[data-swapy-eyes-closed]');
    const motion = gsap.matchMedia();

    motion.add('(prefers-reduced-motion: no-preference)', () => {
        gsap.set(mascot, { y: 204 });
        gsap.set(hand, { transformOrigin: '95% 85%' });
        gsap.set(head, { transformOrigin: '50% 80%' });

        const timeline = gsap.timeline({ paused: true, repeat: -1, repeatDelay: 3 });
        timeline
            .addLabel('greet', 1.2)
            .to(mascot, { y: 0, duration: 1, ease: 'power2.out' }, 0)
            .to(hand, { rotation: 28, duration: 0.35, ease: 'sine.inOut' }, 'greet')
            .to(hand, { rotation: -8, duration: 0.35, repeat: 3, yoyo: true, ease: 'sine.inOut' }, 'greet+=0.35')
            .to(hand, { rotation: 0, duration: 0.25, ease: 'sine.inOut' }, 'greet+=1.75')
            .to(head, { rotation: -6, duration: 0.35, ease: 'sine.inOut' }, 'greet')
            .to(head, { rotation: 6, duration: 0.35, repeat: 3, yoyo: true, ease: 'sine.inOut' }, 'greet+=0.35')
            .to(head, { rotation: 0, duration: 0.25, ease: 'sine.inOut' }, 'greet+=1.75')
            .set(eyesOpen, { opacity: 0 }, 'greet')
            .set(eyesClosed, { opacity: 1 }, 'greet')
            .set(eyesOpen, { opacity: 1 }, 'greet+=0.16')
            .set(eyesClosed, { opacity: 0 }, 'greet+=0.16')
            .set(eyesOpen, { opacity: 0 }, 'greet+=1.1')
            .set(eyesClosed, { opacity: 1 }, 'greet+=1.1')
            .set(eyesOpen, { opacity: 1 }, 'greet+=1.26')
            .set(eyesClosed, { opacity: 0 }, 'greet+=1.26')
            .to(mascot, { y: 204, duration: 1, ease: 'power2.inOut' }, 8);

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
