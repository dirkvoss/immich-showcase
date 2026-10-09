import AppIntents
import WidgetKit

/// Aktionen für Siri, die Kurzbefehle-App und das Widget: Fotos auf den Rahmen schicken, Show beenden, zurück zur vorherigen Show.
/// Laufen im Hintergrund und nutzen Server und Anmeldung aus dem gemeinsamen Speicher.

struct RahmenEntitaet: AppEntity {
    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Bilderrahmen")
    static var defaultQuery = RahmenAbfrage()
    var id: String
    var name: String
    var displayRepresentation: DisplayRepresentation { DisplayRepresentation(title: "\(name)") }
}

struct RahmenAbfrage: EntityQuery {
    private func alle() async throws -> [RahmenEntitaet] {
        try await ServerKlient.ausSpeicher().rahmen().map { RahmenEntitaet(id: $0.id, name: $0.name) }
    }
    func entities(for identifiers: [String]) async throws -> [RahmenEntitaet] { try await alle().filter { identifiers.contains($0.id) } }
    func suggestedEntities() async throws -> [RahmenEntitaet] { try await alle() }
}

struct FotosZeigenIntent: AppIntent {
    static var title: LocalizedStringResource = "Fotos auf den Rahmen zeigen"
    static var description = IntentDescription("Sucht Fotos in Immich (zum Beispiel „Sommer 2022 am Strand“) und zeigt sie auf dem Bilderrahmen.")

    @Parameter(title: "Was soll gezeigt werden?", requestValueDialog: "Was soll ich auf dem Rahmen zeigen?")
    var suche: String

    @Parameter(title: "Rahmen", description: "Leer lassen für den Standard-Rahmen.")
    var rahmen: RahmenEntitaet?

    static var parameterSummary: some ParameterSummary { Summary("Zeige \(\.$suche) auf \(\.$rahmen)") }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let text = try await ServerKlient.ausSpeicher().fotosZeigen(suche: suche, rahmen: rahmen?.id)
        WidgetCenter.shared.reloadAllTimelines()
        return .result(dialog: IntentDialog(stringLiteral: text))
    }
}

struct ShowBeendenIntent: AppIntent {
    static var title: LocalizedStringResource = "Show auf dem Rahmen beenden"
    static var description = IntentDescription("Der Rahmen zeigt wieder das normale Programm.")

    @Parameter(title: "Rahmen", description: "Leer lassen für den Standard-Rahmen.")
    var rahmen: RahmenEntitaet?

    static var parameterSummary: some ParameterSummary { Summary("Show beenden auf \(\.$rahmen)") }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let text = try await ServerKlient.ausSpeicher().normal(rahmen: rahmen?.id)
        WidgetCenter.shared.reloadAllTimelines()
        return .result(dialog: IntentDialog(stringLiteral: text))
    }
}

struct ZurueckIntent: AppIntent {
    static var title: LocalizedStringResource = "Zur vorherigen Show zurück"
    static var description = IntentDescription("Der Rahmen springt zur Show zurück, die vor der aktuellen lief.")

    @Parameter(title: "Rahmen", description: "Leer lassen für den Standard-Rahmen.")
    var rahmen: RahmenEntitaet?

    static var parameterSummary: some ParameterSummary { Summary("Zurück auf \(\.$rahmen)") }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let text = try await ServerKlient.ausSpeicher().zurueck(rahmen: rahmen?.id)
        WidgetCenter.shared.reloadAllTimelines()
        return .result(dialog: IntentDialog(stringLiteral: text))
    }
}
