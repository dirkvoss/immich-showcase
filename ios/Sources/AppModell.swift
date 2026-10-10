import SwiftUI
import LocalAuthentication

@MainActor
final class AppModell: ObservableObject {
    @AppStorage("serverAdresse") private var gespeichert = ""
    @AppStorage("faceIDAktiv") var faceIDAktiv = false
    @AppStorage("demoAktiv") var demoAktiv = false
    @AppStorage("letzterServer") var letzterServer = ""
    @AppStorage("pinMitFaceID") var pinMitFaceID = false

    @Published var server: URL?
    @Published var gesperrt = false
    @Published var einstellungenOffen = false
    @Published var fehlerText: String?

    init() {
        server = Adresse.normalisieren(gespeichert)
        gesperrt = faceIDAktiv
        let s = server
        Task { await ServerKlient.fuerErweiterungenSichern(server: s) }
    }

    func demoStarten() { demoAktiv = true; objectWillChange.send() }
    func demoBeenden() { demoAktiv = false; objectWillChange.send() }

    func serverSetzen(_ url: URL?) {
        demoAktiv = false
        if let alt = server?.host, alt != url?.host { PinSpeicher.loeschen(fuer: alt) }          // gemerkte PIN gehoert zum alten Server
        server = url
        if let url { letzterServer = url.absoluteString }
        gespeichert = url?.absoluteString ?? ""
        Task { await ServerKlient.fuerErweiterungenSichern(server: url) }
    }

    func verbindungsLinkOeffnen(_ url: URL) {
        if let u = Adresse.ausVerbindungsLink(url) { serverSetzen(u) }
    }

    /// Prüft, ob unter der Adresse ein Frameside-Server antwortet.
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
            case .nichtErreichbar: return L("Der Server ist nicht erreichbar. Prüfe die Adresse und ob du im richtigen Netz bist.")
            case .keinShowcase: return L("Unter dieser Adresse antwortet kein Frameside.")
            case .verbindung(let d): return L("Die Verbindung ist fehlgeschlagen: \(d)")
            }
        }
    }

    func entsperren() {
        let kontext = LAContext()
        var err: NSError?
        guard kontext.canEvaluatePolicy(.deviceOwnerAuthentication, error: &err) else { gesperrt = false; return }
        kontext.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: L("Frameside entsperren")) { ok, _ in
            Task { @MainActor in if ok { self.gesperrt = false } }
        }
    }

    func appWurdeInaktiv() { if faceIDAktiv { gesperrt = true } }
}
