# Evaluation: DRM-Streaming, Design, Stabilität und Performance

Stand: November 2026, Basis Browser/Runtime 0.15.0, Engine 0.1.0 (Debian
Chromium 156). Ausgewertet wurden `pllanaio/mgu-browser`, `pllanaio/bmw-airplay`,
`robertnisipeanu/mgu-store` (Store, Deploy, `mgu-render`, Uplink),
`robertnisipeanu/idrive-apps` (cluster-render, waze-on-cluster mit Intel Media SDK),
`cauliflowermossgrape/idrive7-apps` (App-Kit, renderd, Emulator) und
`IterioDev/car-apps` (Drive-Recorder-Player, Screencast, Overlays).

Alle Messwerte unten stammen aus dieser Entwicklungsumgebung (x86_64, Chrome for
Testing 153 mit Googles Widevine-CDM 4.10.3112.0). Sie ersetzen keinen Test auf
der Headunit; die offenen Punkte sind am Ende gesammelt.

## 1. Kurzfassung

**Der Browser kann Netflix, Disney+, Prime Video & Co. grundsätzlich abspielen.**
Die MGU ist x86_64 (Intel Apollo Lake) und damit dieselbe Plattform, auf der
Linux-Chrome diese Dienste offiziell unterstützt. Der einzige legale und
realistische Weg ist **Chromium + Googles Widevine-CDM (Sicherheitsstufe L3,
Software)** – also genau das, was Desktop-Linux-Chrome tut.

Nachgewiesen in dieser Umgebung:

| Prüfung | Ergebnis |
| --- | --- |
| Hint-Registrierung des Browsers mit echtem Google-CDM, `--headless`, Sandbox an | Ohne CDM `NotSupportedError`, mit CDM `MediaKeys` erstellt |
| Robustheit | `SW_SECURE_CRYPTO` ja, `SW_SECURE_DECODE` ja, `HW_SECURE_ALL` nein → **L3** |
| Verschlüsselungsschemata | `cenc` und `cbcs` |
| HDCP (`getStatusForPolicy`) | `output-restricted` – identisch auch bei Chrome unter X11, also normaler Linux-Zustand |
| Chromiums Component-Updater lädt Widevine selbst | Registriert das Widevine-Modul und kontaktiert Googles Update-Server (`dl.google.com`, `edgedl.me.gvt1.com`); hier vom Netzwerk-Proxy blockiert |
| `navigator.webdriver` | Vorher `true` (Bot-Merkmal), jetzt `false` |

**Was fehlte**, damit das im Auto funktioniert, und was dieser Stand ändert:

1. **Kein CDM auf der Headunit.** Neu: *Einstellungen → Medien & Streaming →
   „Widevine laden“* lässt die installierte Chromium-Engine das Modul über ihren
   eigenen Component-Updater von Google holen – wie jedes Desktop-Chromium. Es wird
   persistent unter `/var/opt/mgu-browser/data/cdm-component` abgelegt, geprüft und
   ab dem nächsten Browserstart verwendet. Das Projekt verteilt weiterhin kein CDM.
2. **Automatisierungsmerkmale.** `--headless` + `--remote-debugging-pipe` setzen
   `navigator.webdriver=true`; Client Hints enthielten nur „Chromium“ ohne die
   GREASE-Marke, die jedes echte Chromium sendet; der gemeldete Bildschirm war
   800×600 hinter einem größeren Fenster. Genau solche Merkmale lösen bei Netflix,
   Disney+ und Google Login-/Kontofehler oder CAPTCHAs aus (vgl. den offenen
   „allgemeinen Netflix-Kontofehler“ und das Google-429 im Testbericht 0.15.0).
   Alle drei sind behoben (Details Abschnitt 3).
3. **Diagnose.** Die Medienprüfung meldet jetzt Sicherheitsstufe, Robustheit,
   `cbcs`, HDCP und den Bereitstellungsstatus.

**Erwartete Qualität:** L3 auf Linux bedeutet bei den Anbietern üblicherweise
höchstens 720p (Netflix), bei manchen Titeln/Anbietern weniger. Für das
1920×720-Display mit 1280×720-Screencast ist das passend. 1080p/4K erfordern L1
(Hardware-Sicherheitspfad mit Googles Gerätezertifizierung) – auf der MGU nicht
erreichbar.

## 2. Bewertung der Alternativen („notfalls eigene App-Clients“)

| Weg | Bewertung |
| --- | --- |
| **Chromium + Widevine L3 (dieser Browser)** | Einziger legaler, technisch tragfähiger Weg. Gleicher Pfad wie Linux-Chrome, den die Anbieter offiziell unterstützen. |
| AirPlay (bmw-airplay) | Netflix/Disney+ blockieren Bildschirmspiegelung geschützter Inhalte (schwarzes Bild); AirPlay-Videoübergabe nutzt FairPlay, dessen Schlüssel nur Apple-zertifizierte Empfänger haben. Für DRM-Inhalte ausgeschlossen, für alles andere weiterhin gut. |
| CarPlay / Android Auto | Keine Video-Apps vorgesehen; DRM-Ausgabe an fremde Displays gesperrt. |
| Eigene native Clients (Netflix/Disney+-API) | Brauchen dasselbe Widevine-CDM *plus* private, signierte Anbieter-APIs (bei Netflix z. B. MSL mit gerätespezifischen Schlüsseln). Ohne Anbieterpartnerschaft nicht legal umsetzbar; bringt keinen Vorteil gegenüber dem Browser. |
| Android-Apps (Waydroid o. ä.) | Benötigt Android-Widevine (L3/L1) aus einem zertifizierten Gerät; nicht legal beschaffbar, enormer Ressourcenbedarf. |
| Widevine-Schlüssel extrahieren / Streams entschlüsseln | **Kein Weg für dieses Projekt.** Umgehung wirksamer technischer Schutzmaßnahmen (§ 95a UrhG), Verstoß gegen Anbieter-AGB; Google sperrt extrahierte Geräteschlüssel zudem regelmäßig. Wird hier weder umgesetzt noch vorbereitet. |

Fazit: **Kein eigener App-Client nötig.** Die Arbeit gehört in die Browser-Engine,
Bot-Unauffälligkeit, CDM-Bereitstellung und – für flüssiges Bild – in den
Videopfad (Abschnitt 4).

## 3. Umgesetzte Änderungen

| Bereich | Änderung | Datei |
| --- | --- | --- |
| DRM | Widevine über Chromiums Component-Updater: getrennter, sichtbarloser Engine-Lauf (`--ozone-platform=headless`, Sandbox an, `--component-updater=fast-update`) mit eigenem persistentem Datenordner; endet, sobald eine vollständige, gültige x86_64-Version vorliegt (Timeout 5 min, Prozessgruppe wird beendet). Kein Download, Entpacken oder Ausführen in Node. | `src/browser_cdm_provision.js` |
| DRM | Dritte CDM-Quelle `cdmCache`: neueste gültige Version aus dem Component-Cache. Reihenfolge: Administrator (`cdm.json`) → Entwicklung (`MGU_BROWSER_CDM_DIRECTORY`) → Component-Cache. Gleiche Eigentümer-/Symlink-/Manifest-/ELF-Prüfungen. | `src/browser_drm.js` |
| DRM-Diagnose | Robustheit (L1/L3), `cbcs`, HDCP-Status, Quelle und Bereitstellungsphase in `mediaCapabilities`. | `src/browser_drm.js`, `src/browser_media.js` |
| Bedienung | „Widevine laden / aktualisieren“ mit Fortschritt; Statuszeile zeigt „Widevine L3 4.10…“. | `apps/mgu_browser/chromium_frontend.js`, `src/browser_locale.js` |
| Backend | IPC `cdmProvision`, `cdmStatus`, Ereignis `cdm`; Abbruch beim Dienstende. | `backend/server.js`, `dev/backend.js` |
| Bot-Merkmale | `--disable-blink-features=AutomationControlled` (`navigator.webdriver=false`); mit `WebCodecs` zusammengeführt, weil Chromium nur den letzten Schalter beachtet. | `src/browser_session.js` |
| Bot-Merkmale | `--screen-info` = Browserfläche statt 800×600. | `src/browser_session.js` |
| Client Hints | GREASE-Marke nach Chromiums Algorithmus (Zeichen/Version/Reihenfolge aus der Hauptversion). Gegen natives Chrome 153 verifiziert: `Chromium`, `Not_A Brand 8.0.0.0`. Keine fremde Marke, kein fremdes OS. | `src/browser_identity.js` |

Tests: 156/156 Unit-Tests (vorher 151) als unprivilegierter Nutzer, darunter neue
für Cache-Auswahl, Bereitstellung (Erfolg, Timeout, Engine-Ende, Abbruch,
Prozessende) und GREASE. Integration mit echtem Chromium und Google-CDM siehe
Kurzfassung.

## 4. Performance – größter Hebel: Videopfad über `mgu-render`

Heutiger Bildweg pro Frame:

```
Chromium-Compositor → JPEG (q75) → base64 in CDP-JSON → Node → nativer JPEG-Decoder
→ RGBA (1280×720×4 = 3,7 MB) → Zeilen-Diff in JS → Pixmap-Upload über Socket → Renderer → GPU
```

Bei 30 fps sind das ~110 MB/s RGBA durch Node und Sockets auf einem Apollo-Lake-SoC.
`mgu-render` (mgu-store) bietet seit Protokoll 4 einen **Videokanal**: ein Player
schreibt **I420-Frames in `/dev/shm/mgu-video-<name>`** (Ringpuffer mit 1–4
Slots, 64-Byte-Header „MGVF“), die App zeichnet sie mit Op 19 in ein Rechteck; der
Renderer prüft alle 5 ms auf neue Frames und lädt sie selbst auf die GPU.
`bmw-airplay` nutzt das bereits (`gstmguvideosink.c`), IterioDevs YouTube-Player
`mgu-ytplay` ebenso.

Empfohlener Umbau (Roadmap, Headunit-Test nötig):

1. **JPEG → I420 direkt** im nativen Decoder (`tjDecompressToYUV2` von
   libjpeg-turbo): keine Farbraumkonvertierung, 1,4 MB statt 3,7 MB pro Frame.
2. **Schreiben ins MGVF-Shared-Memory** aus dem Backend (Eigentümer: Backend-UID
   oder `nobody`, wie das Protokoll verlangt), 3 Slots.
3. **Im Video-Vollbild** die Seite als VIDEO-Op zeichnen statt als Pixmap; die
   Browserleiste bleibt als normale Pixmap. Zeilen-Diff/Upload entfällt im
   Vollbild komplett. Grenzen: ≤ 2048 px Kantenlänge, 12 MiB pro App – 1280×720 und
   1920×720 passen.
4. Optional: im Vollbild höhere JPEG-Qualität (z. B. 85) oder `maxWidth` 1920 –
   erst messen, wenn 1–3 Bandbreite freigeben.

Erwartung: deutlich weniger Node-CPU und Socket-Last, stabilere 30 fps bei Video.
Langfristig (großer Aufwand): Chromium direkt per Wayland/dmabuf an den
HMI-Compositor (renderd/mgu-render „embed“, zero-copy) mit VA-API-Dekodierung –
der Intel-Media-SDK-Einsatz in `waze-on-cluster` zeigt, dass die Hardware-Decoder
der MGU nutzbar sind. Mit L3 dekodiert allerdings meist das CDM selbst in
Software; der Gewinn läge dann vor allem im Wegfall der JPEG-Kette.

Weitere Punkte:

- `--disable-gpu` bleibt richtig, solange der Screencast-Pfad genutzt wird.
- Bildrate an die Inhalte koppeln: außerhalb von Video/Scrollen 10–15 fps reichen.
- Netflix/Disney+ wählen die Bitrate nach Fensterbreite: Viewport 1280 statt
  Display-Breite spart Bandbreite und CPU bei gleicher Darstellung.

## 5. Stabilität

- **CDM-Updates:** Google sperrt alte Widevine-Versionen in unregelmäßigen
  Abständen. Der Component-Weg erlaubt „Widevine aktualisieren“ ohne neues Paket.
  Empfehlung: Alter der Version anzeigen und ab ~60 Tagen zur Aktualisierung raten.
- **Engine-Aktualität:** Anbieter verlangen aktuelle Chromium-Hauptversionen.
  Engine 0.1.0 (Chromium 156) regelmäßig nachziehen; CDM-Interface-Version
  (`x-cdm-interface-versions`) muss zur Engine passen – Chromium prüft das selbst.
- **Profil/Lizenzen:** Widevine-Herkunftsdaten (CdmStorage), IndexedDB und
  Local Storage landen bereits im verschlüsselten Sitzungsarchiv; nur
  `WidevineCdm` (Binärmodul) ist ausgenommen – richtig so. Hält das Archiv bei
  Stromabbruch nicht, erscheint die Headunit dem Anbieter als neues Gerät
  (Gerätelimits!). Periodische Checkpoints (offener Punkt aus ARCHITECTURE.md)
  haben deshalb für Streaming hohe Priorität.
- **Speicher:** Die Bereitstellung startet kurzzeitig eine zweite Engine-Instanz
  (einige Minuten). Möglichst bei geschlossenem Browser auslösen.
- **Fahrsicherheit:** `src/park_gate.js` existiert, ist aber nicht aktiv
  eingebunden. Video auf dem Fahrerdisplay während der Fahrt ist unzulässig
  (§ 23 Abs. 1a StVO). Empfehlung: Video-Vollbild und Videoausgabe an
  Parkstellung „P“ binden, Ton darf weiterlaufen.

## 6. Design / Bedienung

- **Streaming-Kacheln** als eigene Startseite (große Logos, 2×3 Raster) statt
  Textknöpfen in den Einstellungen; Dienste mit erkanntem L3 grün markieren.
- **Vollbild-Steuerung:** Drehen = ±10 s spulen, Drücken = Pause, nach links =
  Leiste. Anbieter-Player reagieren auf Pfeiltasten/Leertaste; das ist robuster
  als DOM-Klicks in geschlossenen Shadow-Playern.
- **Anmeldung:** Netflix/Disney+ bieten Geräte-Codes/QR-Login nur für TV-Apps;
  im Browser bleibt E-Mail/Passwort. Passworttresor + Handy-Fernbedienung
  (`remote_control.js`) sind der richtige Weg; einen „Mit Handy eintippen“-Knopf
  direkt auf Login-Seiten anbieten.
- **Statusehrlichkeit beibehalten:** „Widevine L3 erkannt“ ist kein Nachweis der
  Anbieterwiedergabe; die Texte unterscheiden das bereits.

## 7. Offene Punkte, die nur auf der Headunit / mit Internet prüfbar sind

1. **Debian-Chromium 156 mit Widevine-Unterstützung?** Hier nicht prüfbar (Paketquelle
   gesperrt). Linux-Chromium-Builds mit `enable_widevine` registrieren das Modul
   und laden es über den Component-Updater; ob Debians Build das tut, zeigt auf dem
   Gerät *„Widevine laden“* bzw. `node test/drm_engine_probe.js --require-widevine`
   mit der Engine. Falls nicht: Engine aus einem Chromium-Build mit
   `enable_widevine=true` beziehen (z. B. eigener Build oder eine Distribution, die
   es aktiviert) – das ist eine Engine-Paketfrage, kein Browser-Umbau.
2. Google-Update-Server von der MGU erreichbar (Uplink, keine Sperren).
3. Echte Wiedergabe: `test/drm_engine_probe.js --playback` (Shaka/Sintel) und
   danach je Anbieter mit eigenem Konto; Screencast muss das Videobild enthalten
   (unter Linux-L3 gibt es keinen Hardware-Overlay-Schutz, daher erwartet).
4. Anbieter-Kontofehler nach den Bot-Merkmal-Korrekturen erneut prüfen.
5. Bildrate/CPU mit dem MGVF-Videopfad messen (`mgu-render` STATS).
