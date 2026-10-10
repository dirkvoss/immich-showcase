import SwiftUI
import LocalAuthentication

extension Notification.Name {
    static let showcaseHilfe = Notification.Name("showcaseHilfe")
    static let showcaseGesundheit = Notification.Name("showcaseGesundheit")
    static let showcaseQrScannen = Notification.Name("showcaseQrScannen")
    static let showcaseQrErgebnis = Notification.Name("showcaseQrErgebnis")
}

struct EinstellungenAnsicht: View {
    @EnvironmentObject var modell: AppModell
    @Environment(\.dismiss) private var schliessen
    @State private var hinweis: String?
    @State private var pruefenOffen = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Server") {
                    if modell.demoAktiv {
                        Text("Demo-Modus: Beispielfotos, es wird nichts gesendet.").foregroundStyle(.secondary)
                        Button(modell.server == nil ? "Demo beenden und eigenen Server verbinden" : "Demo beenden (zurück zu deinem Server)") { modell.demoBeenden(); schliessen() }
                    } else {
                        Text(modell.server?.absoluteString ?? "nicht verbunden").foregroundStyle(.secondary)
                        Button("Server ändern", role: .destructive) { modell.serverSetzen(nil); schliessen() }
                        if let server = modell.server { Button("Verbindung prüfen") { pruefenOffen = true }.sheet(isPresented: $pruefenOffen) { VerbindungspruefungAnsicht(server: server) } }
                        Button("Demo ansehen (Beispielfotos, ohne Server)") { modell.demoStarten(); schliessen() }
                    }
                }
                if modell.server != nil && !modell.demoAktiv { KalenderAbschnitt() }
                Section("Sicherheit") {
                    Toggle("Mit Face ID sperren", isOn: Binding(get: { modell.faceIDAktiv }, set: { an in faceID(an) }))
                    Toggle("Mit Face ID anmelden (PIN merken)", isOn: Binding(get: { modell.pinMitFaceID }, set: { an in
                        modell.pinMitFaceID = an
                        if !an, let h = modell.server?.host { PinSpeicher.loeschen(fuer: h) }
                    }))
                    if modell.pinMitFaceID { Text("Die PIN wird beim nächsten Anmelden im geschützten Schlüsselbund gemerkt und danach per Face ID eingesetzt.").font(.footnote).foregroundStyle(.secondary) }
                    if let hinweis { Text(hinweis).font(.footnote).foregroundStyle(.secondary) }
                }
                Section("Hilfe") {
                    Button("Hilfe anzeigen") { schliessen(); NotificationCenter.default.post(name: .showcaseHilfe, object: nil) }
                    Button("Alles in Ordnung? (Status)") { schliessen(); NotificationCenter.default.post(name: .showcaseGesundheit, object: nil) }
                    Link("Anleitung auf GitHub", destination: URL(string: "https://github.com/dirkvoss/frameside#readme")!)
                    Text("Die App zeigt deinen eigenen Frameside-Server. Sie verbindet sich nicht direkt mit Immich.").font(.footnote).foregroundStyle(.secondary)
                }
                Section("Über") {
                    LabeledContent("Entwickelt von", value: "Dirk Voß")
                    LabeledContent("Version", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "–")
                    Link("Projekt auf GitHub", destination: URL(string: "https://github.com/dirkvoss/frameside")!)
                    Text("Unabhängiges Projekt, nicht mit dem Immich-Projekt verbunden.").font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("App-Einstellungen")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Fertig") { schliessen() } } }
        }
    }

    private func faceID(_ an: Bool) {
        guard an else { modell.faceIDAktiv = false; hinweis = nil; return }
        let k = LAContext(); var e: NSError?
        guard k.canEvaluatePolicy(.deviceOwnerAuthentication, error: &e) else { hinweis = L("Auf diesem Gerät ist weder Face ID noch ein Code eingerichtet."); return }
        k.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: L("Sperre einschalten")) { ok, _ in
            Task { @MainActor in modell.faceIDAktiv = ok; hinweis = ok ? nil : L("Die Sperre wurde nicht eingeschaltet.") }
        }
    }
}
