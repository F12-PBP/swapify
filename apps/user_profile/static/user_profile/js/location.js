(() => {
    const form = document.getElementById("location-form");
    if (!form) return;

    const button = document.getElementById("detect-location");
    const saveButton = document.getElementById("save-location");
    const status = document.getElementById("location-status");
    const token = form.elements.namedItem("location_token");
    const fields = ["district", "city", "province"];

    fields.forEach((field) => {
        form.elements.namedItem(field).addEventListener("input", () => {
            token.value = "";
            status.textContent = "Area edited manually. Save when you’re ready.";
        });
    });

    button.addEventListener("click", async () => {
        if (!window.isSecureContext || !navigator.geolocation) {
            status.textContent = "Location detection is unavailable. Please enter your area manually.";
            return;
        }
        button.disabled = true;
        saveButton.disabled = true;
        fields.forEach((field) => { form.elements.namedItem(field).disabled = true; });
        token.value = "";
        status.textContent = "Waiting for your location…";
        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: false,
                    timeout: 10000,
                    maximumAge: 60000,
                });
            });
            status.textContent = "Finding your area…";
            const body = new URLSearchParams({
                latitude: position.coords.latitude.toFixed(2),
                longitude: position.coords.longitude.toFixed(2),
            });
            const response = await fetch(form.dataset.resolveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": form.elements.namedItem("csrfmiddlewaretoken").value,
                },
                body,
                signal: AbortSignal.timeout(15000),
            });
            if (response.redirected) {
                status.textContent = "Your session has expired. Please log in again.";
                return;
            }
            const result = await response.json();
            if (!response.ok) {
                status.textContent = result.error || "Location lookup failed. Please enter your area manually.";
                return;
            }
            fields.forEach((field) => {
                form.elements.namedItem(field).value = result[field];
            });
            token.value = result.location_token;
            status.textContent = form.dataset.stepForm
                ? "Area found. Review the details, then select Next."
                : "Area found. Review the details, then select Save Location.";
        } catch (error) {
            const messages = {
                1: "Location access was denied. Please enter your area manually.",
                2: "Your position is unavailable. Please enter your area manually.",
                3: "Finding your position timed out. Please try again or enter your area manually.",
            };
            status.textContent = messages[error.code] || "Location lookup failed. Please try again or enter your area manually.";
        } finally {
            button.disabled = false;
            saveButton.disabled = false;
            fields.forEach((field) => { form.elements.namedItem(field).disabled = false; });
        }
    });
})();
