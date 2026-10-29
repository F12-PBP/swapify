(() => {
    "use strict";
    const root = document.querySelector("[data-chat-root]");
    if (!root) return;

    const search = root.querySelector("[data-chat-search]");
    search?.addEventListener("input", () => {
        let count = 0;
        root.querySelectorAll("[data-room-id]").forEach((room) => {
        room.hidden = !room.textContent.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase());
        if (!room.hidden) count += 1;
        });
        root.querySelector("[data-no-results]").hidden = count !== 0;
    });

    function startUnreadPolling() {
    const url = root.dataset.unreadUrl;
    if (!url) return;

    const status = root.querySelector("[data-unread-status]");
    let timer;
    let busy = false;
    let stopped = false;
    let delay = 3000;

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
            stopped = [401, 403, 404].includes(error.status);
            delay = Math.min(delay * 2, 30000);

            showStatus(error.message, error.status === 401);
        } finally {
            busy = false;
            schedule();
        }
    }

    window.addEventListener("offline", () => {
        clearTimeout(timer);

        if (!stopped) {
            showStatus(
                "Koneksi terputus. Jumlah pesan belum diperbarui."
            );
        }
    });

    window.addEventListener("online", () => schedule(0));

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) schedule(0);
    });

    window.addEventListener("pagehide", () => clearTimeout(timer));

    window.addEventListener("pageshow", (event) => {
        if (event.persisted) schedule(0);
    });

    schedule(0);
}

startUnreadPolling();

const form = root.querySelector("[data-chat-form]");
if (!form) return;

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
        const timeout = setTimeout(() => controller.abort(), 15000);
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
        } finally { clearTimeout(timeout); }
    }
    function receipt(node, read) {
        node.dataset.read = String(node.dataset.read === "true" || read === true);
        const label = node.querySelector("[data-message-receipt]");
        label.hidden = node.dataset.mine !== "true";
        label.textContent = node.dataset.read === "true" ? " · Dibaca" : " · Terkirim";
    }
    function insert(message) {
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
    }
    function render(data, history = false) {
        const nearBottom = stream.scrollHeight - stream.scrollTop - stream.clientHeight < 80;
        const top = stream.getBoundingClientRect().top;
        const anchor = [...list.children].find((node) => node.getBoundingClientRect().bottom > top);
        const offset = anchor?.getBoundingClientRect().top;
        if (typeof data.is_active === "boolean") active = data.is_active;
        (data.read_receipts || []).forEach((item) => { if (nodes.has(item.id)) receipt(nodes.get(item.id), item.is_read); });
        (data.messages || []).forEach(insert);
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
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (sending || !active || halted) return;
        if (!field.value.trim()) { showNotice("Pesan tidak boleh kosong.", "send"); field.focus(); return; }
        const text = field.value;
        const body = new FormData(form);
        saveDraft();
        sending = true;
        controls();
        showNotice("", "");
        try {
        const data = await request(form.action, { method: "POST", body });
        render({ messages: [data.message] });
        if (field.value === text) field.value = "";
        saveDraft();
        resizeField();
        // Cursor polling tidak dinaikkan dari ID hasil POST.
        schedule(0);
        } catch (error) { handleError(error, "send"); }
        finally { sending = false; controls(); }
    });
    older.addEventListener("click", async () => {
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
    field.addEventListener("input", () => { saveDraft(); resizeField(); });
    field.addEventListener("keydown", (event) => {
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
    window.visualViewport?.addEventListener("resize", fitViewport);
    window.visualViewport?.addEventListener("scroll", fitViewport);
    window.addEventListener("resize", fitViewport);
    window.addEventListener("offline", () => {
        clearTimeout(timer);
        if (noticeOwner !== "send" && noticeOwner !== "terminal") showNotice("Koneksi terputus. Tulisan tetap tersimpan.", "sync");
    });
    window.addEventListener("online", () => schedule(0));
    document.addEventListener("visibilitychange", () => { if (!document.hidden) schedule(0); });
    window.addEventListener("pagehide", () => { saveDraft(); clearTimeout(timer); });
    window.addEventListener("pageshow", (event) => { if (event.persisted) schedule(0); });
    try { field.value = sessionStorage.getItem(draftKey) || field.value; } catch { /* Tetap bisa mengirim tanpa storage. */ }
    list.querySelectorAll("time[datetime]").forEach((time) => { if (time.dateTime) time.textContent = timeFormat.format(new Date(time.dateTime)); });
    fitViewport();
    resizeField();
    controls();
    stream.scrollTop = stream.scrollHeight;
    schedule();
})();
