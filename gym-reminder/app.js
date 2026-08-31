/**
 * Gym Reminder — tägliche Trainingserinnerung + Motivations-Benachrichtigungen.
 *
 * Der gesamte Zustand liegt in `localStorage`; es gibt keinen Server. Die
 * Erinnerungen werden von einem Ticker ausgelöst, der alle paar Sekunden
 * prüft, ob ein Termin fällig ist. Das ist robuster als ein langer
 * `setTimeout`, den mobile Browser gerne verschlucken.
 */
(function () {
    "use strict";

    const STORAGE_KEY = "gym-reminder.state.v1";
    const TICK_INTERVAL_MS = 15_000;
    /** Eine Erinnerung, die länger als das her ist, wird stumm verworfen. */
    const REMINDER_GRACE_MS = 4 * 60 * 60 * 1000;
    const QUIET_START_HOUR = 22;
    const QUIET_END_HOUR = 7;

    const DAY_LABELS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
    /** Anzeigereihenfolge der Wochentage (Montag zuerst), Werte sind `Date#getDay()`. */
    const DAY_ORDER = [1, 2, 3, 4, 5, 6, 0];

    const DEFAULT_STATE = {
        reminderTime: "18:00",
        trainingDays: [1, 2, 3, 4, 5],
        motivationIntervalHours: 4,
        quietHours: true,
        history: [],
        lastReminderDate: null,
        nextMotivationAt: null,
        lastQuote: null,
    };

    const el = {
        streakCount: document.getElementById("streak-count"),
        streakLabel: document.getElementById("streak-label"),
        week: document.getElementById("week"),
        checkin: document.getElementById("checkin"),
        checkinText: document.getElementById("checkin-text"),
        undoCheckin: document.getElementById("undo-checkin"),
        quote: document.getElementById("quote"),
        newQuote: document.getElementById("new-quote"),
        permissionStatus: document.getElementById("permission-status"),
        enableNotifications: document.getElementById("enable-notifications"),
        testNotification: document.getElementById("test-notification"),
        reminderTime: document.getElementById("reminder-time"),
        days: document.getElementById("days"),
        motivationInterval: document.getElementById("motivation-interval"),
        quietHoursToggle: document.getElementById("quiet-hours"),
        nextReminder: document.getElementById("next-reminder"),
        toast: document.getElementById("toast"),
    };

    let state = loadState();
    let swRegistration = null;

    // ---------------------------------------------------------------- Zustand

    function loadState() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) {
                return { ...DEFAULT_STATE };
            }
            return { ...DEFAULT_STATE, ...JSON.parse(raw) };
        } catch (error) {
            console.warn("Zustand konnte nicht gelesen werden:", error);
            return { ...DEFAULT_STATE };
        }
    }

    function saveState() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (error) {
            console.warn("Zustand konnte nicht gespeichert werden:", error);
        }
    }

    // ----------------------------------------------------------------- Datum

    function dateKey(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function addDays(date, days) {
        const copy = new Date(date);
        copy.setDate(copy.getDate() + days);
        return copy;
    }

    function parseTime(value) {
        const [hours, minutes] = String(value).split(":").map(Number);
        return {
            hours: Number.isFinite(hours) ? hours : 18,
            minutes: Number.isFinite(minutes) ? minutes : 0,
        };
    }

    function reminderDateFor(date) {
        const { hours, minutes } = parseTime(state.reminderTime);
        const target = new Date(date);
        target.setHours(hours, minutes, 0, 0);
        return target;
    }

    function isTrainingDay(date) {
        return state.trainingDays.includes(date.getDay());
    }

    function isQuietTime(date) {
        if (!state.quietHours) {
            return false;
        }
        const hour = date.getHours();
        return hour >= QUIET_START_HOUR || hour < QUIET_END_HOUR;
    }

    /** Nächster Zeitpunkt außerhalb der Nachtruhe, ab `date`. */
    function afterQuietTime(date) {
        if (!isQuietTime(date)) {
            return date;
        }
        const next = date.getHours() >= QUIET_START_HOUR ? addDays(date, 1) : new Date(date);
        next.setHours(QUIET_END_HOUR, 0, 0, 0);
        return next;
    }

    // ---------------------------------------------------------------- Streak

    function hasCheckIn(date) {
        return state.history.includes(dateKey(date));
    }

    function currentStreak() {
        const today = new Date();
        // Der heutige Tag zählt nur mit, wenn schon eingecheckt wurde — sonst
        // wäre die Serie bis zum Abend fälschlich gebrochen.
        let cursor = hasCheckIn(today) ? today : addDays(today, -1);
        let streak = 0;
        while (hasCheckIn(cursor)) {
            streak += 1;
            cursor = addDays(cursor, -1);
        }
        return streak;
    }

    function toggleCheckIn(done) {
        const key = dateKey(new Date());
        if (done && !state.history.includes(key)) {
            state.history = [...state.history, key].sort();
        } else if (!done) {
            state.history = state.history.filter((entry) => entry !== key);
        }
        saveState();
        render();
    }

    // ---------------------------------------------------- Benachrichtigungen

    function notificationsReady() {
        return "Notification" in window && Notification.permission === "granted";
    }

    async function requestPermission() {
        if (!("Notification" in window)) {
            showToast("Dieser Browser kennt keine Benachrichtigungen.");
            return;
        }
        const result = await Notification.requestPermission();
        if (result === "granted") {
            scheduleNextMotivation(new Date());
            saveState();
            showToast("Benachrichtigungen sind aktiv.");
        } else {
            showToast("Ohne Erlaubnis kann die App dich nicht erinnern.");
        }
        render();
    }

    async function notify(title, body, tag) {
        if (!notificationsReady()) {
            return false;
        }
        const options = {
            body,
            tag,
            renotify: true,
            icon: "icons/icon.svg",
            badge: "icons/icon.svg",
            lang: "de",
        };
        // Auf Android und iOS zeigt ausschließlich der Service Worker
        // Benachrichtigungen an — `new Notification(...)` wirft dort.
        const registration =
            swRegistration ||
            ("serviceWorker" in navigator
                ? await navigator.serviceWorker.getRegistration().catch(() => null)
                : null);
        if (registration) {
            try {
                await registration.showNotification(title, options);
                return true;
            } catch (error) {
                // z. B. wenn der Worker noch nicht aktiv ist — unten weiter.
                console.warn("Service Worker konnte nicht benachrichtigen:", error);
            }
        }
        try {
            new Notification(title, options);
            return true;
        } catch (error) {
            console.warn("Benachrichtigung fehlgeschlagen:", error);
            return false;
        }
    }

    // -------------------------------------------------------------- Scheduler

    function scheduleNextMotivation(from) {
        const hours = state.motivationIntervalHours;
        if (!hours) {
            state.nextMotivationAt = null;
            return;
        }
        const next = new Date(from.getTime() + hours * 60 * 60 * 1000);
        state.nextMotivationAt = afterQuietTime(next).getTime();
    }

    function tick() {
        const now = new Date();
        let dirty = false;

        // 1. Tägliche Gym-Erinnerung
        const todayKey = dateKey(now);
        if (state.lastReminderDate !== todayKey && isTrainingDay(now)) {
            const due = reminderDateFor(now);
            if (now >= due) {
                const late = now.getTime() - due.getTime() > REMINDER_GRACE_MS;
                if (!late && !hasCheckIn(now)) {
                    const quote = self.randomQuote(state.lastQuote);
                    state.lastQuote = quote;
                    notify("Zeit fürs Gym 🏋️", quote, "gym-reminder");
                }
                state.lastReminderDate = todayKey;
                dirty = true;
            }
        }

        // 2. Motivationssprüche im gewählten Intervall
        if (state.motivationIntervalHours) {
            if (!state.nextMotivationAt) {
                scheduleNextMotivation(now);
                dirty = true;
            } else if (now.getTime() >= state.nextMotivationAt) {
                if (isQuietTime(now)) {
                    state.nextMotivationAt = afterQuietTime(now).getTime();
                } else {
                    const quote = self.randomQuote(state.lastQuote);
                    state.lastQuote = quote;
                    notify("Motivation für dich 💪", quote, "gym-motivation");
                    scheduleNextMotivation(now);
                }
                dirty = true;
            }
        } else if (state.nextMotivationAt) {
            state.nextMotivationAt = null;
            dirty = true;
        }

        if (dirty) {
            saveState();
            render();
        } else {
            renderNextReminder();
        }
    }

    // ---------------------------------------------------------------- Ansicht

    function render() {
        renderStreak();
        renderWeek();
        renderCheckIn();
        renderSettings();
        renderPermission();
        renderNextReminder();
    }

    function renderStreak() {
        const streak = currentStreak();
        el.streakCount.textContent = String(streak);
        el.streakLabel.textContent = streak === 1 ? "Tag in Folge" : "Tage in Folge";
    }

    function renderWeek() {
        el.week.innerHTML = "";
        const today = new Date();
        for (let offset = 6; offset >= 0; offset -= 1) {
            const date = addDays(today, -offset);
            const item = document.createElement("li");
            item.className = "week__day";
            if (hasCheckIn(date)) {
                item.classList.add("week__day--done");
            } else if (isTrainingDay(date) && offset > 0) {
                item.classList.add("week__day--missed");
            }
            if (offset === 0) {
                item.classList.add("week__day--today");
            }
            item.innerHTML = `<span class="week__label">${DAY_LABELS[date.getDay()]}</span>
                <span class="week__dot" aria-hidden="true"></span>`;
            item.title = `${DAY_LABELS[date.getDay()]}, ${date.toLocaleDateString("de-DE")}`;
            el.week.append(item);
        }
    }

    function renderCheckIn() {
        const done = hasCheckIn(new Date());
        el.checkin.classList.toggle("checkin--done", done);
        el.checkinText.textContent = done ? "Erledigt — stark!" : "Ich war heute im Gym";
        el.checkin.disabled = done;
        el.undoCheckin.hidden = !done;
    }

    function renderSettings() {
        el.reminderTime.value = state.reminderTime;
        el.motivationInterval.value = String(state.motivationIntervalHours);
        el.quietHoursToggle.checked = state.quietHours;

        if (!el.days.childElementCount) {
            for (const day of DAY_ORDER) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "day";
                button.dataset.day = String(day);
                button.textContent = DAY_LABELS[day];
                button.addEventListener("click", () => {
                    state.trainingDays = state.trainingDays.includes(day)
                        ? state.trainingDays.filter((entry) => entry !== day)
                        : [...state.trainingDays, day].sort();
                    saveState();
                    render();
                });
                el.days.append(button);
            }
        }
        for (const button of el.days.children) {
            const active = state.trainingDays.includes(Number(button.dataset.day));
            button.classList.toggle("day--active", active);
            button.setAttribute("aria-pressed", String(active));
        }
    }

    function renderPermission() {
        const supported = "Notification" in window;
        const permission = supported ? Notification.permission : "unsupported";
        const messages = {
            granted: "Benachrichtigungen sind erlaubt.",
            default: "Noch nicht erlaubt — die App kann dich derzeit nicht erinnern.",
            denied: "Blockiert. Erlaube Benachrichtigungen in den Browser-Einstellungen dieser Seite.",
            unsupported: "Dieser Browser unterstützt keine Benachrichtigungen.",
        };
        el.permissionStatus.textContent = messages[permission];
        el.permissionStatus.dataset.state = permission;
        el.enableNotifications.hidden = permission !== "default";
        el.testNotification.hidden = permission !== "granted";
    }

    function renderNextReminder() {
        if (!state.trainingDays.length) {
            el.nextReminder.textContent = "Kein Trainingstag ausgewählt — es kommen keine Erinnerungen.";
            return;
        }
        const now = new Date();
        let next = null;
        for (let offset = 0; offset < 8 && !next; offset += 1) {
            const date = addDays(now, offset);
            if (!isTrainingDay(date)) {
                continue;
            }
            const due = reminderDateFor(date);
            if (due > now) {
                next = due;
            }
        }
        const parts = [];
        if (next) {
            parts.push(
                `Nächste Erinnerung: ${next.toLocaleString("de-DE", {
                    weekday: "long",
                    hour: "2-digit",
                    minute: "2-digit",
                })} Uhr`,
            );
        }
        if (state.nextMotivationAt) {
            parts.push(
                `nächster Spruch ca. ${new Date(state.nextMotivationAt).toLocaleTimeString("de-DE", {
                    hour: "2-digit",
                    minute: "2-digit",
                })} Uhr`,
            );
        }
        el.nextReminder.textContent = parts.join(" · ");
    }

    let toastTimer = null;
    function showToast(message) {
        el.toast.textContent = message;
        el.toast.hidden = false;
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(() => {
            el.toast.hidden = true;
        }, 3500);
    }

    function showQuote(quote) {
        el.quote.textContent = quote;
        state.lastQuote = quote;
        saveState();
    }

    // ------------------------------------------------------------ Verdrahtung

    el.checkin.addEventListener("click", () => {
        toggleCheckIn(true);
        showToast("Eingetragen. Serie läuft weiter.");
    });
    el.undoCheckin.addEventListener("click", () => toggleCheckIn(false));
    el.newQuote.addEventListener("click", () => showQuote(self.randomQuote(state.lastQuote)));
    el.enableNotifications.addEventListener("click", requestPermission);
    el.testNotification.addEventListener("click", async () => {
        const sent = await notify("Test 🔔", self.randomQuote(state.lastQuote), "gym-test");
        showToast(sent ? "Test-Benachrichtigung gesendet." : "Benachrichtigung konnte nicht gesendet werden.");
    });

    el.reminderTime.addEventListener("change", () => {
        state.reminderTime = el.reminderTime.value || DEFAULT_STATE.reminderTime;
        // Eine geänderte Uhrzeit darf den heutigen Termin wieder scharf schalten.
        state.lastReminderDate = null;
        saveState();
        render();
    });
    el.motivationInterval.addEventListener("change", () => {
        state.motivationIntervalHours = Number(el.motivationInterval.value);
        scheduleNextMotivation(new Date());
        saveState();
        render();
    });
    el.quietHoursToggle.addEventListener("change", () => {
        state.quietHours = el.quietHoursToggle.checked;
        saveState();
        render();
    });

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            tick();
        }
    });

    // ------------------------------------------------------------------ Start

    async function registerServiceWorker() {
        if (!("serviceWorker" in navigator)) {
            return;
        }
        try {
            swRegistration = await navigator.serviceWorker.register("sw.js");
            if ("periodicSync" in swRegistration) {
                // Nur installierte PWAs mit ausreichender "site engagement" bekommen
                // die Erlaubnis; scheitert das, bleibt der Ticker im Vordergrund.
                const status = await navigator.permissions
                    .query({ name: "periodic-background-sync" })
                    .catch(() => ({ state: "denied" }));
                if (status.state === "granted") {
                    await swRegistration.periodicSync.register("gym-motivation", {
                        minInterval: 60 * 60 * 1000,
                    });
                }
            }
        } catch (error) {
            console.warn("Service Worker konnte nicht registriert werden:", error);
        }
    }

    showQuote(state.lastQuote || self.randomQuote(null));
    render();
    // Erst registrieren, dann den ersten Termin prüfen: sonst müsste eine
    // fällige Erinnerung ohne aktiven Service Worker verschickt werden.
    registerServiceWorker().finally(() => {
        tick();
        window.setInterval(tick, TICK_INTERVAL_MS);
    });
})();
