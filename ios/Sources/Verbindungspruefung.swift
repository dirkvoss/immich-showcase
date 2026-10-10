import SwiftUI
import Network

/// Ein Prüfschritt der Verbindungsprüfung („Verbindung prüfen“): Netz, Server, Anmeldung, Immich – jeweils mit einem verständlichen Hinweis.
struct Pruefschritt: Identifiable, Equatable {
    enum Stand { case laeuft, ok, warnung, fehler }
    let id: String
    var titel: String
    var stand: Stand
    var text: String
    var hinweis: String = ""
}

enum Verbindungspruefung {
    static func netzSchritt(erfuellt: Bool, wlan: Bool, mobil: Bool) -> Pruefschritt {
        if !erfuellt { return Pruefschritt(id: "netz", titel: L("Netzwerk"), stand: .fehler, text: L("Das iPhone hat gerade kein Netz."), hinweis: L("WLAN oder Mobilfunk einschalten (Flugmodus aus?).")) }
        if wlan { return Pruefschritt(id: "netz", titel: L("Netzwerk"), stand: .ok, text: L("Mit einem WLAN verbunden.")) }
        if mobil { return Pruefschritt(id: "netz", titel: L("Netzwerk"), stand: .warnung, text: L("Nur Mobilfunk, kein WLAN."), hinweis: L("Steht der Server im Heimnetz, schalte das Heim-WLAN oder den VPN ein.")) }
        return Pruefschritt(id: "netz", titel: L("Netzwerk"), stand: .ok, text: L("Netzwerk vorhanden."))
    }

    /// Eine Netzwerkstörung in einfache Worte übersetzen: (Text, Hinweis).
    static func deute(_ e: URLError.Code) -> (String, String) {
        switch e {
        case .notConnectedToInternet, .dataNotAllowed: return (L("Das iPhone ist nicht mit dem Netz verbunden."), L("WLAN oder Mobilfunk einschalten."))
        case .cannotFindHost, .dnsLookupFailed: return (L("Der Name dieser Adresse wird nicht gefunden."), L("Adresse prüfen. Unterwegs funktionieren Adressen aus dem Heimnetz nur mit VPN."))
        case .timedOut, .cannotConnectToHost, .networkConnectionLost: return (L("Der Server antwortet nicht."), L("Läuft der Server? Bist du im Heimnetz (oder per VPN)? Ein Neustart des Servers hilft oft."))
        case .secureConnectionFailed, .serverCertificateUntrusted, .serverCertificateHasBadDate, .clientCertificateRejected: return (L("Die sichere Verbindung (HTTPS) schlägt fehl."), L("Stimmt die Adresse (https oder http)? Ist das Zertifikat des Servers gültig?"))
        case .appTransportSecurityRequiresSecureConnection: return (L("Diese Adresse erlaubt iOS nur mit https."), L("Adresse mit https:// eingeben oder eine Adresse aus dem Heimnetz (IP) nutzen."))
        default: return (L("Die Verbindung ist fehlgeschlagen."), L("Server und Netz prüfen. (Code \(e.rawValue))"))
        }
    }

    static func deuteStatus(_ code: Int) -> (String, String) {
        switch code {
        case 401: return (L("Der Server verlangt eine Anmeldung."), L("In der App die PIN oder das Immich-Konto eingeben."))
        case 403: return (L("Der Zugriff ist von hier gesperrt."), L("Der Server ist vermutlich nur im Heimnetz erreichbar. VPN einschalten oder im Heim-WLAN sein."))
        case 404: return (L("Unter dieser Adresse gibt es keinen Showcase-Server."), L("Adresse und Port prüfen."))
        case 502, 503, 504: return (L("Der Server (oder der Proxy davor) meldet einen Fehler (\(code))."), L("Läuft der Showcase-Container? Docker-Protokoll ansehen."))
        default: return (L("Der Server antwortet mit Fehler \(code)."), L("Docker-Protokoll des Servers ansehen."))
        }
    }

    private static func holeNetz() async -> (erfuellt: Bool, wlan: Bool, mobil: Bool) {
        await withCheckedContinuation { c in
            let m = NWPathMonitor(); let q = DispatchQueue(label: "showcase.pfad"); var fertig = false
            m.pathUpdateHandler = { p in
                guard !fertig else { return }; fertig = true; m.cancel()
                c.resume(returning: (p.status == .satisfied, p.usesInterfaceType(.wifi) || p.usesInterfaceType(.wiredEthernet), p.usesInterfaceType(.cellular)))
            }
            m.start(queue: q)
        }
    }

    private static func anfrage(_ basis: URL, _ pfad: String, cookie: String?) async -> (Int, [String: Any], Double, URLError.Code?) {
        var r = URLRequest(url: basis.appendingPathComponent("api/" + pfad)); r.timeoutInterval = 8
        r.setValue("1", forHTTPHeaderField: "X-Rahmen")
        if let cookie, !cookie.isEmpty { r.setValue(cookie, forHTTPHeaderField: "Cookie") }
        let k = URLSessionConfiguration.ephemeral; k.urlCache = nil; k.httpCookieStorage = nil
        let t0 = Date()
        do {
            let (d, a) = try await URLSession(configuration: k).data(for: r)
            return ((a as? HTTPURLResponse)?.statusCode ?? 0, ((try? JSONSerialization.jsonObject(with: d)) as? [String: Any]) ?? [:], Date().timeIntervalSince(t0) * 1000, nil)
        } catch { return (0, [:], Date().timeIntervalSince(t0) * 1000, (error as? URLError)?.code ?? .unknown) }
    }

    /// Prüft der Reihe nach und meldet nach jedem Schritt den Zwischenstand.
    @MainActor static func ausfuehren(server: URL, fortschritt: @escaping ([Pruefschritt]) -> Void) async {
        var s: [Pruefschritt] = [
            Pruefschritt(id: "netz", titel: L("Netzwerk"), stand: .laeuft, text: "…"), Pruefschritt(id: "server", titel: L("Server"), stand: .laeuft, text: "…"),
            Pruefschritt(id: "anmeldung", titel: L("Anmeldung"), stand: .laeuft, text: "…"), Pruefschritt(id: "immich", titel: L("Immich"), stand: .laeuft, text: "…")]
        func setze(_ n: Pruefschritt) { if let i = s.firstIndex(where: { $0.id == n.id }) { s[i] = n }; fortschritt(s) }
        fortschritt(s)
        let n = await holeNetz()
        setze(netzSchritt(erfuellt: n.erfuellt, wlan: n.wlan, mobil: n.mobil))
        let cookie = (try? await ServerKlient.erstellen())?.cookieKopf
        let (status, cfg, ms, fehler) = await anfrage(server, "config", cookie: cookie)
        if let fehler { let (t, h) = deute(fehler); setze(Pruefschritt(id: "server", titel: L("Server"), stand: .fehler, text: t, hinweis: h))
            for id in ["anmeldung", "immich"] { setze(Pruefschritt(id: id, titel: id == "immich" ? L("Immich") : L("Anmeldung"), stand: .warnung, text: L("Übersprungen, weil der Server nicht erreichbar ist."))) }
            return }
        guard status == 200, cfg["modus"] != nil else { let (t, h) = deuteStatus(status); setze(Pruefschritt(id: "server", titel: L("Server"), stand: .fehler, text: t, hinweis: h))
            for id in ["anmeldung", "immich"] { setze(Pruefschritt(id: id, titel: id == "immich" ? L("Immich") : L("Anmeldung"), stand: .warnung, text: L("Übersprungen."))) }
            return }
        setze(Pruefschritt(id: "server", titel: L("Server"), stand: .ok, text: L("\(cfg["name"] as? String ?? "Frameside") antwortet (\(Int(ms)) ms), Version \(cfg["version"] as? String ?? "?").")))
        let me = await anfrage(server, "me", cookie: cookie)
        guard (me.1["angemeldet"] as? Bool) == true else {
            setze(Pruefschritt(id: "anmeldung", titel: L("Anmeldung"), stand: .warnung, text: L("Noch nicht angemeldet."), hinweis: L("In der App die PIN oder das Immich-Konto eingeben.")))
            setze(Pruefschritt(id: "immich", titel: L("Immich"), stand: .warnung, text: L("Wird nach der Anmeldung geprüft.")))
            return }
        setze(Pruefschritt(id: "anmeldung", titel: L("Anmeldung"), stand: .ok, text: L("Angemeldet.")))
        let g = await anfrage(server, "gesundheit", cookie: cookie)
        let liste = (g.1["pruefungen"] as? [[String: Any]]) ?? []
        let probleme = liste.filter { ($0["status"] as? String) == "fehler" || ($0["status"] as? String) == "warnung" }
        if g.0 != 200 { setze(Pruefschritt(id: "immich", titel: L("Immich"), stand: .warnung, text: L("Der Status ist nicht abrufbar."))) }
        else if probleme.isEmpty { setze(Pruefschritt(id: "immich", titel: L("Immich"), stand: .ok, text: L("Alles in Ordnung."))) }
        else { setze(Pruefschritt(id: "immich", titel: L("Immich"), stand: (g.1["gesamt"] as? String) == "fehler" ? .fehler : .warnung,
                                   text: probleme.compactMap { "\($0["titel"] as? String ?? ""): \($0["text"] as? String ?? "")" }.joined(separator: "\n"),
                                   hinweis: probleme.compactMap { $0["hinweis"] as? String }.first(where: { !$0.isEmpty }) ?? "")) }
    }
}

struct VerbindungspruefungAnsicht: View {
    let server: URL
    @Environment(\.dismiss) private var schliessen
    @State private var schritte: [Pruefschritt] = []
    @State private var laeuft = false

    var body: some View {
        NavigationStack {
            List {
                Section { Text(server.absoluteString).font(.footnote).foregroundStyle(.secondary) }
                ForEach(schritte) { s in
                    HStack(alignment: .top, spacing: 12) {
                        symbol(s.stand).frame(width: 24)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(s.titel).fontWeight(.semibold)
                            Text(s.text).font(.subheadline)
                            if !s.hinweis.isEmpty { Text(s.hinweis).font(.footnote).foregroundStyle(.secondary) }
                        }
                    }.padding(.vertical, 2)
                }
                Section { Button("Erneut prüfen") { starten() }.disabled(laeuft) }
            }
            .navigationTitle("Verbindung prüfen")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Fertig") { schliessen() } } }
            .task { starten() }
        }
    }

    @ViewBuilder private func symbol(_ s: Pruefschritt.Stand) -> some View {
        switch s {
        case .laeuft: ProgressView()
        case .ok: Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
        case .warnung: Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
        case .fehler: Image(systemName: "xmark.octagon.fill").foregroundStyle(.red)
        }
    }

    private func starten() {
        laeuft = true
        Task { await Verbindungspruefung.ausfuehren(server: server) { schritte = $0 }; laeuft = false }
    }
}
