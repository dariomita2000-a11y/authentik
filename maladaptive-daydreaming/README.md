# Tagtraum – ein kurzer Film über Maladaptive Daydreaming

Ein ruhiger, cineastischer Kurzfilm im Hochformat 9:16, gedacht für TikTok, YouTube Shorts und Instagram Reels.

| | |
|---|---|
| Länge | 2:51 (171 s). Der vollständige Sprechertext lässt sich in ruhigem Tempo nicht in 90 s sprechen. |
| Format | 1080 × 1920, 30 fps, H.264 / AAC 48 kHz |
| Stimme | ElevenLabs, Modell `eleven_v4`, Stimme „Jörg M.“ (tief, warm, ruhig, Deutsch) |
| Klang | Selbst synthetisiert (`src/ambient.py`): leise, verhallte Klaviertöne, dunkler Drone, Raumluft. Keine Beats, kein Rhythmus. |
| Bilder | Prozedural gerendert (`src/scenes.py`): Gegenlicht-Silhouetten, Mondlicht, Bokeh, Bloom, Filmkorn |
| Untertitel | Deutsch, nach Sinneinheiten von Hand gesetzt (`src/cues_de.txt`), eingebrannt sowie als `untertitel_de.srt` |
| Lautheit | −14 LUFS integriert, −1,5 dBTP |

## Dramaturgie

1. **Realität (0:00–0:17).** Handy-Licht im Dunkeln, Kopfhörer werden aufgesetzt, die Figur läuft im Mondlicht hin und her und verblasst langsam zu Nachbildern.
2. **Übergang (0:17–0:21).** Hinter dem Kopf wird es langsam warm, und Lichtpartikel steigen auf.
3. **Fantasie (0:21–1:24).** Nächtliche Fahrt durch die Lichter der Stadt, Menschen, die hinsehen, ein Gegenüber im Gegenlicht, das Meer bei Sonnenuntergang, zwei Profile, die sich näherkommen. Danach überlagern sich Zimmer und Fantasie, und das Fenster glüht im Abendlicht. Die Szene endet in einem überstrahlten Höhepunkt.
4. **Das Lied endet (1:24–1:43).** Der Fortschrittsbalken erreicht das Ende, die Kopfhörer kommen ab. Das Zimmer ist kalt und still, und die Musik setzt aus. Dieser Moment bleibt bewusst lange stehen.
5. **Zurück (1:43–1:57).** Das nächste Lied wird gestartet, und warmes Licht sickert wieder ins Fenster.
6. **Einordnung (1:57–2:24).** Regen am Fenster, die Figur sitzt am Boden.
7. **Sehnsucht (2:24–2:51).** Eine verblasste Erinnerung an das Meer. Der andere Mensch löst sich in Licht auf, die Figur steht allein am Fenster, und das Bild verlischt.

## Neu erzeugen

```bash
python3 src/align.py audio/voice_joerg.mp3 sprechertext.txt audio/align_raw.json   # Satz-Zeitpunkte
python3 src/timeline.py audio/voice_joerg.mp3 audio/align_raw.json audio/voice_edit.wav timeline.json
python3 -c "import json;json.dump(json.load(open('timeline.json'))['cues'],open('audio/cues.json','w'))"
python3 src/ambient.py audio/cues.json audio/ambient.wav                            # Klangteppich
python3 src/subtitles.py timeline.json build/untertitel.ass build/untertitel_de.srt src/cues_de.txt audio/voice_edit.wav
(cd src && python3 director.py ../timeline.json ../build/video_nosound.mp4)          # Bild (~20 min, 4 Kerne)
./make_final.sh
```

Testbilder rendern: `(cd src && python3 director.py ../timeline.json /tmp/still --stills 10,50,90)`.
