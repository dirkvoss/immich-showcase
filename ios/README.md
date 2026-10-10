# Frameside – iPhone-App

Eine dünne native Hülle (SwiftUI + `WKWebView`) um die Web-App von Frameside. Die Oberfläche bleibt die Web-App, die App ergänzt, was eine Web-App auf dem iPhone nicht kann: Einrichtung per QR-Code, Face-ID-Sperre, saubere Fehlerseite, Kurzbefehle/Siri, ein Widget und Teilen aus der Fotos-App.

> Unabhängiges Projekt, nicht mit dem Immich-Projekt verbunden.

## Bauen und ausprobieren (Mac mit Xcode, [XcodeGen](https://github.com/yonaskolb/XcodeGen))
```bash
cd ios
./scripts/test.sh        # Unit-Tests im Simulator
./scripts/run-sim.sh     # baut und startet die App im iPhone-Simulator
```
Das Xcode-Projekt wird aus `project.yml` erzeugt und nicht eingecheckt.

## Verbinden
- **Im WLAN suchen:** Beim ersten Start sucht die App im eigenen Netz (/24, Ports 8090 und 80) nach Showcase-Servern und zeigt Treffer zum Antippen an. Dafür fragt iOS einmal nach dem Zugriff auf das lokale Netzwerk. Zusätzlich probiert die Suche bekannte Namen (`showcase`, `immich-showcase`, `bilderrahmen`, auch mit `.local`), das klappt über Netzgrenzen hinweg, wenn dein DNS den Namen kennt. Meldet sich der Server zusätzlich per **Bonjour** (`./install.sh --bonjour`, siehe Haupt-README), findet die App ihn auch in anderen Netzen, wenn der Router mDNS weiterleitet. Für ein anderes Netz oder VLAN gibt es unter „Server in einem anderen Netz suchen“ ein Eingabefeld (z. B. `192.168.2`); die Suche beschränkt sich auf private Adressbereiche.
- **Demo ohne Server:** „Demo ausprobieren“ zeigt die echte Oberfläche mit erfundenen Beispielfotos (gemalt, keine echten Fotos). Es wird nichts gesendet. Technisch liefert die App die Oberfläche (Kopie von `static/` im Paket) und eine Mini-Schnittstelle unter `showcase-demo://demo/` selbst aus (`ios/Demo/`).
- Adresse des Servers eintippen (zum Beispiel `192.168.1.20:8090`), oder
- in der Web-App unter *Konto → Einstellungen → iPhone-App verbinden* den QR-Code zeigen und in der App scannen.

Die App erkennt sich in der Web-App am Zusatz `ShowcaseApp/<Version>` im User-Agent; dort erscheint dann *Konto → App-Einstellungen* (Server ändern, Face ID).

## Siri, Widget und Teilen
Alles läuft über den Showcase-Server; die App legt Server-Adresse und Anmeldung (PIN-Cookie) im gemeinsamen Schlüsselbund ab (Gruppe `<TeamID>.com.dirk-voss.showcase.geteilt`, ohne Portal-Einrichtung). **Die App muss dafür einmal geöffnet worden sein.**
- **Kurzbefehle/Siri:** *Fotos auf den Rahmen zeigen* (Suchtext wie in der Web-App, z. B. „Sommer 2022 am Strand“), *Show beenden*, *Zur vorherigen Show zurück*. Sätze: „Zeige Fotos auf dem Rahmen mit Frameside“, „Beende die Show mit Frameside“.
- **Teilen:** In der Fotos-App Fotos wählen → Teilen → „Frameside“. Die Fotos werden als JPEG hochgeladen (Server → Immich, Album „Showcase-Uploads“) und laufen auf dem Rahmen (bei mehreren Rahmen mit Auswahl). Benötigt auf dem Server `RAHMEN_IMMICH_UPLOAD_KEY`.
- **Widget „Bilderrahmen“:** zeigt, was auf dem Rahmen läuft, mit Knöpfen *Beenden* und *Zurück*.

## TestFlight / App Store (einmalig einrichten)
1. **App-Eintrag** in App Store Connect anlegen (lässt sich nicht automatisieren): *Apps → ＋ → Neue App* – Plattform iOS, Name „Frameside“ (falls vergeben: Alternative), Primärsprache Deutsch, **Bundle-ID `com.dirk-voss.showcase`** aus der Liste wählen, SKU `showcase-immich-1`.
2. API-Zugang: `scripts/release.env` mit `KEY_ID`, `ISSUER_ID`, `TEAM_ID` (Vorlage: dein App-Store-Connect-API-Schlüssel, `~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8`).
3. App-IDs (App, Teilen, Widget) und Verteilungsprofile anlegen und installieren: `node scripts/asc.js profil`
4. Bauen und hochladen: `./scripts/release-ios.sh` (`--nur-bauen` zum Testen ohne Upload)
5. Stand prüfen: `node scripts/asc.js app`; in TestFlight Tester einladen.

## Technik
- iOS 17+, Manual Signing mit Apple-Distribution-Zertifikat, Build-Nummer = Zeitstempel.
- Lokale HTTP-Server im Heimnetz sind über `NSAllowsLocalNetworking` erlaubt; fremde Links öffnen im Browser.
