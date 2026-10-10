import BackgroundTasks
import EventKit
import SwiftUI

/// Gibt auf Wunsch die Termine der gewählten iPhone-Kalender (iCloud, Google, Exchange, CalDAV … alles, was im Kalender steht) an den
/// Showcase-Server. Der Rahmen zeigt daraus die nächsten Termine des Tages. Ohne Einschalten wird nichts gelesen und nichts gesendet.
@MainActor
final class KalenderSync: ObservableObject {
    static let gemeinsam = KalenderSync()
    static let aufgabe = "com.dirk-voss.showcase.kalender"
    static let tage = 3

    private let d = UserDefaults.standard
    private let speicher = EKEventStore()
    private var beobachter: NSObjectProtocol?
    private var verzoegerung: Task<Void, Never>?
    private var sendet = false

    @Published var aktiv: Bool { didSet { d.set(aktiv, forKey: "kalenderAktiv") } }
    @Published var nurZeiten: Bool { didSet { d.set(nurZeiten, forKey: "kalenderNurZeiten"); nachAenderung() } }
    @Published var name: String { didSet { d.set(name, forKey: "kalenderName") } }
    @Published var kuerzel: String { didSet { d.set(String(kuerzel.prefix(2)), forKey: "kalenderKuerzel") } }      // steht am Rahmen vor den Terminen, wenn mehrere Handys teilen
    @Published var farbe: String { didSet { d.set(farbe, forKey: "kalenderFarbe") } }                            // #rrggbb
    @Published var auswahl: Set<String> { didSet { d.set(Array(auswahl), forKey: "kalenderAuswahl") } }
    @Published var status: String?
    @Published var zugriffVerweigert = false

    private init() {
        aktiv = d.bool(forKey: "kalenderAktiv")
        nurZeiten = d.bool(forKey: "kalenderNurZeiten")
        name = d.string(forKey: "kalenderName") ?? "iPhone"
        auswahl = Set(d.stringArray(forKey: "kalenderAuswahl") ?? [])
        let q = d.string(forKey: "kalenderQuelle") ?? UUID().uuidString.lowercased()
        d.set(q, forKey: "kalenderQuelle")
        kuerzel = d.string(forKey: "kalenderKuerzel") ?? "iPhone".prefix(1).uppercased()
        farbe = d.string(forKey: "kalenderFarbe") ?? Self.farbpalette[Int(q.unicodeScalars.reduce(0) { $0 &+ $1.value } % UInt32(Self.farbpalette.count))]      // stabil, nicht zufällig je Start
        if d.string(forKey: "kalenderFarbe") == nil { d.set(farbe, forKey: "kalenderFarbe") }
        if d.string(forKey: "kalenderKuerzel") == nil { d.set(kuerzel, forKey: "kalenderKuerzel") }
        if aktiv { beobachten() }
    }

    static let farbpalette = ["#e0a24a", "#5ac8fa", "#34c759", "#ff6b6b", "#bf5af2", "#ff9f0a"]

    /// Zufällige, dauerhafte Kennung dieses Handys beim Server (keine Konten, nur diese Nummer).
    var quelle: String {
        if let q = d.string(forKey: "kalenderQuelle"), !q.isEmpty { return q }
        let q = UUID().uuidString.lowercased()
        d.set(q, forKey: "kalenderQuelle")
        return q
    }

    var erlaubt: Bool { EKEventStore.authorizationStatus(for: .event) == .fullAccess }

    /// Alle Kalender des Handys, nach Konto geordnet (für die Auswahl).
    func kalender() -> [EKCalendar] {
        guard erlaubt else { return [] }
        return speicher.calendars(for: .event).sorted { ($0.source.title, $0.title) < ($1.source.title, $1.title) }
    }

    func einschalten() async {
        zugriffVerweigert = false
        let ok = (try? await speicher.requestFullAccessToEvents()) ?? false
        guard ok else { aktiv = false; zugriffVerweigert = true; return }
        if auswahl.isEmpty { auswahl = Set(kalender().map(\.calendarIdentifier)) }
        aktiv = true
        beobachten()
        await senden()
    }

    func ausschalten() async {
        aktiv = false
        status = nil
        verzoegerung?.cancel()
        if let b = beobachter { NotificationCenter.default.removeObserver(b); beobachter = nil }
        if let k = try? await ServerKlient.erstellen() { _ = try? await k.aufruf(k.anfrage("DELETE", "termine/telefon/" + quelle)) }    // der Server vergisst die Termine dieses Handys
    }

    /// Termine der gewählten Kalender von heute bis in einige Tage.
    func sammeln(ab start: Date = Date()) -> [KalenderNutzlast.Eintrag] {
        guard erlaubt else { return [] }
        let kal = Calendar.current
        let von = kal.startOfDay(for: start), bis = kal.date(byAdding: .day, value: Self.tage, to: von) ?? von.addingTimeInterval(3 * 86400)
        let kalender = speicher.calendars(for: .event).filter { auswahl.contains($0.calendarIdentifier) }
        guard !kalender.isEmpty else { return [] }
        let treffer = speicher.events(matching: speicher.predicateForEvents(withStart: von, end: bis, calendars: kalender))
        return treffer.filter { $0.status != .canceled }.sorted { $0.startDate < $1.startDate }
            .map { KalenderNutzlast.Eintrag(titel: $0.title ?? "", von: $0.startDate, bis: $0.endDate ?? $0.startDate, ganztag: $0.isAllDay, geburtstag: $0.calendar.type == .birthday) }
    }

    func senden() async {
        guard aktiv, erlaubt, !sendet else { return }
        sendet = true
        defer { sendet = false }
        do {
            let k = try await ServerKlient.erstellen()
            let termine = KalenderNutzlast.termine(sammeln(), nurZeiten: nurZeiten, platzhalter: L("Termin"))
            let antwort = try await k.aufruf(k.anfrage("PUT", "termine/telefon", koerper: ["quelle": quelle, "name": name.isEmpty ? "iPhone" : name, "kuerzel": kuerzel, "farbe": farbe, "termine": termine]))
            let n = (antwort["anzahl"] as? Int) ?? termine.count
            status = L("Zuletzt gesendet: \(Int(n)) Termine, \(Date().formatted(date: .omitted, time: .shortened))")
        } catch {
            status = L("Senden nicht möglich: \(error.localizedDescription)")
        }
    }

    // MARK: Wann wird gesendet?

    /// Beim Öffnen der App und wenn sich der Kalender ändert, solange die App läuft.
    private func beobachten() {
        guard beobachter == nil else { return }
        beobachter = NotificationCenter.default.addObserver(forName: .EKEventStoreChanged, object: speicher, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.nachAenderung() }
        }
    }

    func nachAenderung() {
        guard aktiv else { return }
        verzoegerung?.cancel()
        verzoegerung = Task { try? await Task.sleep(for: .seconds(5)); if !Task.isCancelled { await senden() } }       // mehrere Änderungen auf einmal zusammenfassen
    }

    /// iOS startet die App nach eigenem Ermessen kurz im Hintergrund (etwa alle paar Stunden), damit sendet sie den aktuellen Stand.
    func hintergrundPlanen() {
        guard aktiv else { return }
        let anfrage = BGAppRefreshTaskRequest(identifier: Self.aufgabe)
        anfrage.earliestBeginDate = Date(timeIntervalSinceNow: 30 * 60)
        try? BGTaskScheduler.shared.submit(anfrage)
    }

    func hintergrundLauf() async {
        await senden()
        hintergrundPlanen()
    }

    #if DEBUG
    /// Nur für Tests im Simulator (Startargument -KalenderTestdaten): legt ein paar Beispieltermine im Standardkalender an.
    func testtermineAnlegen() async {
        guard (try? await speicher.requestFullAccessToEvents()) == true, let kal = speicher.defaultCalendarForNewEvents else { return }
        let jetzt = Date(), cal = Calendar.current
        guard speicher.events(matching: speicher.predicateForEvents(withStart: cal.startOfDay(for: jetzt), end: jetzt.addingTimeInterval(86400 * 2), calendars: [kal])).isEmpty else { return }
        for (titel, stunden, dauer) in [("Zahnarzt", 1.0, 1.0), ("Elternabend", 5.0, 2.0), ("Training mit den Kindern", 8.0, 1.5)] {
            let e = EKEvent(eventStore: speicher); e.title = titel; e.calendar = kal
            e.startDate = jetzt.addingTimeInterval(stunden * 3600); e.endDate = e.startDate.addingTimeInterval(dauer * 3600)
            try? speicher.save(e, span: .thisEvent)
        }
        let g = EKEvent(eventStore: speicher); g.title = "Geburtstag Oma"; g.calendar = kal; g.isAllDay = true
        g.startDate = cal.startOfDay(for: jetzt); g.endDate = g.startDate
        try? speicher.save(g, span: .thisEvent)
        auswahl = Set(kalender().map(\.calendarIdentifier)); aktiv = true; beobachten()
        await senden()
    }
    #endif
}
