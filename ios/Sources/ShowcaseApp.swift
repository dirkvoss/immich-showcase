import SwiftUI

@main
struct ShowcaseApp: App {
    @StateObject private var modell = AppModell()

    var body: some Scene {
        WindowGroup {
            WurzelAnsicht()
                .environmentObject(modell)
                .onOpenURL { modell.verbindungsLinkOeffnen($0) }
                .preferredColorScheme(.dark)
                #if DEBUG
                .task {
                    if CommandLine.arguments.contains("-KalenderTestdaten") { await KalenderSync.gemeinsam.testtermineAnlegen() }
                    if CommandLine.arguments.contains("-EinstellungenOeffnen") { modell.einstellungenOffen = true }
                }
                #endif
        }
        .backgroundTask(.appRefresh(KalenderSync.aufgabe)) { await KalenderSync.gemeinsam.hintergrundLauf() }
    }
}
