(() => {
    const root = document.getElementById("onboarding");
    if (!root) return;
    const track = document.getElementById("onboarding-track");
    const viewport = track.parentElement;
    const panels = Array.from(track.querySelectorAll("[data-panel]"));
    let step = Number(root.dataset.step);
    let busy = false;
    let moving = false;
    let previewUrl;
    let photoUpload = null;
    let photoSelection = 0;

    function resize() {
        viewport.style.height = `${panels[step - 1].getBoundingClientRect().height}px`;
    }
    async function show(next, focus = true) {
        if (moving) return;
        const previous = step;
        const animate = focus && previous !== next &&
            !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const direction = next > previous ? 1 : -1;
        const durationValue = getComputedStyle(root).getPropertyValue("--onboarding-duration").trim();
        const duration = parseFloat(durationValue) * (durationValue.endsWith("ms") ? 1 : 1000) || 800;
        const distance = viewport.clientWidth;
        const easing = getComputedStyle(root).getPropertyValue("--onboarding-easing").trim();
        const slide = async (panel, frames) => {
            const animation = panel.animate(frames, { duration: duration / 2, easing });
            try { await animation.finished; } catch { /* Motion may be cancelled by navigation. */ }
        };
        moving = animate;
        if (animate) {
            panels[previous - 1].inert = true;
            await slide(panels[previous - 1], [
                { transform: "translate3d(0, 0, 0)" },
                { transform: `translate3d(${-direction * distance}px, 0, 0)` },
            ]);
        }
        step = next;
        root.dataset.step = String(step);
        panels.forEach((panel, index) => {
            const active = index === step - 1;
            panel.hidden = !active;
            panel.inert = !active;
            panel.setAttribute("aria-hidden", String(!active));
        });
        document.querySelectorAll("[data-progress]").forEach((item) => {
            const index = Number(item.dataset.progress);
            item.classList.toggle("is-complete", index < step);
            if (index === step) item.setAttribute("aria-current", "step");
            else item.removeAttribute("aria-current");
        });
        const progress = document.getElementById("onboarding-progress");
        progress.hidden = false;
        progress.inert = step === 4;
        progress.setAttribute("aria-hidden", String(step === 4));
        root.classList.toggle("is-complete", step === 4);
        const laterButton = document.querySelector("#finish-later-form button");
        laterButton.hidden = false;
        laterButton.classList.toggle("is-hidden", step === 4);
        laterButton.inert = step === 4;
        history.replaceState(null, "", `${location.pathname}?step=${step}`);
        viewport.scrollTop = 0;
        viewport.scrollLeft = 0;
        resize();
        if (animate) {
            await slide(panels[step - 1], [
                { transform: `translate3d(${direction * distance}px, 0, 0)` },
                { transform: "translate3d(0, 0, 0)" },
            ]);
        }
        moving = false;
        if (focus) panels[step - 1].querySelector("h1, h2").focus({ preventScroll: true });
    }
    root.classList.add("is-enhanced");
    show(step, false);
    requestAnimationFrame(() => requestAnimationFrame(() => root.classList.add("is-ready")));
    const observer = new ResizeObserver(resize);
    panels.forEach((panel) => observer.observe(panel));
    document.fonts.ready.then(resize);
    root.querySelectorAll("[data-back]").forEach((button) => {
        button.addEventListener("click", (event) => {
            event.preventDefault();
            if (!busy && !moving) show(step - 1);
        });
    });
    const bio = root.querySelector('[name="bio"]');
    bio.addEventListener("input", () => {
        document.getElementById("bio-count").textContent = `${bio.value.length}/1000 characters`;
    });
    const photo = root.querySelector('[name="new_profile_picture"]');
    const photoStatus = document.getElementById("photo-status");
    let savedPhotoUrl = document.getElementById("photo-preview").getAttribute("src") || "";
    photo.addEventListener("change", () => {
        const file = photo.files[0];
        const errors = root.querySelector('[data-field-errors="new_profile_picture"]');
        errors.textContent = "";
        if (!file) return;
        if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024) {
            errors.textContent = "Choose a JPG, PNG, or WebP image up to 5 MB.";
            photo.value = "";
            return;
        }
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = URL.createObjectURL(file);
        const preview = document.getElementById("photo-preview");
        const plus = document.getElementById("photo-plus");
        const selection = ++photoSelection;
        const localPreviewUrl = previewUrl;
        const previousSrc = savedPhotoUrl;
        const previouslyHidden = !savedPhotoUrl;
        preview.src = previewUrl;
        preview.hidden = false;
        plus.hidden = true;
        photoStatus.textContent = "Uploading photo…";
        photo.disabled = true;
        const nextButton = photo.form.querySelector('button[type="submit"]');
        nextButton.disabled = true;
        const body = new FormData();
        body.set("action", "upload_photo");
        body.set("new_profile_picture", file);
        body.set("csrfmiddlewaretoken", photo.form.elements.namedItem("csrfmiddlewaretoken").value);
        photoUpload = (async () => {
            try {
                const response = await fetch(location.pathname, {
                    method: "POST", body, credentials: "same-origin",
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                    signal: AbortSignal.timeout(45000),
                });
                if (response.redirected) throw new Error("Your session has expired. Please sign in again.");
                const result = await response.json();
                if (!response.ok) {
                    const messages = Object.values(result.errors || {}).flat().map(item => item.message);
                    throw new Error(result.error || messages.join(" ") || "Your photo could not be saved. Please select it again.");
                }
                // Keep the instant local preview while the saved image loads.
                savedPhotoUrl = result.profile_picture_url;
                const savedImage = new Image();
                savedImage.onload = () => {
                    if (selection !== photoSelection) return;
                    preview.src = result.profile_picture_url;
                    URL.revokeObjectURL(localPreviewUrl);
                    previewUrl = null;
                };
                savedImage.src = result.profile_picture_url;
                photo.value = ""; // Next must not upload the same photo a second time.
                photoStatus.textContent = "Photo saved";
                return true;
            } catch (error) {
                errors.textContent = error.message || "Your photo could not be saved. Please select it again.";
                photoStatus.textContent = "Profile Picture";
                if (previousSrc) preview.src = previousSrc;
                else preview.removeAttribute("src");
                preview.hidden = previouslyHidden;
                plus.hidden = !previouslyHidden;
                photo.value = "";
                return false;
            } finally {
                photo.disabled = false;
                nextButton.disabled = false;
                photoUpload = null;
                resize();
            }
        })();
    });
    root.querySelectorAll("[data-step-form]").forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            if (busy || moving || photoUpload || !form.reportValidity()) return;
            const errors = form.querySelector("[data-errors]");
            errors.replaceChildren();
            const body = new FormData(form);
            const buttons = Array.from(form.querySelectorAll("button"));
            busy = true;
            buttons.forEach((button) => { button.disabled = true; });
            form.setAttribute("aria-busy", "true");
            try {
                const response = await fetch(location.pathname, {
                    method: "POST", body, credentials: "same-origin",
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                    signal: AbortSignal.timeout(30000),
                });
                if (response.redirected) {
                    errors.textContent = "Your session has expired. Please sign in again.";
                    return;
                }
                const result = await response.json();
                if (!response.ok) {
                    Object.entries(result.errors || {}).forEach(([name, messages]) => {
                        messages.forEach(({ message }) => {
                            const line = document.createElement("p");
                            const field = form.elements.namedItem(name);
                            const label = field && field.id ? form.querySelector(`label[for="${field.id}"]`) : null;
                            line.textContent = `${label ? `${label.textContent.trim()}: ` : ""}${message}`;
                            errors.append(line);
                        });
                    });
                    if (!errors.textContent) errors.textContent = result.error || "We couldn’t save this step. Please try again.";
                    return;
                }
                document.getElementById("welcome-name").textContent = `${result.display_name}!`;
                await show(result.step);
            } catch {
                errors.textContent = "We couldn’t save your changes. Check your connection and try again.";
            } finally {
                busy = false;
                buttons.forEach((button) => { button.disabled = false; });
                form.removeAttribute("aria-busy");
                resize();
            }
        });
    });
})();
