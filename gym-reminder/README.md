# Gym Reminder

Eine kleine App, die dich täglich ans Training erinnert und dir regelmäßig
Motivationssprüche als Benachrichtigung schickt.

Enthalten sind zwei Wege, weil Browser Benachrichtigungen nur eingeschränkt im
Hintergrund schicken dürfen:

1. **Web-App (PWA)** — installierbar auf Handy und Desktop, mit Streak-Zähler.
2. **`desktop_reminder.py`** — ein Hintergrundskript für zuverlässige
   Erinnerungen am Rechner, auch wenn kein Browser offen ist.

Beide nutzen dieselbe Spruchsammlung aus `quotes.js`.

## Web-App starten

Ein Service Worker und Benachrichtigungen brauchen `http(s)://` — ein
Doppelklick auf `index.html` (`file://`) reicht nicht:

```bash
cd gym-reminder
python3 -m http.server 8000
```

Dann <http://localhost:8000> öffnen, **„Benachrichtigungen erlauben“** klicken
und die Einstellungen anpassen:

- **Erinnerung um** — Uhrzeit der täglichen Gym-Erinnerung (Standard 18:00).
- **Trainingstage** — an welchen Wochentagen erinnert wird.
- **Motivationssprüche** — Abstand der zusätzlichen Motivations-Benachrichtigungen.
- **Nachtruhe** — zwischen 22 und 7 Uhr kommen keine Sprüche.

Der große Button trägt das heutige Training ein und hält die Serie (🔥) am
Leben. Alles liegt lokal im Browser (`localStorage`); es gibt keinen Server und
keine Konten.

**Kalender:** Der Monatskalender zeigt grün, an welchen Tagen du trainiert
hast, schraffiert die verpassten Trainingstage und gestrichelt die Tage, die
gar keine Trainingstage sind. Ein Tipp auf einen vergangenen Tag trägt ihn nach
oder streicht ihn wieder; mit ‹ und › blätterst du durch die Monate.

**Sprüche mit Begründung:** Ein Tipp auf den Spruch klappt auf, warum er
funktioniert — statt nur einen Satz zu lesen, siehst du, was dahintersteckt.

### Auf dem Handy installieren

Damit die App als eigenständiges Icon läuft, muss sie über HTTPS erreichbar
sein — z. B. via GitHub Pages, Netlify oder einem eigenen Webserver. Danach:

- **iOS/Safari:** Teilen → „Zum Home-Bildschirm“. Benachrichtigungen
  funktionieren ab iOS 16.4 **nur** für die installierte Variante.
- **Android/Chrome:** Menü → „App installieren“.

### Wie zuverlässig sind die Erinnerungen?

Ehrliche Antwort: Ohne Server gibt es keine garantierte Zustellung.

- Ist die App (auch nur im Hintergrund) geöffnet, prüft ein Timer alle 15
  Sekunden, ob eine Erinnerung fällig ist — das klappt zuverlässig.
- Als installierte PWA nutzt Chrome zusätzlich *Periodic Background Sync*, dann
  kommen Sprüche auch bei geschlossener App (Intervall bestimmt der Browser).
- Wird die App tagelang gar nicht geöffnet, verpasste Erinnerungen werden
  stumm verworfen, statt sie gesammelt nachzuliefern.

Für garantierte Zustellung bräuchte es Web Push mit VAPID-Schlüsseln und einen
kleinen Server, der die Benachrichtigungen auslöst. Alternativ das Skript unten.

## Desktop-Skript

Läuft ohne Abhängigkeiten mit Python 3.10+ und nutzt die Benachrichtigungen des
Betriebssystems (`osascript` auf macOS, `notify-send` auf Linux, PowerShell auf
Windows):

```bash
python3 desktop_reminder.py                        # 18:00 Uhr, Spruch alle 4 h
python3 desktop_reminder.py --time 07:30 --every 2
python3 desktop_reminder.py --days mo,mi,fr
python3 desktop_reminder.py --test                 # einmal senden und beenden
```

Dauerhaft im Hintergrund: als `launchd`-Agent (macOS), `systemd --user`-Service
(Linux) oder Autostart-Verknüpfung (Windows) einrichten.

## Sprüche anpassen

Alle Texte stehen in `quotes.js` im Array `GYM_QUOTES`. Jeder Eintrag hat zwei
Felder: `text` ist der Spruch, `why` die Begründung, die in der App aufklappt.
Ergänzen, speichern, Seite neu laden — das Desktop-Skript liest dieselbe Datei
und nutzt daraus nur `text`.

## Dateien

| Datei                  | Zweck                                                        |
| ---------------------- | ------------------------------------------------------------ |
| `index.html`           | Aufbau der Oberfläche                                        |
| `app.js`               | Zustand, Streak-Logik, Scheduler für die Erinnerungen        |
| `quotes.js`            | Motivationssprüche (gemeinsame Quelle für App und Skript)    |
| `styles.css`           | Gestaltung                                                   |
| `sw.js`                | Service Worker: Offline-Cache, Hintergrund-Benachrichtigungen |
| `manifest.webmanifest` | PWA-Metadaten für die Installation                           |
| `desktop_reminder.py`  | Hintergrundskript für Desktop-Benachrichtigungen             |
