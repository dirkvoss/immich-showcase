import Foundation
import Darwin

struct GefundenerServer: Identifiable, Hashable {
    let url: URL
    let name: String
    var anmeldung: String? = nil          // was die Seite verlangt (aus /api/config "auth")
    var id: URL { url }
    var anmeldungText: String? {
        switch anmeldung {
        case "pin": return L("Anmeldung mit PIN (im Heimnetz oft ohne)")
        case "immich": return L("Anmeldung mit Immich-Konto")
        case "beide": return L("Anmeldung mit PIN oder Immich-Konto")
        default: return nil
        }
    }
    var anzeigeAdresse: String { (url.host ?? "") + (url.port.map { ":\($0)" } ?? "") }
}

/// Sucht Immich-Showcase-Server im eigenen WLAN (Netz /24 des iPhones, Ports 8090 und 80). Der Server braucht dafür nichts zu tun.
enum ServerSuche {
    static let ports = [8090, 80]
    /// Namen, unter denen ein Server oft erreichbar ist (DNS/mDNS) – klappt auch über Netzgrenzen hinweg, wenn der Name bekannt ist.
    static let bekannteNamen = ["showcase", "immich-showcase", "bilderrahmen", "showcase.local", "immich-showcase.local", "bilderrahmen.local"]

    /// „192.168.2“, „192.168.2.“ oder „192.168.2.17“ -> „192.168.2.“; nil bei Ungültigem. Nur private Netze (kein Scan fremder Adressen).
    static func praefix(aus eingabe: String) -> String? {
        let t = eingabe.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: ".").map(String.init)
        guard t.count >= 3, t.count <= 4, t.prefix(3).allSatisfy({ Int($0).map { (0...255).contains($0) } ?? false }) else { return nil }
        return praefixe(adressen: [t.prefix(3).joined(separator: ".") + ".1"]).first
    }

    static func namenKandidaten(_ namen: [String] = bekannteNamen) -> [URL] {
        namen.flatMap { n in ports.compactMap { URL(string: "http://\(n)\($0 == 80 ? "" : ":\($0)")") } }
    }

    /// Aus den IPv4-Adressen des Geräts die privaten /24-Netze („192.168.1.“) – ohne Doppelte.
    static func praefixe(adressen: [String]) -> [String] {
        var ergebnis: [String] = []
        for a in adressen {
            let t = a.split(separator: ".").compactMap { Int($0) }
            guard t.count == 4, t.allSatisfy({ (0...255).contains($0) }) else { continue }
            let privat = t[0] == 10 || (t[0] == 192 && t[1] == 168) || (t[0] == 172 && (16...31).contains(t[1]))
            guard privat else { continue }
            let p = "\(t[0]).\(t[1]).\(t[2])."
            if !ergebnis.contains(p) { ergebnis.append(p) }
        }
        return ergebnis
    }

    static func eigeneAdressen() -> [String] {
        var liste: [String] = []
        var anfang: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&anfang) == 0, let erster = anfang else { return [] }
        defer { freeifaddrs(anfang) }
        for zeiger in sequence(first: erster, next: { $0.pointee.ifa_next }) {
            let i = zeiger.pointee
            guard let adr = i.ifa_addr, adr.pointee.sa_family == UInt8(AF_INET) else { continue }
            let name = String(cString: i.ifa_name)
            guard name.hasPrefix("en") || name.hasPrefix("bridge") else { continue }       // WLAN/LAN, nicht Mobilfunk oder VPN
            var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            if getnameinfo(adr, socklen_t(adr.pointee.sa_len), &host, socklen_t(host.count), nil, 0, NI_NUMERICHOST) == 0 { liste.append(String(cString: host)) }
        }
        return liste
    }

    /// Ist die Antwort von /api/config die eines Showcase-Servers? Dann sein Name.
    static func showcaseName(_ daten: Data) -> String? { showcaseInfo(daten)?.name }

    static func showcaseInfo(_ daten: Data) -> (name: String, auth: String?)? {
        guard let j = (try? JSONSerialization.jsonObject(with: daten)) as? [String: Any], j["modus"] != nil, j["version"] != nil,
              let n = j["name"] as? String, !n.isEmpty else { return nil }
        return (n, j["auth"] as? String)
    }

    static func kandidaten(praefixe: [String]) -> [URL] {
        praefixe.flatMap { p in (1...254).flatMap { h in ports.compactMap { URL(string: "http://\(p)\(h)\($0 == 80 ? "" : ":\($0)")") } } }
    }

    /// Prueft eine einzelne Adresse (z. B. aus Bonjour): antwortet dort wirklich ein Showcase-Server?
    static func bestaetige(_ url: URL) async -> GefundenerServer? {
        let k = URLSessionConfiguration.ephemeral; k.timeoutIntervalForRequest = 3; k.urlCache = nil
        return await pruefe(url, sitzung: URLSession(configuration: k), zeit: 3)
    }

    private static func pruefe(_ url: URL, sitzung: URLSession, zeit: TimeInterval = 1.2) async -> GefundenerServer? {
        var r = URLRequest(url: url.appendingPathComponent("api/config")); r.timeoutInterval = zeit
        guard let (d, a) = try? await sitzung.data(for: r), (a as? HTTPURLResponse)?.statusCode == 200, let info = showcaseInfo(d) else { return nil }
        var basis = URLComponents(url: a.url ?? url, resolvingAgainstBaseURL: false)                  // nach einer Weiterleitung (z. B. auf https) gilt die Endadresse
        basis?.path = ""; basis?.query = nil
        return GefundenerServer(url: basis?.url ?? url, name: info.name, anmeldung: info.auth)
    }

    /// `gefunden` wird für jeden Treffer sofort aufgerufen (die Liste muss nicht bis zum Ende warten).
    static func suchen(adressen: [String] = eigeneAdressen(), weitere: [String] = [], mitNamen: Bool = true, gefunden melde: (@Sendable (GefundenerServer) -> Void)? = nil) async -> [GefundenerServer] {
        var urls = (mitNamen ? namenKandidaten() : []) + kandidaten(praefixe: praefixe(adressen: adressen) + weitere)
        var gesehen = Set<URL>(); urls = urls.filter { gesehen.insert($0).inserted }
        guard !urls.isEmpty else { return [] }
        let konfig = URLSessionConfiguration.ephemeral
        konfig.timeoutIntervalForRequest = 1.2; konfig.waitsForConnectivity = false; konfig.httpMaximumConnectionsPerHost = 4; konfig.urlCache = nil
        let sitzung = URLSession(configuration: konfig)
        var gefunden: [GefundenerServer] = []
        await withTaskGroup(of: GefundenerServer?.self) { gruppe in
            var naechste = urls.makeIterator(), laufend = 0
            func starten() { if let u = naechste.next() { laufend += 1; gruppe.addTask { await pruefe(u, sitzung: sitzung) } } }
            for _ in 0..<200 { starten() }
            while laufend > 0, let e = await gruppe.next() {
                laufend -= 1
                if let e, !gefunden.contains(where: { $0.url == e.url }) { gefunden.append(e); melde?(e) }
                starten()
            }
        }
        return gefunden.sorted { $0.anzeigeAdresse.localizedStandardCompare($1.anzeigeAdresse) == .orderedAscending }
    }
}
