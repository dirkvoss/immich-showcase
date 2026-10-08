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
        }
    }
}
