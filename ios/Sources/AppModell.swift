import SwiftUI
import LocalAuthentication

@MainActor
final class AppModell: ObservableObject {
    @AppStorage("serverAdresse") private var gespeichert = ""
    @AppStorage("faceIDAktiv") var faceIDAktiv = false

    @Published var server: URL?
    @Published var gesperrt = false
    @Published var einstellungenOffen = false
    @Published var fehlerText: String?

    init() {
        server = Adresse.normalisieren(gespeichert)
        gesperrt = faceIDAktiv
    }

    func serverSetzen(_ url: URL?) {
        server = url
        gespeichert = url?.absoluteString ?? ""
    }

    func verbindungsLinkOeffnen(_ url: URL) {
        if let u = Adresse.ausVerbindungsLink(url) { serverSetzen(u) }
    }

    /// Prüft, ob unter der Adresse ein Immich-Showcase-Server antwortet.
    func pruefen(_ url: URL) async -> Result<String, Fehler> {
        var req = URLRequest(url: url.appendingPathComponent("api/config"))
        req.timeoutInterval = 8
        do {
            let (daten, antwort) = try await URLSession.shared.data(for: req)
            guard (antwort as? HTTPURLResponse)?.statusCode == 200,
                  let json = try JSONSerialization.jsonObject(with: daten) as? [String: Any], let name = json["name"] as? String
            else { return .failure(.keinShowcase) }
            return .success(name)
        } catch let e as URLError where e.code == .notConnectedToInternet || e.code == .cannotFindHost || e.code == .timedOut || e.code == .cannotConnectToHost {
            return .failure(.nichtErreichbar)
        } catch let e as URLError {
            return .failure(.verbindung("\(e.localizedDescription) (\(e.code.rawValue))"))
        } catch { return .failure(.keinShowcase) }
    }

    enum Fehler: Error { case nichtErreichbar, keinShowcase, verbindung(String)
        var text: String {
            switch self {
            case .nichtErreichbar: return "Der Server ist nicht erreichbar. Prüfe die Adresse und ob du im richtigen Netz bist."
            case .keinShowcase: return "Unter dieser Adresse antwortet kein Immich Showcase."
            case .verbindung(let d): return "Die Verbindung ist fehlgeschlagen: \(d)"
            }
        }
    }

    func entsperren() {
        let kontext = LAContext()
        var err: NSError?
        guard kontext.canEvaluatePolicy(.deviceOwnerAuthentication, error: &err) else { gesperrt = false; return }
        kontext.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Showcase Immich entsperren") { ok, _ in
            Task { @MainActor in if ok { self.gesperrt = false } }
        }
    }

    func appWurdeInaktiv() { if faceIDAktiv { gesperrt = true } }
}
