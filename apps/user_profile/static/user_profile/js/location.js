(() => {
    const form = document.getElementById("location-form");
    if (!form) return;

    const button = document.getElementById("detect-location");
    const saveButton = document.getElementById("save-location");
    const status = document.getElementById("location-status");
    const token = form.elements.namedItem("location_token");
    const fields = ["district", "city", "province"];

    const mapPanel = document.getElementById("location-map-panel");
    const mapElement = document.getElementById("location-map");
    const mapStatus = document.getElementById("location-map-status");
    const recenterButton = document.getElementById("recenter-location");
    let map, areaCircle, marker, leafletReady;
    let hasMapView = false;
    let mapRevision = 0;

    function loadLeaflet() {
        if (leafletReady) return leafletReady;
        leafletReady = new Promise((resolve, reject) => {
            const css = document.createElement("link");
            css.rel = "stylesheet";
            css.href = mapElement.dataset.leafletCss;
            const script = document.createElement("script");
            script.src = mapElement.dataset.leafletJs;
            let cssLoaded = false;
            let jsLoaded = false;
            const timer = setTimeout(fail, 10000);
            function done() {
                if (!cssLoaded || !jsLoaded) return;
                clearTimeout(timer);
                resolve(window.L);
            }
            function fail() {
                clearTimeout(timer);
                css.remove();
                script.remove();
                leafletReady = null;
                reject(new Error("The map could not load."));
            }
            css.onload = () => { cssLoaded = true; done(); };
            script.onload = () => { jsLoaded = true; done(); };
            css.onerror = script.onerror = fail;
            document.head.append(css, script);
        });
        return leafletReady;
    }

    function recenter(animate = true) {
        if (!map || !areaCircle || mapElement.clientWidth === 0) return false;
        map.invalidateSize({ pan: false });
        const options = { padding: [24, 24], maxZoom: 14 };
        if (animate && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
            map.flyToBounds(areaCircle.getBounds(), { ...options, duration: 0.8 });
        } else {
            map.fitBounds(areaCircle.getBounds(), options);
        }
        return true;
    }

    async function showArea(latitude, longitude, accuracy = 0) {
        if (!mapPanel || !mapElement) return;
        const revision = ++mapRevision;
        // Use the same approximate position as reverse geocoding and storage.
        const area = [Number(latitude.toFixed(2)), Number(longitude.toFixed(2))];
        mapPanel.hidden = false;
        mapStatus.textContent = "Loading your area on the map…";
        try {
            const L = await loadLeaflet();
            if (revision !== mapRevision) return;
            if (!map) {
                map = L.map(mapElement, { scrollWheelZoom: false }).setView(area, 13);
                L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
                    maxZoom: 19,
                    referrerPolicy: "strict-origin-when-cross-origin",
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                }).on("tileerror", () => {
                    mapStatus.textContent = "Some map tiles could not load. You can still review and save your area below.";
                }).addTo(map);
                const color = getComputedStyle(document.documentElement).getPropertyValue("--color-primary-base").trim() || "#73141d";
                // The 800 m allowance accounts for rounding coordinates to 2 decimals.
                areaCircle = L.circle(area, { radius: Math.max(800, Number.isFinite(accuracy) ? accuracy : 0), color, weight: 1, fillOpacity: 0.12 }).addTo(map);
                marker = L.circleMarker(area, { radius: 8, color: "#ffffff", weight: 3, fillColor: color, fillOpacity: 1 }).addTo(map);
                marker.bindTooltip("Your approximate area", { direction: "top" });
            } else {
                areaCircle.setLatLng(area).setRadius(Math.max(800, Number.isFinite(accuracy) ? accuracy : 0));
                marker.setLatLng(area);
            }
            hasMapView = recenter(hasMapView) || hasMapView;
            mapStatus.textContent = "Highlighted: your approximate detected area.";
        } catch {
            if (revision !== mapRevision) return;
            mapStatus.textContent = "The map is unavailable. Location detection and manual entry still work.";
        }
    }

    if (mapElement) {
        new ResizeObserver(() => {
            if (map && mapElement.clientWidth > 0) {
                map.invalidateSize({ pan: false });
                if (!hasMapView) hasMapView = recenter(false);
            }
        }).observe(mapElement);
        recenterButton.addEventListener("click", () => recenter());
        const latitude = Number(mapElement.dataset.latitude);
        const longitude = Number(mapElement.dataset.longitude);
        if (mapElement.dataset.latitude && mapElement.dataset.longitude &&
            Number.isFinite(latitude) && Number.isFinite(longitude) &&
            Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180) {
            showArea(latitude, longitude);
        }
    }

    fields.forEach((field) => {
        form.elements.namedItem(field).addEventListener("input", () => {
            token.value = "";
            mapRevision += 1;
            if (mapPanel) mapPanel.hidden = true;
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
            showArea(position.coords.latitude, position.coords.longitude, position.coords.accuracy);
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
