import SwiftUI
import WebKit

/// Die Showcase-Oberfläche in einer Web-Ansicht. Anmeldung (Cookie) bleibt erhalten; Fehler werden freundlich angezeigt.
struct WebAnsicht: View {
    @EnvironmentObject var modell: AppModell
    let server: URL
    var demo = false
    @State private var fehler: String?
    @State private var ladeNummer = 0
    @State private var pruefenOffen = false
    @State private var scannerOffen = false

    var body: some View {
        ZStack {
            WebKitAnsicht(server: server, demo: demo, neuLaden: ladeNummer,
                          fehler: { fehler = $0 }, einstellungen: { modell.einstellungenOffen = true }, demoBeenden: { modell.demoBeenden() })
                .opacity(fehler == nil ? 1 : 0)
            if let fehler {
                VStack(spacing: 16) {
                    Image(systemName: "wifi.exclamationmark").font(.system(size: 44)).foregroundStyle(.secondary)
                    Text("Keine Verbindung zum Server").font(.headline)
                    Text(fehler).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center).padding(.horizontal, 32)
                    Button("Erneut versuchen") { self.fehler = nil; ladeNummer += 1 }.buttonStyle(.borderedProminent).tint(Color(red: 0.88, green: 0.70, blue: 0.35))
                    Button("Verbindung prüfen") { pruefenOffen = true }
                    Button("Server ändern") { modell.einstellungenOffen = true }
                }
            }
        }
        .sheet(isPresented: $pruefenOffen) { VerbindungspruefungAnsicht(server: server) }
        .sheet(isPresented: $scannerOffen) {
            QRScanner { text in scannerOffen = false; NotificationCenter.default.post(name: .showcaseQrErgebnis, object: text) }.ignoresSafeArea()
        }
        .onReceive(NotificationCenter.default.publisher(for: .showcaseQrScannen)) { _ in if QRScanner.verfuegbar { scannerOffen = true } else { NotificationCenter.default.post(name: .showcaseQrErgebnis, object: "") } }
    }
}

struct WebKitAnsicht: UIViewRepresentable {
    let server: URL
    var demo = false
    let neuLaden: Int
    let fehler: (String) -> Void
    let einstellungen: () -> Void
    var demoBeenden: () -> Void = {}

    func makeCoordinator() -> Koordinator { Koordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let konfig = WKWebViewConfiguration()
        konfig.allowsInlineMediaPlayback = true
        konfig.applicationNameForUserAgent = "ShowcaseApp/\(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0")"
        konfig.userContentController.add(context.coordinator, name: "showcase")
        if demo { konfig.setURLSchemeHandler(DemoServer(), forURLScheme: DemoServer.schema) }
        let web = WKWebView(frame: .zero, configuration: konfig)
        web.navigationDelegate = context.coordinator
        web.uiDelegate = context.coordinator
        web.allowsBackForwardNavigationGestures = true
        web.isOpaque = false
        web.backgroundColor = UIColor(red: 0.07, green: 0.08, blue: 0.11, alpha: 1)
        web.scrollView.backgroundColor = web.backgroundColor
        #if DEBUG
        web.isInspectable = true
        #endif
        let refresh = UIRefreshControl()
        refresh.addTarget(context.coordinator, action: #selector(Koordinator.neuLadenGezogen(_:)), for: .valueChanged)
        web.scrollView.refreshControl = refresh
        context.coordinator.web = web
        web.load(URLRequest(url: server))
        return web
    }

    func updateUIView(_ web: WKWebView, context: Context) {
        context.coordinator.eltern = self
        if context.coordinator.letzteNummer != neuLaden {
            context.coordinator.letzteNummer = neuLaden
            web.load(URLRequest(url: server))
        }
    }

    final class Koordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
        var eltern: WebKitAnsicht
        weak var web: WKWebView?
        var letzteNummer = 0
        init(_ eltern: WebKitAnsicht) {
            self.eltern = eltern
            super.init()
            // Kommt die App wieder nach vorne, den Zustand des Rahmens neu laden (Siri, Teilen oder das Widget haben ihn evtl. geändert)
            NotificationCenter.default.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in
                self?.web?.evaluateJavaScript("window.rwAktualisieren && window.rwAktualisieren()")
            }
            NotificationCenter.default.addObserver(forName: .showcaseQrErgebnis, object: nil, queue: .main) { [weak self] n in
                let text = (n.object as? String) ?? ""
                let json = (try? JSONSerialization.data(withJSONObject: [text], options: []))
                    .flatMap { String(data: $0, encoding: .utf8) }.map { String($0.dropFirst().dropLast()) } ?? "\"\""
                self?.web?.evaluateJavaScript("window.rwQrErgebnis && window.rwQrErgebnis(\(json))")
            }
            NotificationCenter.default.addObserver(forName: .showcaseGesundheit, object: nil, queue: .main) { [weak self] _ in
                self?.web?.evaluateJavaScript("window.rwGesundheitOeffnen && window.rwGesundheitOeffnen()")
            }
            NotificationCenter.default.addObserver(forName: .showcaseHilfe, object: nil, queue: .main) { [weak self] _ in
                self?.web?.evaluateJavaScript("window.rwHilfeOeffnen && window.rwHilfeOeffnen()")
            }
        }
        deinit { NotificationCenter.default.removeObserver(self) }

        @objc func neuLadenGezogen(_ r: UIRefreshControl) { web?.reload() }

        func webView(_ webView: WKWebView, decidePolicyFor aktion: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let ziel = aktion.request.url else { return decisionHandler(.allow) }
            if ["about", "blob", "data", DemoServer.schema].contains(ziel.scheme ?? "") { return decisionHandler(.allow) }
            if ["http", "https"].contains(ziel.scheme ?? ""), !Adresse.gehoertZumServer(ziel, server: eltern.server) {
                UIApplication.shared.open(ziel)                              // fremde Seiten (z. B. GitHub) im Browser
                return decisionHandler(.cancel)
            }
            decisionHandler(.allow)
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            webView.scrollView.refreshControl?.endRefreshing()
            if !eltern.demo { let s = eltern.server; Task { await ServerKlient.fuerErweiterungenSichern(server: s) } }      // Anmeldung (PIN-Cookie) für Teilen-Erweiterung und Widget merken
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { melden(error, webView) }
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { melden(error, webView) }
        private func melden(_ error: Error, _ webView: WKWebView) {
            webView.scrollView.refreshControl?.endRefreshing()
            if (error as? URLError)?.code == .cancelled { return }
            eltern.fehler(L("Der Server unter \(eltern.server.absoluteString) antwortet nicht."))
        }

        // Neue Fenster (target=_blank) im selben Fenster öffnen bzw. nach außen reichen
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for aktion: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let u = aktion.request.url { if Adresse.gehoertZumServer(u, server: eltern.server) { webView.load(aktion.request) } else { UIApplication.shared.open(u) } }
            return nil
        }
        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: L("Abbrechen"), style: .cancel) { _ in completionHandler(false) })
            a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler(true) })
            UIApplication.shared.keyFenster?.rootViewController?.topmost.present(a, animated: true)
        }
        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            UIApplication.shared.keyFenster?.rootViewController?.topmost.present(a, animated: true)
        }

        // Brücke: window.webkit.messageHandlers.showcase.postMessage({aktion: "einstellungen"})
        func userContentController(_ c: WKUserContentController, didReceive m: WKScriptMessage) {
            guard let d = m.body as? [String: Any], let aktion = d["aktion"] as? String else { return }
            if aktion == "einstellungen" { DispatchQueue.main.async { self.eltern.einstellungen() } }
            if aktion == "demoBeenden" { DispatchQueue.main.async { self.eltern.demoBeenden() } }
            if aktion == "pinMerken", UserDefaults.standard.bool(forKey: "pinMitFaceID"), let pin = d["pin"] as? String, let host = eltern.server.host { PinSpeicher.speichern(pin, fuer: host) }
            if aktion == "pinHolen", UserDefaults.standard.bool(forKey: "pinMitFaceID"), let host = eltern.server.host {
                Task { @MainActor in
                    guard PinSpeicher.vorhanden(fuer: host), let pin = await PinSpeicher.holen(fuer: host, grund: L("Showcase Immich anmelden")) else { return }
                    self.web?.evaluateJavaScript("window.rwPinErgebnis && window.rwPinErgebnis('\(pin)')", completionHandler: nil)
                }
            }
            if aktion == "qrScannen" { DispatchQueue.main.async { NotificationCenter.default.post(name: .showcaseQrScannen, object: nil) } }
        }
    }
}

extension UIApplication {
    var keyFenster: UIWindow? { connectedScenes.compactMap { ($0 as? UIWindowScene)?.windows.first(where: \.isKeyWindow) }.first }
}
extension UIViewController {
    var topmost: UIViewController { presentedViewController?.topmost ?? self }
}
