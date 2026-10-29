(() => {
    "use strict";
    function mountChat(root, previousPosition = null) {
        const lifecycle = new AbortController();
        const on = (target, type, handler) => target?.addEventListener(type, handler,
            target === lifecycle.signal ? { once: true } : { signal: lifecycle.signal });
        let sendFinished = Promise.resolve();
        const controller = { destroy: () => lifecycle.abort(), whenIdle: () => sendFinished };
        const roomList = root.querySelector("[data-chat-rooms]");
        roomList?.querySelector("[data-chat-indicator]")?.remove();
        const indicator = document.createElement("span");
        indicator.dataset.chatIndicator = "";
        indicator.className = "pointer-events-none absolute top-0 left-0 w-full border-l-4 border-primary-base bg-primary-10";
        indicator.setAttribute("aria-hidden", "true");
        roomList?.append(indicator);
        if (roomList) roomList.dataset.indicatorReady = "true";
        const positionIndicator = (from = null) => {
            const selected = roomList?.querySelector('.chat-room[aria-current="page"]');
            indicator.hidden = !selected || selected.hidden;
            if (indicator.hidden) return;
            const top = selected.offsetTop;
            const height = selected.offsetHeight;
            indicator.style.transform = `translateY(${top}px)`;
            indicator.style.height = `${height}px`;
            if (from !== null) window.SwapifyMotion?.play(indicator, [
                { transform: `translateY(${from}px)` },
                { transform: `translateY(${top}px)` },
            ]);
        };
        positionIndicator(previousPosition);
        const observer = new ResizeObserver(() => positionIndicator());
        if (roomList) observer.observe(roomList);
        on(lifecycle.signal, "abort", () => observer.disconnect());

        const search = root.querySelector("[data-chat-search]");
        on(search, "input", () => {
            let count = 0;
            root.querySelectorAll(".chat-room[data-room-id]").forEach((room) => {
                room.hidden = !room.textContent.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase());
                if (!room.hidden) {
                    window.SwapifyMotion?.reveal(room, { duration: 240, delay: Math.min(count * 20, 80) });
                    count += 1;
                }
            });
            root.querySelector("[data-no-results]").hidden = count !== 0;
            positionIndicator();
        });

        function startUnreadPolling() {
            const url = root.dataset.unreadUrl;
            if (!url) return;

            const status = root.querySelector("[data-unread-status]");
            let timer;
            let busy = false;
            let stopped = false;
            let delay = 3000;
            on(lifecycle.signal, "abort", () => { stopped = true; clearTimeout(timer); });

            function showStatus(message, login = false) {
                if (!status) return;

                status.hidden = !message;
                status.querySelector("[data-unread-text]").textContent = message;
                status.querySelector("[data-unread-login]").hidden = !login;
            }

            function schedule(wait = delay) {
                clearTimeout(timer);

                if (!stopped && !document.hidden && navigator.onLine) {
                    timer = setTimeout(refresh, wait);
                }
            }

            async function refresh() {
                if (busy || stopped || document.hidden || !navigator.onLine) {
                    return;
                }

                busy = true;

                try {
                    const data = await request(url);

                    const counts = new Map(
                        data.rooms.map((room) => [
                            String(room.id),
                            room.unread_count,
                        ])
                    );

                    root.querySelectorAll("[data-unread-count]").forEach((badge) => {
                        const room = badge.closest("[data-room-id]");
                        const count = counts.get(room.dataset.roomId) || 0;

                        badge.textContent = String(count);
                        badge.hidden = count === 0;
                        badge.setAttribute(
                            "aria-label",
                            `${count} pesan belum dibaca`
                        );
                    });

                    delay = 3000;
                    showStatus("");
                } catch (error) {
                    if (lifecycle.signal.aborted) return;
                    stopped = [401, 403, 404].includes(error.status);
                    delay = Math.min(delay * 2, 30000);

                    showStatus(error.message, error.status === 401);
                } finally {
                    busy = false;
                    schedule();
                }
            }

            on(window, "offline", () => {
                clearTimeout(timer);

                if (!stopped) {
                    showStatus(
                        "Koneksi terputus. Jumlah pesan belum diperbarui."
                    );
                }
            });

            on(window, "online", () => schedule(0));

            on(document, "visibilitychange", () => {
                if (!document.hidden) schedule(0);
            });

            on(window, "pagehide", () => clearTimeout(timer));

            on(window, "pageshow", (event) => {
                if (event.persisted) schedule(0);
            });

            schedule(0);
        }

        startUnreadPolling();

        const form = root.querySelector("[data-chat-form]");
        if (!form) return controller;

        const field = form.elements.message;
        const submit = form.querySelector("button[type=submit]");
        const stream = root.querySelector("[data-chat-stream]");
        const list = root.querySelector("[data-messages]");
        const template = root.querySelector("[data-message-template]");
        const older = root.querySelector("[data-load-older]");
        const notice = root.querySelector("[data-chat-notice]");
        const nodes = new Map();
        list.querySelectorAll("[data-message-id]").forEach((node) => nodes.set(Number(node.dataset.messageId), node));
        let cursor = Number(root.dataset.latestId) || 0;
        let before = Number(root.dataset.oldestId) || 0;
        let hasOlder = root.dataset.hasOlder === "true";
        let active = root.dataset.active === "true";
        let sending = false, busy = false, halted = false, timer, delay = 3000, receiptOffset = 0, noticeOwner = "";
        on(lifecycle.signal, "abort", () => { halted = true; saveDraft(); clearTimeout(timer); });
        const draftKey = `swapify:chat:${root.dataset.userId}:${root.dataset.roomId}`;
        const timeFormat = new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit" });

        function saveDraft() {
            try {
            if (field.value) sessionStorage.setItem(draftKey, field.value);
            else sessionStorage.removeItem(draftKey);
            } catch { /* Penyimpanan browser boleh tidak tersedia. */ }
        }
        function resizeField() {
            field.style.height = "auto";
            field.style.height = `${Math.min(field.scrollHeight, parseFloat(getComputedStyle(field).maxHeight))}px`;
        }
        function controls() {
            submit.disabled = sending || !active || halted;
            submit.setAttribute("aria-label", sending ? "Mengirim pesan" : "Kirim pesan");
            form.setAttribute("aria-busy", String(sending));
            field.readOnly = !active;
            root.querySelector("[data-inactive]").hidden = active;
            root.querySelector("[data-send-state]").hidden = !sending;
            root.querySelector("[data-send-spinner]").hidden = !sending;
            root.querySelector("[data-send-icon]").hidden = sending;
            older.hidden = !hasOlder;
            older.disabled = busy;
        }
        function showNotice(text, owner, href = "", label = "") {
            noticeOwner = owner;
            notice.hidden = !text;
            notice.querySelector("[data-notice-text]").textContent = text;
            const action = notice.querySelector("[data-notice-action]");
            const url = new URL(href || location.href, location.href);
            action.hidden = !href || url.origin !== location.origin;
            action.href = url.href;
            action.textContent = label;
        }
        function handleError(error, owner) {
            if ([401, 403, 404].includes(error.status)) {
            halted = true;
            clearTimeout(timer);
            }
            if (error.status === 409) active = false;
            const login = error.status === 401;
            const csrf = error.data?.error?.code === "csrf_failed";
            showNotice(
            error.message,
            halted ? "terminal" : owner,
            login ? (error.data?.login_url || root.dataset.loginUrl) : csrf ? location.href : "",
            login ? "Masuk kembali" : "Muat ulang halaman"
            );
            controls();
        }
        async function request(url, options = {}) {
            const controller = new AbortController();
            const abort = () => controller.abort();
            lifecycle.signal.addEventListener("abort", abort, { once: true });
            const timeout = setTimeout(abort, 15000);
            try {
            const response = await fetch(url, {
                ...options, credentials: "same-origin", cache: "no-store", signal: controller.signal,
                headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest", ...options.headers }
            });
            if (response.redirected) {
                throw Object.assign(new Error("Sesi login berakhir. Silakan masuk kembali."), { status: 401 });
            }
            const data = response.headers.get("Content-Type")?.includes("application/json") ? await response.json() : null;
            if (!response.ok || !data || data.ok === false) {
                const message = data?.errors?.message?.map((error) => error.message).join(" ")
                || data?.error?.message || "Layanan chat belum dapat diakses. Coba kembali nanti.";
                throw Object.assign(new Error(message), { status: response.status, data });
            }
            return data;
            } catch (error) {
            if (error.status) throw error;
            throw new Error(options.method === "POST"
                ? "Pengiriman belum dapat dipastikan. Tulisan tetap disimpan; periksa riwayat sebelum mencoba lagi."
                : "Koneksi bermasalah. Chat akan mencoba terhubung kembali.");
            } finally { clearTimeout(timeout); lifecycle.signal.removeEventListener("abort", abort); }
        }
        function receipt(node, read) {
            node.dataset.read = String(node.dataset.read === "true" || read === true);
            const label = node.querySelector("[data-message-receipt]");
            label.hidden = node.dataset.mine !== "true";
            label.textContent = node.dataset.read === "true" ? " · Dibaca" : " · Terkirim";
        }
        function insert(message, animate = true) {
            const id = Number(message.id);
            if (nodes.has(id)) { receipt(nodes.get(id), message.is_read); return; }
            const node = template.content.firstElementChild.cloneNode(true);
            node.dataset.messageId = String(id);
            node.dataset.mine = String(message.is_mine);
            node.dataset.read = "false";
            node.classList.toggle("is-mine", message.is_mine);
            node.querySelector("[data-message-text]").textContent = message.message;
            const time = node.querySelector("[data-message-time]");
            time.dateTime = message.sent_at;
            time.textContent = timeFormat.format(new Date(message.sent_at));
            receipt(node, message.is_read);
            const next = [...list.children].find((item) => Number(item.dataset.messageId) > id);
            list.insertBefore(node, next || null);
            nodes.set(id, node);
            if (animate) window.SwapifyMotion?.play(node, [
                { opacity: 0, transform: `translate(${message.is_mine ? 8 : -8}px, 8px) scale(.98)` },
                { opacity: 1, transform: "translate(0, 0) scale(1)" },
            ], { duration: 320 });
        }
        function render(data, history = false) {
            const nearBottom = stream.scrollHeight - stream.scrollTop - stream.clientHeight < 80;
            const top = stream.getBoundingClientRect().top;
            const anchor = [...list.children].find((node) => node.getBoundingClientRect().bottom > top);
            const offset = anchor?.getBoundingClientRect().top;
            if (typeof data.is_active === "boolean") active = data.is_active;
            (data.read_receipts || []).forEach((item) => { if (nodes.has(item.id)) receipt(nodes.get(item.id), item.is_read); });
            (data.messages || []).forEach((message) => insert(message, !history));
            if (history) {
            hasOlder = data.has_more;
            if (data.next_before) before = data.next_before;
            }
            root.querySelector("[data-empty]").hidden = nodes.size !== 0;
            controls();
            if (!history && nearBottom) stream.scrollTop = stream.scrollHeight;
            else if (anchor) stream.scrollTop += anchor.getBoundingClientRect().top - offset;
        }
        function receiptIds() {
            const ids = [...nodes.entries()].filter(([, node]) => node.dataset.mine === "true" && node.dataset.read !== "true").map(([id]) => id);
            if (!ids.length) return "";
            receiptOffset %= ids.length;
            const result = [...ids.slice(receiptOffset), ...ids.slice(0, receiptOffset)].slice(0, 100);
            receiptOffset = (receiptOffset + result.length) % ids.length;
            return result.join(",");
        }
        function schedule(wait = delay) {
            clearTimeout(timer);
            if (!halted && navigator.onLine) timer = setTimeout(poll, wait);
        }
        async function poll() {
            if (halted) return;
            if (busy || document.hidden) { schedule(); return; }
            busy = true;
            controls();
            try {
            let data;
            do {
                const url = new URL(root.dataset.pollUrl, location.href);
                url.search = new URLSearchParams({ after: cursor, read_ids: receiptIds() });
                data = await request(url);
                render(data);
                cursor = Math.max(cursor, Number(data.next_after) || cursor);
            } while (data.has_more && !halted && !document.hidden);
            delay = 3000;
            if (noticeOwner === "sync") showNotice("", "");
            } catch (error) {
            delay = Math.min(delay * 2, 30000);
            if (noticeOwner !== "send" && noticeOwner !== "terminal") handleError(error, "sync");
            else if ([401, 403, 404].includes(error.status)) handleError(error, "sync");
            } finally { busy = false; controls(); schedule(); }
        }
        on(form, "submit", async (event) => {
            event.preventDefault();
            if (sending || !active || halted) return;
            if (!field.value.trim()) { showNotice("Pesan tidak boleh kosong.", "send"); field.focus(); return; }
            const text = field.value;
            const body = new FormData(form);
            saveDraft();
            sending = true;
            let finishSending;
            sendFinished = new Promise((resolve) => { finishSending = resolve; });
            controls();
            showNotice("", "");
            try {
            const data = await request(form.action, { method: "POST", body });
            render({ messages: [data.message] });
            stream.scrollTo({ top: stream.scrollHeight, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
            if (field.value === text) field.value = "";
            saveDraft();
            resizeField();
            // Cursor polling tidak dinaikkan dari ID hasil POST.
            schedule(0);
            } catch (error) { handleError(error, "send"); }
            finally { sending = false; controls(); finishSending(); }
        });
        on(older, "click", async () => {
            if (busy || halted || !hasOlder) return;
            busy = true;
            controls();
            older.textContent = "Memuat riwayat…";
            try {
            const url = new URL(root.dataset.pollUrl, location.href);
            url.search = new URLSearchParams({ before, read_ids: receiptIds() });
            render(await request(url), true);
            if (noticeOwner === "sync") showNotice("", "");
            } catch (error) { handleError(error, "sync"); }
            finally { busy = false; older.textContent = "Muat pesan sebelumnya"; controls(); }
        });
        on(field, "input", () => { saveDraft(); resizeField(); });
        on(field, "keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.isComposing && event.keyCode !== 229 && !matchMedia("(pointer: coarse)").matches) {
            event.preventDefault();
            form.requestSubmit();
            }
        });
        function fitViewport() {
            const viewport = window.visualViewport;
            root.style.setProperty("--chat-visual-height", `${viewport?.height || innerHeight}px`);
            root.style.setProperty("--chat-visual-top", `${viewport?.offsetTop || 0}px`);
        }
        on(window.visualViewport, "resize", fitViewport);
        on(window.visualViewport, "scroll", fitViewport);
        on(window, "resize", fitViewport);
        on(window, "offline", () => {
            clearTimeout(timer);
            if (noticeOwner !== "send" && noticeOwner !== "terminal") showNotice("Koneksi terputus. Tulisan tetap tersimpan.", "sync");
        });
        on(window, "online", () => schedule(0));
        on(document, "visibilitychange", () => { if (!document.hidden) schedule(0); });
        on(window, "pagehide", () => { saveDraft(); clearTimeout(timer); });
        on(window, "pageshow", (event) => { if (event.persisted) schedule(0); });
        try { field.value = sessionStorage.getItem(draftKey) || field.value; } catch { /* Tetap bisa mengirim tanpa storage. */ }
        list.querySelectorAll("time[datetime]").forEach((time) => { if (time.dateTime) time.textContent = timeFormat.format(new Date(time.dateTime)); });
        fitViewport();
        resizeField();
        controls();
        stream.scrollTop = stream.scrollHeight;
        schedule();
        return controller;
    }

    let root = document.querySelector("[data-chat-root]");
    if (!root) return;
    let mounted = mountChat(root);
    let navigation;
    let sequence = 0;
    let currentURL = new URL(location.href);
    const scrollRestoration = history.scrollRestoration;
    history.scrollRestoration = "manual";
    window.addEventListener("pagehide", () => { history.scrollRestoration = scrollRestoration; });
    window.addEventListener("pageshow", () => { history.scrollRestoration = "manual"; });
    const roomPath = new URL(root.dataset.unreadUrl, location.href).pathname;
    const navigate = async (url, push = true) => {
        navigation?.abort();
        const current = ++sequence;
        const controller = new AbortController();
        navigation = controller;
        const timeout = setTimeout(() => controller.abort(), 15000);
        root.setAttribute("aria-busy", "true");
        root.querySelector("[data-chat-navigation-status]").hidden = true;
        try {
            await mounted.whenIdle();
            if (current !== sequence) return;
            const response = await fetch(url, { credentials: "same-origin", signal: controller.signal, headers: { Accept: "text/html" } });
            if (current !== sequence) return;
            if (response.redirected || [401, 403, 404].includes(response.status)) {
                location.assign(response.redirected ? response.url : url);
                return;
            }
            if (!response.ok) throw new Error("Conversation unavailable");
            const page = new DOMParser().parseFromString(await response.text(), "text/html");
            const next = page.querySelector("[data-chat-root]");
            if (!next) throw new Error("Conversation unavailable");
            await mounted.whenIdle();
            if (current !== sequence) return;
            const selected = root.querySelector('.chat-room[aria-current="page"]');
            const previousPosition = selected?.offsetTop ?? null;
            const sidebar = root.querySelector("[data-chat-rooms]");
            const sidebarScroll = sidebar?.scrollTop || 0;
            const searchValue = root.querySelector("[data-chat-search]")?.value || "";
            const hadLinkFocus = document.activeElement?.matches(".chat-room");
            const previousSidebar = root.querySelector(".chat-sidebar");
            const nextSidebarContent = next.querySelector(".chat-sidebar");
            const nextRoomId = next.dataset.roomId;
            mounted.destroy();
            if (previousSidebar && nextSidebarContent) {
                previousSidebar.className = nextSidebarContent.className;
                previousSidebar.querySelectorAll(".chat-room").forEach((link) => {
                    if (link.dataset.roomId === nextRoomId) link.setAttribute("aria-current", "page");
                    else link.removeAttribute("aria-current");
                });
                nextSidebarContent.replaceWith(previousSidebar);
            }
            root.replaceWith(next);
            root = next;
            document.title = page.title;
            if (push && location.href !== url.href) history.pushState(null, "", url);
            currentURL = new URL(url);
            mounted = mountChat(root, previousPosition);
            const nextSearch = root.querySelector("[data-chat-search]");
            if (nextSearch && searchValue) {
                nextSearch.value = searchValue;
                nextSearch.dispatchEvent(new Event("input"));
            }
            const nextSidebar = root.querySelector("[data-chat-rooms]");
            if (nextSidebar) nextSidebar.scrollTop = sidebarScroll;
            if (hadLinkFocus) root.querySelector('.chat-room[aria-current="page"]')?.focus({ preventScroll: true });
            window.SwapifyMotion?.reveal(root.querySelector(".chat-pane") || root.querySelector(".chat-placeholder"), { duration: 320 });
        } catch {
            if (current === sequence) {
                root.querySelector("[data-chat-navigation-status]").hidden = false;
                if (!push) history.replaceState(null, "", currentURL);
            }
        } finally {
            clearTimeout(timeout);
            if (current === sequence) root.removeAttribute("aria-busy");
        }
    };
    document.addEventListener("pointerdown", (event) => {
        const link = event.target.closest(".chat-room, .chat-pane a[aria-label]");
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || !link || !root.contains(link)) return;
        if (link.matches(".chat-room") && event.pointerType !== "mouse") return;
        event.preventDefault();
        if (link.matches(".chat-room")) link.focus({ preventScroll: true });
    });
    document.addEventListener("click", (event) => {
        const link = event.target.closest(".chat-room, .chat-pane a[aria-label]");
        if (!link || !root.contains(link) || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const url = new URL(link.href);
        if (url.origin !== location.origin || !url.pathname.startsWith(roomPath) || !(url.pathname === roomPath || /^\d+\/$/.test(url.pathname.slice(roomPath.length)))) return;
        event.preventDefault();
        if (url.pathname !== location.pathname) navigate(url);
    });
    window.addEventListener("popstate", () => {
        if (location.pathname.startsWith(roomPath)) navigate(new URL(location.href), false);
        else location.reload();
    });
})();
