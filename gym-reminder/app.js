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
        checkin: document.getElementById("checkin"),
        checkinText: document.getElementById("checkin-text"),
        undoCheckin: document.getElementById("undo-checkin"),
        quoteToggle: document.getElementById("quote-toggle"),
        quote: document.getElementById("quote"),
        why: document.getElementById("why"),
        whyText: document.getElementById("why-text"),
        newQuote: document.getElementById("new-quote"),
        calPrev: document.getElementById("cal-prev"),
        calNext: document.getElementById("cal-next"),
        calMonth: document.getElementById("cal-month"),
        calGrid: document.getElementById("cal-grid"),
        calSummary: document.getElementById("cal-summary"),
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
    /** Der im Kalender angezeigte Monat (immer der Erste des Monats). */
    let visibleMonth = startOfMonth(new Date());

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

    function startOfDay(date) {
        const copy = new Date(date);
        copy.setHours(0, 0, 0, 0);
        return copy;
    }

    function startOfMonth(date) {
        return new Date(date.getFullYear(), date.getMonth(), 1);
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

    /** Längste Kette aufeinanderfolgender Tage in der gesamten Historie. */
    function bestStreak() {
        const days = [...new Set(state.history)].sort();
        let best = 0;
        let run = 0;
        let previous = null;
        for (const entry of days) {
            const date = new Date(`${entry}T00:00:00`);
            run = previous && (date - previous) / 86_400_000 === 1 ? run + 1 : 1;
            best = Math.max(best, run);
            previous = date;
        }
        return best;
    }

    function setCheckIn(date, done) {
        const key = dateKey(date);
        if (done) {
            state.history = [...new Set([...state.history, key])].sort();
        } else {
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
                    showQuote(self.randomQuote(state.lastQuote));
                    notify("Zeit fürs Gym 🏋️", state.lastQuote, "gym-reminder");
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
                    showQuote(self.randomQuote(state.lastQuote));
                    notify("Motivation für dich 💪", state.lastQuote, "gym-motivation");
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
        renderCheckIn();
        renderCalendar();
        renderSettings();
        renderPermission();
        renderNextReminder();
    }

    function renderStreak() {
        const streak = currentStreak();
        el.streakCount.textContent = String(streak);
        el.streakLabel.textContent = streak === 1 ? "Tag in Folge" : "Tage in Folge";
    }

    function renderCheckIn() {
        const done = hasCheckIn(new Date());
        el.checkin.classList.toggle("checkin--done", done);
        el.checkinText.textContent = done ? "Erledigt — stark!" : "Ich war heute im Gym";
        el.checkin.disabled = done;
        el.undoCheckin.hidden = !done;
    }

    /** Setzt Spruch und Begründung; die Begründung bleibt eingeklappt. */
    function showQuote(text) {
        state.lastQuote = text;
        el.quote.textContent = text;
        el.whyText.textContent = self.explainQuote(text);
        saveState();
    }

    function toggleWhy(open) {
        const expanded = open ?? el.quoteToggle.getAttribute("aria-expanded") !== "true";
        el.quoteToggle.setAttribute("aria-expanded", String(expanded));
        el.why.hidden = !expanded;
    }

    function renderCalendar() {
        const today = startOfDay(new Date());
        const year = visibleMonth.getFullYear();
        const month = visibleMonth.getMonth();

        el.calMonth.textContent = visibleMonth.toLocaleDateString("de-DE", {
            month: "long",
            year: "numeric",
        });
        el.calNext.disabled = year === today.getFullYear() && month === today.getMonth();

        el.calGrid.innerHTML = "";
        for (const day of DAY_ORDER) {
            const head = document.createElement("span");
            head.className = "calendar__weekday";
            head.textContent = DAY_LABELS[day];
            el.calGrid.append(head);
        }

        // Montag ist die erste Spalte, `getDay()` zählt aber ab Sonntag.
        const offset = (new Date(year, month, 1).getDay() + 6) % 7;
        for (let index = 0; index < offset; index += 1) {
            const filler = document.createElement("span");
            filler.className = "calendar__day calendar__day--empty";
            el.calGrid.append(filler);
        }

        const daysInMonth = new Date(year, month + 1, 0).getDate();
        let trained = 0;
        let planned = 0;

        for (let dayOfMonth = 1; dayOfMonth <= daysInMonth; dayOfMonth += 1) {
            const date = new Date(year, month, dayOfMonth);
            const future = date > today;
            const done = hasCheckIn(date);
            const training = isTrainingDay(date);

            const cell = document.createElement("button");
            cell.type = "button";
            cell.className = "calendar__day";
            cell.textContent = String(dayOfMonth);

            if (done) {
                cell.classList.add("calendar__day--done");
                trained += 1;
            } else if (!training) {
                cell.classList.add("calendar__day--rest");
            } else if (!future) {
                cell.classList.add("calendar__day--missed");
            }
            if (training && !future) {
                planned += 1;
            }
            if (future) {
                cell.classList.add("calendar__day--future");
                cell.disabled = true;
            }
            if (date.getTime() === today.getTime()) {
                cell.classList.add("calendar__day--today");
            }

            const label = date.toLocaleDateString("de-DE", { dateStyle: "full" });
            const status = done ? "trainiert" : training ? "nicht trainiert" : "kein Trainingstag";
            cell.title = `${label}: ${status}`;
            cell.setAttribute("aria-label", `${label} — ${status}`);
            cell.setAttribute("aria-pressed", String(done));
            cell.addEventListener("click", () => setCheckIn(date, !done));
            el.calGrid.append(cell);
        }

        const best = bestStreak();
        const units = `${trained} ${trained === 1 ? "Einheit" : "Einheiten"} in diesem Monat`;
        el.calSummary.textContent = planned
            ? `${units} · ${planned} Trainingstage waren geplant · Bestwert ${best} ${best === 1 ? "Tag" : "Tage"}`
            : units;
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
            el.nextReminder.textContent =
                "Kein Trainingstag ausgewählt — es kommen keine Erinnerungen.";
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

    // ------------------------------------------------------------ Verdrahtung

    el.checkin.addEventListener("click", () => {
        setCheckIn(new Date(), true);
        showToast("Eingetragen. Serie läuft weiter.");
    });
    el.undoCheckin.addEventListener("click", () => setCheckIn(new Date(), false));
    el.quoteToggle.addEventListener("click", () => toggleWhy());
    el.newQuote.addEventListener("click", () => {
        showQuote(self.randomQuote(state.lastQuote));
        toggleWhy(false);
    });
    el.calPrev.addEventListener("click", () => {
        visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1);
        renderCalendar();
    });
    el.calNext.addEventListener("click", () => {
        visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1);
        renderCalendar();
    });
    el.enableNotifications.addEventListener("click", requestPermission);
    el.testNotification.addEventListener("click", async () => {
        showQuote(self.randomQuote(state.lastQuote));
        const sent = await notify("Test 🔔", state.lastQuote, "gym-test");
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

    // Ein gespeicherter Spruch ohne Begründung stammt aus einer älteren Liste.
    showQuote(
        state.lastQuote && self.explainQuote(state.lastQuote)
            ? state.lastQuote
            : self.randomQuote(null),
    );
    render();
    // Erst registrieren, dann den ersten Termin prüfen: sonst müsste eine
    // fällige Erinnerung ohne aktiven Service Worker verschickt werden.
    registerServiceWorker().finally(() => {
        tick();
        window.setInterval(tick, TICK_INTERVAL_MS);
    });
})();
