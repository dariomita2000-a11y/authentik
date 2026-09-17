/**
 * Motivationssprüche samt Begründung.
 *
 * Wird sowohl von der Seite (`<script src="quotes.js">`) als auch vom
 * Service Worker (`importScripts("quotes.js")`) geladen, deshalb hängt die
 * Liste am globalen Objekt und nicht an `window`. `desktop_reminder.py`
 * liest dieselbe Datei, damit es nur eine Quelle für die Texte gibt.
 */
(function attachQuotes(global) {
    global.GYM_QUOTES = [
        {
            text: "Der einzige schlechte Workout ist der, den du nicht gemacht hast.",
            why: "Du vergleichst dein Training mit dem perfekten, das du dir vorgestellt hast. Der ehrliche Vergleich lautet aber: Training oder Couch.",
        },
        {
            text: "Du musst heute nicht dein Bestes geben. Du musst nur anfangen.",
            why: "Der Anspruch, Bestleistung zu bringen, ist der häufigste Grund, gar nicht erst loszugehen. Senk die Hürde auf „umziehen und hinfahren“.",
        },
        {
            text: "Motivation bringt dich zur Tür. Disziplin bringt dich rein.",
            why: "Motivation ist ein Gefühl und schwankt täglich. Feste Zeiten und Abläufe funktionieren auch an den Tagen, an denen das Gefühl fehlt.",
        },
        {
            text: "Dein zukünftiges Ich schaut gerade zu. Gib ihm etwas zum Feiern.",
            why: "Wir behandeln unser späteres Ich wie eine fremde Person. Wer es sich konkret vorstellt, entscheidet sich leichter für die unbequeme Option.",
        },
        {
            text: "45 Minuten sind 3 % deines Tages. Die hast du.",
            why: "„Keine Zeit“ heißt fast immer „keine Priorität“. In Prozent ausgedrückt schrumpft die Ausrede auf ihre echte Größe.",
        },
        {
            text: "Schwer wird es sowieso. Such dir aus, ob im Gym oder später.",
            why: "Die Anstrengung verschwindet nicht, wenn du sie aufschiebst. Sie wird nur teurer: steifer Rücken, schlechterer Schlaf, weniger Kraft.",
        },
        {
            text: "Jede Wiederholung zählt, auch die, die sich nach nichts anfühlt.",
            why: "Dein Körper passt sich an die Summe aller Sätze an, nicht an den einen spektakulären. Das Gefühl im Moment ist ein schlechter Messwert.",
        },
        {
            text: "Ein mittelmäßiges Training schlägt jedes perfekte, das ausfällt.",
            why: "Der perfekte Plan existiert nur im Kopf. Was zählt, ist der Plan, den du an einem miesen Dienstag noch durchziehst.",
        },
        {
            text: "Du bereust nie, dass du hingegangen bist.",
            why: "Geh deine letzten zehn Trainings durch: Nach welchem ging es dir schlechter als davor? Das Bereuen betrifft immer nur die ausgefallenen.",
        },
        {
            text: "Stärke ist das Ergebnis von langweiliger Wiederholung.",
            why: "Fortschritt entsteht, weil du dieselben paar Übungen über Monate leicht steigerst — nicht aus ständig neuen Programmen.",
        },
        {
            text: "Fortschritt ist leise. Er kommt trotzdem.",
            why: "Kraft wächst in Wochen, nicht in Tagen. Wer täglich nach sichtbaren Beweisen sucht, hört auf, bevor die ersten kommen.",
        },
        {
            text: "Zieh die Schuhe an. Den Rest regelt der Weg dorthin.",
            why: "Der Widerstand sitzt vor dem Start, nicht im Training. Bist du erst unterwegs, ist die Entscheidung praktisch gefallen.",
        },
        {
            text: "Deine Ausreden sind kreativer als dein Trainingsplan. Ändere das.",
            why: "Ausreden entstehen spontan, Pläne nicht. Wer Tag, Uhrzeit und Übungen vorher festlegt, muss im Moment nichts mehr verhandeln.",
        },
        {
            text: "Kleine Gewichte, saubere Form, langer Atem.",
            why: "Technik entscheidet, wie lange du trainieren kannst. Wer zu früh zu schwer lädt, kauft ein paar Wochen Fortschritt mit Monaten Pause.",
        },
        {
            text: "Nicht jeder Tag ist ein PR-Tag. Erscheinen reicht.",
            why: "Schlaf, Stress und Essen schwanken, deine Leistung folgt. An solchen Tagen ist ein Erhaltungs-Training der Gewinn.",
        },
        {
            text: "Konstanz schlägt Intensität. Jedes Mal.",
            why: "Dreimal pro Woche über ein Jahr sind rund 150 Einheiten. Zwei brutale Wochen mit anschließendem Abbruch sind zehn.",
        },
        {
            text: "Der Körper schafft, was der Kopf ihm zutraut.",
            why: "Die meisten brechen ab, bevor die Muskeln wirklich am Ende sind. Solange die Technik sauber bleibt, ist oft noch eine Wiederholung drin.",
        },
        {
            text: "Heute trainieren heißt morgen leichter atmen.",
            why: "Kraft und Ausdauer zahlen direkt auf den Alltag ein: Treppen, Einkäufe, langes Stehen. Der Effekt zeigt sich außerhalb des Gyms.",
        },
        {
            text: "Wer aufhört, wird nicht ausgeruhter, nur unfitter.",
            why: "Nach ein bis zwei Wochen Pause baut der Körper spürbar ab. Die Erholung, die du suchst, kommt aus Schlaf und Essen, nicht aus Aufgeben.",
        },
        {
            text: "Du bist einen Satz weiter als gestern.",
            why: "Im Spiegel siehst du kurzfristig nichts. Im Trainingslog siehst du sofort, dass etwas passiert ist — deshalb schreib es auf.",
        },
        {
            text: "Selbstachtung wird im Gym trainiert, nicht nur Muskeln.",
            why: "Jedes eingehaltene Versprechen an dich selbst ist ein Beleg, dass dein Wort zählt. Das wirkt weit über das Training hinaus.",
        },
        {
            text: "Müde ist ein Gefühl, kein Grund.",
            why: "Leichte Müdigkeit verschwindet bei den meisten nach dem Aufwärmen. Echte Erschöpfung erkennst du daran, dass sie danach bleibt.",
        },
        {
            text: "Die Hantel fragt nicht nach deiner Laune.",
            why: "Das Gewicht ist immer gleich schwer. Genau das macht Training zu einem verlässlichen Fixpunkt an unruhigen Tagen.",
        },
        {
            text: "Der Anfang ist das schwerste Gewicht des Tages.",
            why: "Die Hürde liegt beim Losgehen. Mach dir den Start leicht — Tasche gepackt, Plan fertig, kurzer Weg — dann fällt der Rest.",
        },
        {
            text: "Baue Gewohnheiten, nicht Stimmungen.",
            why: "Gewohnheiten hängen an Auslösern: gleicher Tag, gleiche Zeit, gleicher Weg. Stimmungen kannst du nicht planen, Auslöser schon.",
        },
        {
            text: "Ein Prozent besser pro Tag ist doppelt so gut in 70 Tagen.",
            why: "Kleine Steigerungen verzinsen sich. 2,5 kg mehr pro Monat auf einer Übung sind nach einem Jahr 30 kg.",
        },
        {
            text: "Trainiere heute, damit du mit 70 noch Treppen nimmst.",
            why: "Muskelmasse und Kraft sind die beste Vorsorge gegen Stürze und Unselbstständigkeit im Alter. Aufgebaut wird sie jetzt.",
        },
        {
            text: "Niemand hat je bereut, sich bewegt zu haben.",
            why: "Das Nachher ist verlässlich besser als das Vorher: Kopf freier, Schlaf tiefer. Nur das Vorher beschwert sich lautstark.",
        },
        {
            text: "Der Plan funktioniert nur, wenn du auftauchst.",
            why: "Der beste Trainingsplan der Welt hat die Wirkung null, solange du ihn liest statt ihn zu machen.",
        },
        {
            text: "Halte die Serie am Leben. Ein Tag reicht schon.",
            why: "Eine laufende Serie wird selbst zum Antrieb: Je länger sie ist, desto weniger willst du derjenige sein, der sie abreißen lässt.",
        },
        {
            text: "Du gegen gestern. Sonst niemand.",
            why: "Der Vergleich mit anderen im Gym sagt nichts über deinen Fortschritt — andere Hebel, andere Jahre, anderer Startpunkt.",
        },
        {
            text: "Erst kommt die Routine, dann kommt die Form.",
            why: "Die ersten Wochen haben nur eine Aufgabe: das Hingehen selbstverständlich machen. Die sichtbaren Ergebnisse kommen danach.",
        },
        {
            text: "Zwei Stunden Serien schauen ist Zeit. Eine Stunde Gym auch.",
            why: "Zeit fehlt selten wirklich, sie ist nur schon vergeben. Schau eine Woche lang nach, woran — die Antwort ist unbequem konkret.",
        },
        {
            text: "Wenn du keine Lust hast, ist es genau das richtige Training.",
            why: "Die Einheiten, die du nur aus Disziplin machst, bauen die Gewohnheit. Die mit Lust hättest du ohnehin gemacht.",
        },
        {
            text: "Stark werden ist ein Marathon aus kurzen Einheiten.",
            why: "Niemand wird in einem Training stark. Jede einzelne Einheit ist ein Baustein, der ohne die anderen nichts wert wäre.",
        },
        {
            text: "Der beste Zeitpunkt war gestern. Der zweitbeste ist jetzt.",
            why: "Verpasste Wochen holst du nicht nach. Aber der Verlauf ab heute hängt nur an der Entscheidung von heute.",
        },
        {
            text: "Deine Serie ist ein Versprechen an dich selbst.",
            why: "Einen Termin mit einem Freund würdest du nicht kommentarlos platzen lassen. Behandle deinen Trainingstermin genauso.",
        },
        {
            text: "Kein Spiegel misst Disziplin. Dein Kalender schon.",
            why: "Der Spiegel zeigt Tagesform, Licht und Laune. Der Kalender zeigt, was du tatsächlich getan hast — die ehrlichere Rückmeldung.",
        },
        {
            text: "Auch ein leichter Tag hält die Gewohnheit am Leben.",
            why: "Wenn alles gegen ein volles Training spricht, mach die Mini-Version: 20 Minuten. Die Serie bleibt, die Hürde morgen bleibt niedrig.",
        },
    ];

    /** Liefert einen zufälligen Spruchtext, möglichst nicht denselben wie zuletzt. */
    global.randomQuote = function randomQuote(previous) {
        const quotes = global.GYM_QUOTES;
        if (quotes.length < 2) {
            return quotes[0].text;
        }
        let text = previous;
        while (text === previous) {
            text = quotes[Math.floor(Math.random() * quotes.length)].text;
        }
        return text;
    };

    /** Die Begründung zu einem Spruchtext, oder "" wenn es ihn nicht mehr gibt. */
    global.explainQuote = function explainQuote(text) {
        const match = global.GYM_QUOTES.find((quote) => quote.text === text);
        return match ? match.why : "";
    };
})(typeof self !== "undefined" ? self : globalThis);
