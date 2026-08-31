/**
 * Motivationssprüche für Erinnerungen und Benachrichtigungen.
 *
 * Wird sowohl von der Seite (`<script src="quotes.js">`) als auch vom
 * Service Worker (`importScripts("quotes.js")`) geladen, deshalb hängt die
 * Liste am globalen Objekt und nicht an `window`.
 */
(function attachQuotes(global) {
    global.GYM_QUOTES = [
        "Der einzige schlechte Workout ist der, den du nicht gemacht hast.",
        "Du musst heute nicht dein Bestes geben. Du musst nur anfangen.",
        "Motivation bringt dich zur Tür. Disziplin bringt dich rein.",
        "Dein zukünftiges Ich schaut gerade zu. Gib ihm etwas zum Feiern.",
        "45 Minuten sind 3 % deines Tages. Die hast du.",
        "Schwer wird es sowieso. Such dir aus, ob im Gym oder später.",
        "Jede Wiederholung zählt, auch die, die sich nach nichts anfühlt.",
        "Ein mittelmäßiges Training schlägt jedes perfekte, das ausfällt.",
        "Du bereust nie, dass du hingegangen bist.",
        "Stärke ist das Ergebnis von langweiliger Wiederholung.",
        "Fortschritt ist leise. Er kommt trotzdem.",
        "Zieh die Schuhe an. Den Rest regelt der Weg dorthin.",
        "Deine Ausreden sind kreativer als dein Trainingsplan. Ändere das.",
        "Kleine Gewichte, saubere Form, langer Atem.",
        "Nicht jeder Tag ist ein PR-Tag. Erscheinen reicht.",
        "Konstanz schlägt Intensität. Jedes Mal.",
        "Der Körper schafft, was der Kopf ihm zutraut.",
        "Heute trainieren heißt morgen leichter atmen.",
        "Wer aufhört, wird nicht ausgeruhter, nur unfitter.",
        "Du bist einen Satz weiter als gestern.",
        "Selbstachtung wird im Gym trainiert, nicht nur Muskeln.",
        "Müde ist ein Gefühl, kein Grund.",
        "Die Hantel fragt nicht nach deiner Laune.",
        "Der Anfang ist das schwerste Gewicht des Tages.",
        "Baue Gewohnheiten, nicht Stimmungen.",
        "Ein Prozent besser pro Tag ist doppelt so gut in 70 Tagen.",
        "Trainiere heute, damit du mit 70 noch Treppen nimmst.",
        "Niemand hat je bereut, sich bewegt zu haben.",
        "Der Plan funktioniert nur, wenn du auftauchst.",
        "Schweiß ist einfach nur Fett, das weint.",
        "Halte die Serie am Leben. Ein Tag reicht schon.",
        "Du gegen gestern. Sonst niemand.",
        "Erst kommt die Routine, dann kommt die Form.",
        "Zwei Stunden Serien schauen ist Zeit. Eine Stunde Gym auch.",
        "Wenn du keine Lust hast, ist es genau das richtige Training.",
        "Stark werden ist ein Marathon aus kurzen Einheiten.",
        "Der beste Zeitpunkt war gestern. Der zweitbeste ist jetzt.",
        "Deine Serie ist ein Versprechen an dich selbst.",
        "Kein Spiegel misst Disziplin. Dein Kalender schon.",
        "Auch ein leichter Tag hält die Gewohnheit am Leben.",
    ];

    /** Liefert einen zufälligen Spruch, möglichst nicht denselben wie zuletzt. */
    global.randomQuote = function randomQuote(previous) {
        const quotes = global.GYM_QUOTES;
        if (quotes.length < 2) {
            return quotes[0];
        }
        let quote = previous;
        while (quote === previous) {
            quote = quotes[Math.floor(Math.random() * quotes.length)];
        }
        return quote;
    };
})(typeof self !== "undefined" ? self : globalThis);
