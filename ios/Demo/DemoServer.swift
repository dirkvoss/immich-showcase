import Foundation
import WebKit
import UniformTypeIdentifiers

/// Liefert im Demo-Modus die Oberfläche (aus dem App-Paket) und die erfundene Schnittstelle unter showcase-demo://demo/ aus.
final class DemoServer: NSObject, WKURLSchemeHandler {
    static let schema = "showcase-demo"
    static let startURL = URL(string: "\(schema)://demo/")!

    private let api = DemoAPI(version: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "demo")
    private var aktiv = Set<ObjectIdentifier>()
    private let arbeit = DispatchQueue(label: "showcase.demo", qos: .userInitiated, attributes: .concurrent)

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        aktiv.insert(ObjectIdentifier(task))
        let req = task.request
        let koerper = req.httpBody.flatMap { (try? JSONSerialization.jsonObject(with: $0)) as? [String: Any] } ?? [:]
        arbeit.async { [self] in
            let a = antworten(req, koerper)
            DispatchQueue.main.async {
                guard self.aktiv.remove(ObjectIdentifier(task)) != nil, let url = req.url else { return }
                let kopf = ["Content-Type": a.mime, "Content-Length": String(a.daten.count), "Cache-Control": a.mime == "application/json" ? "no-store" : "no-cache"]
                guard let r = HTTPURLResponse(url: url, statusCode: a.status, httpVersion: "HTTP/1.1", headerFields: kopf) else { return }
                task.didReceive(r); task.didReceive(a.daten); task.didFinish()
            }
        }
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) { aktiv.remove(ObjectIdentifier(task)) }

    func antworten(_ req: URLRequest, _ koerper: [String: Any]) -> DemoAPI.Antwort {
        guard let url = req.url else { return DemoAPI.Antwort(status: 400) }
        let pfad = url.path.isEmpty ? "/" : url.path
        if pfad.hasPrefix("/api/") {
            let q = Dictionary((URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []).map { ($0.name, $0.value ?? "") }) { _, neu in neu }
            return api.antwort(methode: req.httpMethod ?? "GET", pfad: String(pfad.dropFirst(0)), abfrage: q, koerper: koerper)
        }
        return Self.datei(pfad)
    }

    /// Dateien der Oberfläche aus dem App-Paket (Ordner "static", eine Kopie von ../static/).
    static func datei(_ pfad: String) -> DemoAPI.Antwort {
        guard let wurzel = Bundle.main.url(forResource: "static", withExtension: nil) else { return DemoAPI.Antwort(status: 500, daten: Data("web fehlt".utf8), mime: "text/plain") }
        var rel = String(pfad.dropFirst())
        if rel.isEmpty || rel.hasSuffix("/") { rel += "index.html" }
        if rel.contains("..") { return DemoAPI.Antwort(status: 400) }
        let ziel = wurzel.appendingPathComponent(rel)
        guard let d = try? Data(contentsOf: ziel) else { return DemoAPI.Antwort(status: 404, daten: Data("nicht gefunden".utf8), mime: "text/plain") }
        return DemoAPI.Antwort(daten: d, mime: mime(ziel.pathExtension.lowercased()))
    }

    static func mime(_ ext: String) -> String {
        switch ext {
        case "html": return "text/html; charset=utf-8"
        case "js": return "application/javascript; charset=utf-8"
        case "json": return "application/json; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "png": return "image/png"
        case "svg": return "image/svg+xml"
        case "woff2": return "font/woff2"
        case "webmanifest": return "application/manifest+json"
        default: return "application/octet-stream"
        }
    }
}
