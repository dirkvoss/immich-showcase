import SwiftUI
import LocalAuthentication

extension Notification.Name { static let showcaseHilfe = Notification.Name("showcaseHilfe") }

struct EinstellungenAnsicht: View {
    @EnvironmentObject var modell: AppModell
    @Environment(\.dismiss) private var schliessen
    @State private var hinweis: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Server") {
                    Text(modell.server?.absoluteString ?? "nicht verbunden").foregroundStyle(.secondary)
                    Button("Server ändern", role: .destructive) { modell.serverSetzen(nil); schliessen() }
                }
                Section("Sicherheit") {
                    Toggle("Mit Face ID sperren", isOn: Binding(get: { modell.faceIDAktiv }, set: { an in faceID(an) }))
                    if let hinweis { Text(hinweis).font(.footnote).foregroundStyle(.secondary) }
                }
                Section("Hilfe") {
                    Button("Hilfe anzeigen") { schliessen(); NotificationCenter.default.post(name: .showcaseHilfe, object: nil) }
                    Link("Anleitung auf GitHub", destination: URL(string: "https://github.com/dirkvoss/immich-showcase#readme")!)
                    Text("Die App zeigt deinen eigenen Immich-Showcase-Server. Sie verbindet sich nicht direkt mit Immich.").font(.footnote).foregroundStyle(.secondary)
                }
                Section("Über") {
                    LabeledContent("Entwickelt von", value: "Dirk Voß")
                    LabeledContent("Version", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "–")
                    Link("Projekt auf GitHub", destination: URL(string: "https://github.com/dirkvoss/immich-showcase")!)
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
        guard k.canEvaluatePolicy(.deviceOwnerAuthentication, error: &e) else { hinweis = "Auf diesem Gerät ist weder Face ID noch ein Code eingerichtet."; return }
        k.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Sperre einschalten") { ok, _ in
            Task { @MainActor in modell.faceIDAktiv = ok; hinweis = ok ? nil : "Die Sperre wurde nicht eingeschaltet." }
        }
    }
}
