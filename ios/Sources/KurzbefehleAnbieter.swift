import AppIntents

/// Die Sätze für Siri (müssen im Hauptprogramm stehen, nicht im Widget).
struct ShowcaseKurzbefehle: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: FotosZeigenIntent(),
                    phrases: ["Zeige Fotos auf dem Rahmen mit \(.applicationName)", "Fotos auf den Rahmen mit \(.applicationName)"],
                    shortTitle: "Fotos zeigen", systemImageName: "photo.on.rectangle")
        AppShortcut(intent: ShowBeendenIntent(),
                    phrases: ["Beende die Show mit \(.applicationName)", "Rahmen wieder normal mit \(.applicationName)"],
                    shortTitle: "Show beenden", systemImageName: "stop.circle")
        AppShortcut(intent: ZurueckIntent(),
                    phrases: ["Zurück zur vorherigen Show mit \(.applicationName)"],
                    shortTitle: "Zurück", systemImageName: "arrow.uturn.backward")
    }
}
