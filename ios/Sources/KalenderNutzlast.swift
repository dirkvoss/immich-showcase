import Foundation

/// Die Termine eines Handys im Format des Showcase-Servers (PUT /api/termine/telefon): Ortszeit ohne Zeitzone, Ganztägiges nur als Datum.
enum KalenderNutzlast {
    struct Eintrag: Equatable {
        let titel: String
        let von: Date
        let bis: Date
        let ganztag: Bool
        var geburtstag = false           // aus dem Geburtstags-Kalender des Handys: der Rahmen zeigt sie als eigene Zeile
    }

    /// Der Server nimmt höchstens 400 Termine an; für die Anzeige am Rahmen reichen einige Tage.
    static let maximum = 300

    private static func formatierer(_ muster: String, _ zone: TimeZone) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = zone
        f.dateFormat = muster
        return f
    }

    /// - Parameter nurZeiten: Titel nicht senden (am Rahmen steht dann nur „Termin“ mit der Uhrzeit).
    static func termine(_ eintraege: [Eintrag], nurZeiten: Bool, zone: TimeZone = .current, platzhalter: String = "Termin") -> [[String: Any]] {
        let tag = formatierer("yyyy-MM-dd", zone), zeit = formatierer("yyyy-MM-dd'T'HH:mm", zone)
        var kalender = Calendar(identifier: .gregorian)
        kalender.timeZone = zone
        return eintraege.prefix(maximum).map { e in
            var t: [String: Any] = ["titel": nurZeiten || e.titel.trimmingCharacters(in: .whitespaces).isEmpty ? platzhalter : e.titel]
            if e.ganztag {
                // EventKit lässt Ganztägiges am letzten Tag um 23:59 enden; der Server erwartet das Ende wie in Kalendern üblich am Folgetag (ausschließlich).
                let letzter = kalender.startOfDay(for: max(e.bis, e.von))
                t["von"] = tag.string(from: e.von)
                t["bis"] = tag.string(from: kalender.date(byAdding: .day, value: 1, to: letzter) ?? letzter)
            } else {
                t["von"] = zeit.string(from: e.von)
                t["bis"] = zeit.string(from: max(e.bis, e.von))
            }
            if e.geburtstag { t["geburtstag"] = true }
            return t
        }
    }
}
