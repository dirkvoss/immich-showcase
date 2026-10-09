import Foundation

/// Aufbereitung der Server-Adresse, die der Mensch eintippt oder die ein QR-Code liefert.
enum Adresse {
    /// "192.168.1.20:8090" -> "http://192.168.1.20:8090", "meine.domain.de" -> "https://meine.domain.de".
    /// Nil bei offensichtlichem Unsinn.
    static func normalisieren(_ roh: String) -> URL? {
        var t = roh.trimmingCharacters(in: .whitespacesAndNewlines)
        while t.hasSuffix("/") { t.removeLast() }
        guard !t.isEmpty, !t.contains(" ") else { return nil }
        if t.contains("://") && !t.lowercased().hasPrefix("http://") && !t.lowercased().hasPrefix("https://") { return nil }
        if !t.lowercased().hasPrefix("http://") && !t.lowercased().hasPrefix("https://") {
            let istIP = t.range(of: #"^[\d.]+(:\d+)?(/.*)?$"#, options: .regularExpression) != nil
            let host = String(t.lowercased().prefix { $0 != ":" && $0 != "/" })
            let istLokal = host.hasSuffix(".local") || host == "localhost" || !host.contains(".")
            t = ((istIP || istLokal) ? "http://" : "https://") + t
        }
        guard let u = URL(string: t), let host = u.host, !host.isEmpty, ["http", "https"].contains(u.scheme ?? "") else { return nil }
        return u
    }

    /// Alle Adressen, die beim Verbinden der Reihe nach probiert werden. Mit Schema (http:// oder https://) genau eine;
    /// ohne Schema erst die wahrscheinlichere Variante (Domain -> https, IP/lokaler Name -> http), danach die andere.
    static func kandidaten(_ roh: String) -> [URL] {
        guard let erste = normalisieren(roh) else { return [] }
        let t = roh.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if t.hasPrefix("http://") || t.hasPrefix("https://") { return [erste] }
        var comp = URLComponents(url: erste, resolvingAgainstBaseURL: false)
        comp?.scheme = erste.scheme == "https" ? "http" : "https"
        guard let zweite = comp?.url else { return [erste] }
        return [erste, zweite]
    }

    /// Verbindungs-Link aus dem QR-Code der Web-App: showcase://verbinden?adresse=<url>
    static func ausVerbindungsLink(_ url: URL) -> URL? {
        guard url.scheme == "showcase", url.host == "verbinden",
              let teil = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first(where: { $0.name == "adresse" })?.value
        else { return nil }
        return normalisieren(teil)
    }

    /// Ein QR-Code kann auch nur die nackte Adresse enthalten.
    static func ausQRText(_ text: String) -> URL? {
        if let u = URL(string: text), u.scheme == "showcase" { return ausVerbindungsLink(u) }
        return normalisieren(text)
    }

    /// Nur http(s)-Adressen im selben Server bleiben in der App; alles andere geht in den Browser.
    static func gehoertZumServer(_ ziel: URL, server: URL) -> Bool {
        ziel.host?.lowercased() == server.host?.lowercased() && (ziel.port ?? 0) == (server.port ?? 0)
    }
}
