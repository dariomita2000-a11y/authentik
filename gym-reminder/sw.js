/**
 * Service Worker: Offline-Cache, Notification-Klicks und — wo verfügbar —
 * Motivationssprüche über Periodic Background Sync, also auch dann, wenn die
 * App gerade nicht offen ist.
 */
/* global importScripts, clients */
importScripts("quotes.js");

const CACHE = "gym-reminder-v1";
const ASSETS = [
    "./",
    "index.html",
    "styles.css",
    "app.js",
    "quotes.js",
    "manifest.webmanifest",
    "icons/icon.svg",
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches
            .keys()
            .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
            .then(() => self.clients.claim()),
    );
});

self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") {
        return;
    }
    event.respondWith(
        caches.match(event.request).then((cached) => cached || fetch(event.request)),
    );
});

/** Notification anzeigen — auf Wunsch der Seite oder aus dem Hintergrund. */
function showQuoteNotification(title) {
    return self.registration.showNotification(title, {
        body: self.randomQuote(null),
        tag: "gym-motivation",
        renotify: true,
        icon: "icons/icon.svg",
        badge: "icons/icon.svg",
        lang: "de",
    });
}

self.addEventListener("periodicsync", (event) => {
    if (event.tag === "gym-motivation") {
        event.waitUntil(showQuoteNotification("Motivation für dich 💪"));
    }
});

self.addEventListener("message", (event) => {
    if (event.data && event.data.type === "show-quote") {
        event.waitUntil(showQuoteNotification(event.data.title || "Motivation für dich 💪"));
    }
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
            for (const client of windows) {
                if ("focus" in client) {
                    return client.focus();
                }
            }
            return clients.openWindow("./");
        }),
    );
});
