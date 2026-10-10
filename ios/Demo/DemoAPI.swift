import Foundation

/// Die Server-Schnittstelle im Demo-Modus: beantwortet genau die Aufrufe, die die Oberfläche macht, mit erfundenen Daten.
/// Es wird nichts gesendet und nichts gespeichert (nur im Arbeitsspeicher, solange die App läuft).
final class DemoAPI {
    struct Antwort { var status = 200; var daten = Data(); var mime = "application/json" }
    struct Show { var id: String; var name: String; var ids: [String]; var zeit: String; var gemerkt: Bool }

    private let lock = NSLock()
    private var shows: [Show] = []
    private var laeuft: Show?
    private var seit = ""
    private var zurueckName: String?
    private let version: String
    static let rahmenName = "Bilderrahmen (Demo)"

    init(version: String = "demo") { self.version = version }

    // MARK: Einstieg

    func antwort(methode: String, pfad: String, abfrage: [String: String], koerper: [String: Any]) -> Antwort {
        lock.lock(); defer { lock.unlock() }
        let teile = pfad.split(separator: "/").map(String.init)           // ["api", "shows", "abc", "anzeigen"]
        guard teile.first == "api", teile.count >= 2 else { return fehler(404, "Unbekannt") }
        switch (methode, teile[1]) {
        case ("GET", "config"): return json(konfig())
        case ("GET", "me"): return json(["angemeldet": true, "lan": true, "auth": "pin"])
        case ("GET", "version"): return json(["v": version])
        case ("GET", "filter"), ("GET", "facetten"): return json(facetten(abfrage))
        case ("GET", "neueste"): return json(neueste(abfrage))
        case ("GET", "suche"): return json(suche(abfrage["text"] ?? ""))
        case ("GET", "vorschau"):
            guard teile.count == 3, let f = DemoDaten.foto(id: teile[2]) else { return fehler(404, "Foto nicht verfügbar") }
            let gross = abfrage["s"] == "gross"
            return Antwort(daten: DemoBild.jpeg(f, breite: gross ? 1280 : 360), mime: "image/jpeg")
        case ("GET", "gesundheit"): return json(gesundheit())
        case ("GET", "status"): return json(status())
        case ("GET", "geraete"): return json(["geraete": [geraet()]])
        case ("POST", "anzeigen"): return anzeigen(koerper)
        case ("POST", "normal"): return normal()
        case ("POST", "zurueck"): return zurueck()
        case ("POST", "reihenfolge"): return json(["ok": true, "nachricht": "Reihenfolge geändert (Demo)."])
        case (_, "shows"): return showsRoute(methode, teile, koerper)
        default: return fehler(404, "In der Demo nicht verfügbar.")
        }
    }

    // MARK: Antworten

    private func json(_ d: [String: Any]) -> Antwort { Antwort(daten: (try? JSONSerialization.data(withJSONObject: d)) ?? Data()) }
    private func fehler(_ code: Int, _ text: String) -> Antwort { var a = json(["nachricht": text]); a.status = code; return a }

    func konfig() -> [String: Any] {
        ["name": "Frameside (Demo)", "version": version, "modus": "rahmen", "auth": "pin", "musik_upload": false, "hochladen": false, "hochladen_mb": 40,
         "konfiguriert": true, "tv_url": "", "beispiele": ["Sommer 2022 am Strand", "Anna Beispiel in Sardinien", "Alpen 2023"],
         "beispiele_en": ["Summer 2022 at the beach", "Anna in Sardinia", "Alps 2023"], "ziele": [String: String](),
         "rahmen": ["rahmen"], "rahmen_namen": ["rahmen": Self.rahmenName], "rahmen_sek": 8, "rahmen_fuellung": "unscharf", "tv_fuellung": "balken",
         "rahmen_anzeige": ["datum", "ort"], "rahmen_nacht": "", "rahmen_zusatz": [String](), "koppeln": false,
         "alle_ziele": ["rahmen": Self.rahmenName], "demo": true]
    }

    private func gefiltert(_ q: [String: String]) -> [DemoFoto] {
        var l = DemoDaten.alle
        if let j = Int(q["jahr"] ?? ""), j > 0 { l = l.filter { $0.jahr == j } }
        if let o = q["ort"], !o.isEmpty { l = l.filter { $0.ort.land == o || $0.ort.landDE.lowercased() == o.lowercased() } }
        if let p = q["person"], !p.isEmpty { l = l.filter { $0.personen.contains { $0.lowercased() == p.lowercased() } } }
        if q["favoriten"] == "1" { l = l.filter { $0.favorit } }
        return l
    }

    private func facetten(_ q: [String: String]) -> [String: Any] {
        let l = gefiltert(q)
        let jahre = Dictionary(grouping: gefiltert(q.merging(["jahr": ""]) { $1 }), by: \.jahr).map { ["wert": $0.key, "anzahl": $0.value.count] }.sorted { ($0["wert"] as! Int) > ($1["wert"] as! Int) }
        let laender = DemoOrt.allCases.map { o in ["wert": o.land, "name": o.landDE, "anzahl": gefiltert(q.merging(["ort": ""]) { $1 }).filter { $0.ort == o }.count] as [String: Any] }
            .filter { ($0["anzahl"] as! Int) > 0 }.sorted { ($0["name"] as! String) < ($1["name"] as! String) }
        let personen = DemoDaten.personen.map { p in ["name": p, "anzahl": gefiltert(q.merging(["person": ""]) { $1 }).filter { $0.personen.contains(p) }.count] as [String: Any] }
            .filter { ($0["anzahl"] as! Int) > 0 }
        return ["jahre": jahre, "laender": laender, "personen": personen, "gesamt": l.count]
    }

    private func neueste(_ q: [String: String]) -> [String: Any] { ["fotos": gefiltert(q).map(\.json), "weiter": NSNull()] }

    func suche(_ text: String) -> [String: Any] {
        let t = text.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { return ["ok": false, "nachricht": "Bitte einen Suchtext eingeben.", "fotos": [Any]()] }
        var l = DemoDaten.alle
        var erkannt: [String] = []
        let orte = DemoOrt.allCases.filter { $0.stichworte.contains { t.contains($0) } }
        if !orte.isEmpty { l = l.filter { orte.contains($0.ort) }; erkannt.append("Ort") }
        if let m = t.range(of: #"20(2[1-5])"#, options: .regularExpression), let j = Int(t[m]) { l = l.filter { $0.jahr == j }; erkannt.append("Jahr") }
        let pers = DemoDaten.personen.filter { p in p.lowercased().split(separator: " ").contains { t.contains($0) } || (p == "Opa Karl" && t.contains("opa")) }
        if !pers.isEmpty { l = l.filter { f in pers.allSatisfy { f.personen.contains($0) } }; erkannt.append("Person") }
        let info: [String: Any] = ["personen": pers, "ort": orte.first?.landDE ?? NSNull(), "zeitraeume": 0, "favoriten": false, "motiv": ""]
        if l.isEmpty { return ["ok": true, "nachricht": "Dazu habe ich keine Fotos gefunden (Demo).", "erkannt": info, "gesamt": 0, "fotos": [Any]()] }
        let hinweis = erkannt.isEmpty ? "Demo: Die Suche versteht hier Orte (Sardinien, Alpen, Nordsee, Lissabon), Jahre 2021–2025 und die Namen Anna und Opa Karl." : "\(l.count) Fotos gefunden (Demo)."
        return ["ok": true, "nachricht": hinweis, "erkannt": info, "gesamt": l.count, "fotos": l.map(\.json)]
    }

    private func gesundheit() -> [String: Any] {
        func p(_ id: String, _ titel: String, _ status: String, _ text: String) -> [String: Any] { ["id": id, "titel": titel, "status": status, "text": text, "hinweis": ""] }
        return ["gesamt": "ok", "pruefungen": [
            p("immich", "Immich", "ok", "Demo: Immich ist erreichbar."),
            p("fotos", "Fotos und Schlüssel", "ok", "\(DemoDaten.anzahl) Fotos sichtbar (erfundene Beispielfotos)."),
            p("g-rahmen", Self.rahmenName, "ok", "Online."),
            p("version", "Showcase", "info", "Demo-Modus, \(version).")]]
    }

    private func status() -> [String: Any] {
        ["ok": true, "nachricht": laeuft.map { "Läuft gerade: \"\($0.name)\" (\($0.ids.count) Fotos, seit \(seit))" } ?? "Der Bilderrahmen zeigt das normale Programm.",
         "laeuft": laeuft?.name ?? NSNull(), "anzahl": laeuft?.ids.count ?? NSNull(), "seit": laeuft == nil ? NSNull() : seit as Any, "zurueck": zurueckName ?? NSNull(),
         "titelbild": laeuft?.ids.first ?? NSNull(), "reihenfolge": "alt", "ziel": "rahmen",
         "rahmen": [["id": "rahmen", "name": Self.rahmenName, "laeuft": laeuft?.name ?? NSNull(), "online": true] as [String: Any]]]
    }

    private func geraet() -> [String: Any] {
        ["id": "rahmen", "name": Self.rahmenName, "art": "rahmen", "online": true, "zustand": laeuft == nil ? "dauerprogramm" : "spielt", "zuletzt_vor_s": 1,
         "spielt": laeuft?.name ?? NSNull(), "dauerprogramm": laeuft == nil, "bild_alter_s": 2, "fully": false, "selbst": false, "bildschirm": NSNull(), "akku": NSNull(), "laedt": NSNull()]
    }

    private static func zeitstempel() -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd'T'HH:mm"; return f.string(from: Date())
    }

    private func anzeigen(_ k: [String: Any]) -> Antwort {
        let roh = (k["name"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard (1...60).contains(roh.count) else { return fehler(400, "Bitte einen Namen (1-60 Zeichen) eingeben") }
        let ids = (k["ids"] as? [String] ?? []).filter { DemoDaten.foto(id: $0) != nil }
        guard !ids.isEmpty else { return fehler(400, "Bitte 1 bis 1000 Fotos auswählen") }
        if k["dry"] as? Bool == true { return json(["ok": true, "nachricht": "(Test) \(ids.count) Fotos als \"\(roh)\" würden auf den Rahmen gehen.", "anzahl": ids.count, "ziele": ["rahmen"]]) }
        let vorher = laeuft?.name
        var show = Show(id: String(UUID().uuidString.prefix(12)).lowercased(), name: roh, ids: ids, zeit: Self.zeitstempel(), gemerkt: k["speichern"] as? Bool ?? false)
        shows.removeAll { $0.name.lowercased() == roh.lowercased() }
        shows.insert(show, at: 0); show = shows[0]
        if vorher != show.name { zurueckName = vorher ?? "Normales Programm" }
        laeuft = show; seit = Self.zeitstempel()
        return json(["ok": true, "anzahl": ids.count, "show": show.id, "zurueck": zurueckName ?? NSNull(), "ziele": ["rahmen"],
                     "nachricht": "\"\(roh)\" mit \(ids.count) Fotos läuft gleich auf dem Bilderrahmen. (Demo: Es wird nichts an einen echten Rahmen gesendet.)"])
    }

    private func normal() -> Antwort {
        if let l = laeuft { zurueckName = l.name }
        laeuft = nil
        return json(["ok": true, "nachricht": "Der Bilderrahmen zeigt wieder das normale Programm.", "zurueck": zurueckName ?? NSNull()])
    }

    private func zurueck() -> Antwort {
        guard let ziel = zurueckName else { return fehler(404, "Es gibt noch nichts, wohin ich zurückgehen könnte.") }
        let aktuell = laeuft?.name
        if let s = shows.first(where: { $0.name == ziel }) { laeuft = s; seit = Self.zeitstempel() } else { laeuft = nil }
        zurueckName = aktuell
        return json(["ok": true, "nachricht": laeuft.map { "Zurück bei \"\($0.name)\" – läuft gleich auf dem Rahmen." } ?? "Der Bilderrahmen zeigt wieder das normale Programm.", "zurueck": zurueckName ?? NSNull()])
    }

    private func showsRoute(_ methode: String, _ teile: [String], _ k: [String: Any]) -> Antwort {
        let je = laeuft?.name.lowercased()
        if teile.count == 2 && methode == "GET" {
            return json(["zurueck": zurueckName ?? NSNull(), "shows": shows.map { ["id": $0.id, "name": $0.name, "anzahl": $0.ids.count, "zeit": $0.zeit, "gemerkt": $0.gemerkt,
                         "laeuft": $0.name.lowercased() == je, "laeuft_auf": $0.name.lowercased() == je ? ["rahmen"] : [String]()] as [String: Any] }])
        }
        guard teile.count >= 3, let i = shows.firstIndex(where: { $0.id == teile[2] }) else { return fehler(404, "Show nicht gefunden") }
        switch (methode, teile.count) {
        case ("GET", 3): let s = shows[i]; return json(["id": s.id, "name": s.name, "zeit": s.zeit, "gemerkt": s.gemerkt, "fotos": s.ids.map { ["id": $0] }])
        case ("DELETE", 3): shows.remove(at: i); return json(["ok": true])
        case ("PUT", 3):
            if let n = k["name"] as? String, !n.isEmpty { shows[i].name = String(n.prefix(60)) }
            if let ids = k["ids"] as? [String] { shows[i].ids = ids.filter { DemoDaten.foto(id: $0) != nil } }
            if let g = k["gemerkt"] as? Bool { shows[i].gemerkt = g }
            return json(["ok": true, "show": shows[i].id])
        case ("POST", 4):
            return anzeigen(["name": shows[i].name, "ids": shows[i].ids, "speichern": shows[i].gemerkt])
        default: return fehler(404, "In der Demo nicht verfügbar.")
        }
    }
}
