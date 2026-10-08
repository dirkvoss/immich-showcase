# Showcase Immich – iPhone-App

Eine dünne native Hülle (SwiftUI + `WKWebView`) um die Web-App von Immich Showcase. Die Oberfläche bleibt die Web-App, die App ergänzt, was eine Web-App auf dem iPhone nicht kann: Einrichtung per QR-Code, Face-ID-Sperre, saubere Fehlerseite, später Kurzbefehle, Widgets und Teilen aus der Fotos-App.

> Unabhängiges Projekt, nicht mit dem Immich-Projekt verbunden.

## Bauen und ausprobieren (Mac mit Xcode, [XcodeGen](https://github.com/yonaskolb/XcodeGen))
```bash
cd ios
./scripts/test.sh        # Unit-Tests im Simulator
./scripts/run-sim.sh     # baut und startet die App im iPhone-Simulator
```
Das Xcode-Projekt wird aus `project.yml` erzeugt und nicht eingecheckt.

## Verbinden
- Adresse des Servers eintippen (zum Beispiel `192.168.1.20:8090`), oder
- in der Web-App unter *Konto → Einstellungen → iPhone-App verbinden* den QR-Code zeigen und in der App scannen.

Die App erkennt sich in der Web-App am Zusatz `ShowcaseApp/<Version>` im User-Agent; dort erscheint dann *Konto → App-Einstellungen* (Server ändern, Face ID).

## TestFlight / App Store (einmalig einrichten)
1. **App-Eintrag** in App Store Connect anlegen (lässt sich nicht automatisieren): *Apps → ＋ → Neue App* – Plattform iOS, Name „Showcase Immich“ (falls vergeben: Alternative), Primärsprache Deutsch, **Bundle-ID `com.dirk-voss.showcase`** aus der Liste wählen, SKU `showcase-immich-1`.
2. API-Zugang: `scripts/release.env` mit `KEY_ID`, `ISSUER_ID`, `TEAM_ID` (Vorlage: dein App-Store-Connect-API-Schlüssel, `~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8`).
3. Verteilungsprofil anlegen und installieren: `node scripts/asc.js profil`
4. Bauen und hochladen: `./scripts/release-ios.sh` (`--nur-bauen` zum Testen ohne Upload)
5. Stand prüfen: `node scripts/asc.js app`; in TestFlight Tester einladen.

## Technik
- iOS 17+, Manual Signing mit Apple-Distribution-Zertifikat, Build-Nummer = Zeitstempel.
- Lokale HTTP-Server im Heimnetz sind über `NSAllowsLocalNetworking` erlaubt; fremde Links öffnen im Browser.
