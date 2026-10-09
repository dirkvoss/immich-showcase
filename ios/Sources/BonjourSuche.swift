import Foundation
import Network
import os

/// Lauscht im Netz auf Immich-Showcase-Server, die sich per Bonjour (Diensttyp _showcase._tcp) anmelden (docker-compose.bonjour.yml).
/// Findet auch Server in anderen Netzen, wenn der Router Bonjour (mDNS) weiterleitet.
final class BonjourSuche {
    private static let log = Logger(subsystem: "com.dirk-voss.showcase", category: "bonjour")
    static let typ = "_showcase._tcp"
    private var browser: NWBrowser?
    private var verbindungen: [NWEndpoint: NWConnection] = [:]
    private let queue = DispatchQueue(label: "showcase.bonjour")

    /// Adresse als URL: IPv6 und Zonenkennungen („%en0“) lassen wir weg, Port 80 wird nicht angehaengt.
    static func url(host: String, port: Int) -> URL? {
        let h = host.split(separator: "%").first.map(String.init) ?? host
        guard !h.contains(":"), !h.isEmpty else { return nil }
        return URL(string: "http://\(h)" + (port == 80 ? "" : ":\(port)"))
    }

    /// `gefunden` wird mit der Adresse eines angemeldeten Servers aufgerufen (bitte danach pruefen, ob dort wirklich Showcase antwortet).
    func start(gefunden: @escaping @Sendable (URL) -> Void) {
        stop()
        let b = NWBrowser(for: .bonjour(type: Self.typ, domain: nil), using: .tcp)
        b.browseResultsChangedHandler = { [weak self] ergebnisse, _ in
            Self.log.info("Bonjour-Ergebnisse: \(ergebnisse.count)")
            for e in ergebnisse { self?.aufloesen(e.endpoint, gefunden) }
        }
        b.stateUpdateHandler = { Self.log.info("Browser: \(String(describing: $0))") }
        b.start(queue: queue)
        browser = b
    }

    func stop() {
        browser?.cancel(); browser = nil
        queue.async { [self] in verbindungen.values.forEach { $0.cancel() }; verbindungen.removeAll() }
    }

    private func aufloesen(_ endpoint: NWEndpoint, _ gefunden: @escaping @Sendable (URL) -> Void) {
        queue.async { [self] in
            guard verbindungen[endpoint] == nil else { return }
            let c = NWConnection(to: endpoint, using: .tcp)
            verbindungen[endpoint] = c
            c.stateUpdateHandler = { [weak self] state in
                Self.log.info("Verbindung: \(String(describing: state))")
                switch state {
                case .ready:
                    if case let .hostPort(host, port)? = c.currentPath?.remoteEndpoint {
                        let text: String
                        switch host { case .ipv4(let a): text = "\(a)"; case .name(let n, _): text = n; default: text = "" }
                        if let u = Self.url(host: text, port: Int(port.rawValue)) { gefunden(u) }
                    }
                    c.cancel()
                case .failed, .cancelled:
                    self?.queue.async { self?.verbindungen[endpoint] = nil }
                default: break
                }
            }
            c.start(queue: queue)
        }
    }
}
