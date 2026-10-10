import Foundation

/// Spricht den Showcase-Server direkt an (ohne die Web-Ansicht) – für Siri und Kurzbefehle.
/// Die Anmeldung (Cookie) kommt aus dem Speicher der Web-Ansicht; im vertrauten Netz braucht es keine.
struct ServerKlient {
    let basis: URL
    var cookieKopf: String?

    struct Rahmen: Equatable { let id: String; let name: String }

    enum KlientFehler: LocalizedError, Equatable {
        case keinServer, nichtErreichbar, anmeldungNoetig, server(String)
        var errorDescription: String? {
            switch self {
            case .keinServer: return L("Die App ist noch mit keinem Server verbunden. Öffne Frameside einmal und gib die Adresse ein.")
            case .nichtErreichbar: return L("Der Server ist nicht erreichbar. Bist du im richtigen Netz?")
            case .anmeldungNoetig: return L("Bitte öffne Frameside einmal und melde dich mit der PIN an.")
            case .server(let t): return t
            }
        }
    }

    static func gespeicherterServer() -> URL? { Adresse.normalisieren(UserDefaults.standard.string(forKey: "serverAdresse") ?? "") }

    /// Aus dem gemeinsamen Speicher (Teilen-Erweiterung, Widget): Server-Adresse und Anmelde-Cookie, die die App dort ablegt.
    static func ausSpeicher() throws -> ServerKlient {
        guard let basis = GeteilterSpeicher.lesen("server").flatMap(Adresse.normalisieren) ?? gespeicherterServer() else { throw KlientFehler.keinServer }
        return ServerKlient(basis: basis, cookieKopf: GeteilterSpeicher.lesen("cookie"))
    }

    /// Cookie-Kopf („name=wert; …“) aus den Cookies, die zum Server gehören.
    static func cookieKopf(aus alle: [HTTPCookie], fuer url: URL) -> String? {
        guard let host = url.host?.lowercased() else { return nil }
        let passend = alle.filter {
            let d = $0.domain.lowercased().drop { $0 == "." }
            return host == d || host.hasSuffix("." + d)
        }
        return HTTPCookie.requestHeaderFields(with: passend)["Cookie"]
    }

    /// Baut eine Anfrage an die API. Schreibende Aufrufe brauchen den Header X-Rahmen (Schutz des Servers vor fremden Formularen).
    func anfrage(_ methode: String, _ pfad: String, abfrage: [URLQueryItem] = [], koerper: [String: Any]? = nil) -> URLRequest {
        var teile = URLComponents(url: basis.appendingPathComponent("api/" + pfad), resolvingAgainstBaseURL: false)!
        if !abfrage.isEmpty { teile.queryItems = abfrage }
        var r = URLRequest(url: teile.url!)
        r.httpMethod = methode
        r.timeoutInterval = 30
        r.setValue("1", forHTTPHeaderField: "X-Rahmen")
        r.setValue("ShowcaseApp-Kurzbefehl", forHTTPHeaderField: "User-Agent")
        if let cookieKopf, !cookieKopf.isEmpty { r.setValue(cookieKopf, forHTTPHeaderField: "Cookie") }
        if let koerper {
            r.httpBody = try? JSONSerialization.data(withJSONObject: koerper)
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return r
    }

    func aufruf(_ r: URLRequest, sitzung: URLSession = .shared) async throws -> [String: Any] {
        let daten: Data, antwort: URLResponse
        do { (daten, antwort) = try await sitzung.data(for: r) } catch { throw KlientFehler.nichtErreichbar }
        let status = (antwort as? HTTPURLResponse)?.statusCode ?? 0
        let json = (try? JSONSerialization.jsonObject(with: daten)) as? [String: Any] ?? [:]
        if status == 401 { throw KlientFehler.anmeldungNoetig }
        if !(200..<300).contains(status) { throw KlientFehler.server((json["nachricht"] as? String) ?? L("Der Server meldet einen Fehler (\(status)).")) }
        return json
    }

    // MARK: Aktionen

    struct Stand: Equatable {
        let rahmenName: String
        let laeuft: String?        // Name der laufenden Show, nil = normales Programm
        let anzahl: Int?
        let zurueck: String?       // Name der vorherigen Show
        let online: Bool?
    }

    /// Was läuft auf dem Rahmen? (für das Widget)
    func stand(rahmen: String? = nil) async throws -> Stand {
        let r = try await aufruf(anfrage("GET", "status", abfrage: rahmen.map { [URLQueryItem(name: "ziel", value: $0)] } ?? []))
        let liste = (r["rahmen"] as? [[String: Any]]) ?? []
        let id = (r["ziel"] as? String) ?? rahmen
        let eintrag = liste.first { ($0["id"] as? String) == id } ?? liste.first
        return Stand(rahmenName: (eintrag?["name"] as? String) ?? L("Bilderrahmen"), laeuft: r["laeuft"] as? String,
                     anzahl: r["anzahl"] as? Int, zurueck: r["zurueck"] as? String, online: eintrag?["online"] as? Bool)
    }

    func rahmen() async throws -> [Rahmen] {
        let c = try await aufruf(anfrage("GET", "config"))
        let ids = (c["rahmen"] as? [String]) ?? []
        let namen = (c["rahmen_namen"] as? [String: String]) ?? [:]
        return ids.map { Rahmen(id: $0, name: namen[$0] ?? $0) }
    }

    private func ziel(_ rahmen: String?) -> [String: Any] { rahmen.map { ["ziel": $0] } ?? [:] }

    func normal(rahmen: String?) async throws -> String {
        (try await aufruf(anfrage("POST", "normal", koerper: ziel(rahmen))))["nachricht"] as? String ?? L("Der Rahmen zeigt wieder das normale Programm.")
    }

    func zurueck(rahmen: String?) async throws -> String {
        (try await aufruf(anfrage("POST", "zurueck", koerper: ziel(rahmen))))["nachricht"] as? String ?? L("Zurück zur vorherigen Show.")
    }

    /// Schickt Fotos (IDs aus Immich) als Show auf den Rahmen.
    func anzeigen(name: String, ids: [String], rahmen: String?) async throws -> String {
        var k = ziel(rahmen)
        let n = String(name.prefix(60))
        k["name"] = n.prefix(1).uppercased() + n.dropFirst()
        k["ids"] = ids
        k["speichern"] = false
        let a = try await aufruf(anfrage("POST", "anzeigen", koerper: k))
        return (a["nachricht"] as? String) ?? L("Die Show läuft gleich auf dem Rahmen.")
    }

    /// Sucht Fotos (wie die Suche in der Web-App: „Sommer 2022 am Strand“) und schickt sie als Show auf den Rahmen.
    func fotosZeigen(suche: String, rahmen: String?) async throws -> String {
        let text = suche.trimmingCharacters(in: .whitespacesAndNewlines)
        let s = try await aufruf(anfrage("GET", "suche", abfrage: [URLQueryItem(name: "text", value: text), URLQueryItem(name: "lang", value: "de")]))
        let fotos = (s["fotos"] as? [[String: Any]]) ?? []
        let ids = fotos.filter { $0["v"] == nil }.compactMap { $0["id"] as? String }
        guard !ids.isEmpty else { throw KlientFehler.server((s["nachricht"] as? String) ?? L("Dazu habe ich keine Fotos gefunden.")) }
        return try await anzeigen(name: text, ids: ids, rahmen: rahmen)
    }

    /// Lädt ein Foto (JPEG/PNG/…) zum Server hoch; der legt es in Immich ab. Ergebnis: die Immich-ID.
    func hochladen(_ foto: Data, name: String) async throws -> String {
        var r = anfrage("PUT", "hochladen")
        r.timeoutInterval = 180
        r.setValue("application/octet-stream", forHTTPHeaderField: "Content-Type")
        r.setValue(name.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? "Foto", forHTTPHeaderField: "X-Dateiname")
        r.setValue(String(Int(Date().timeIntervalSince1970 * 1000)), forHTTPHeaderField: "X-Datum")
        let antwortDaten: Data, antwort: URLResponse
        do { (antwortDaten, antwort) = try await URLSession.shared.upload(for: r, from: foto) } catch { throw KlientFehler.nichtErreichbar }
        let status = (antwort as? HTTPURLResponse)?.statusCode ?? 0
        let json = (try? JSONSerialization.jsonObject(with: antwortDaten)) as? [String: Any] ?? [:]
        if status == 401 { throw KlientFehler.anmeldungNoetig }
        guard (200..<300).contains(status), let id = json["id"] as? String else { throw KlientFehler.server((json["nachricht"] as? String) ?? L("Der Server hat das Foto nicht angenommen (\(status)).")) }
        return id
    }
}
