import EventKit
import SwiftUI

/// Abschnitt „Kalender auf dem Rahmen“ in den App-Einstellungen.
struct KalenderAbschnitt: View {
    @ObservedObject var kalender = KalenderSync.gemeinsam

    var body: some View {
        Section {
            Toggle("Meine Termine auf dem Rahmen zeigen", isOn: Binding(get: { kalender.aktiv }, set: { an in
                Task { if an { await kalender.einschalten() } else { await kalender.ausschalten() } }
            }))
            if kalender.aktiv {
                NavigationLink {
                    KalenderAuswahlAnsicht()
                } label: {
                    LabeledContent("Kalender auswählen", value: "\(kalender.auswahl.count)")
                }
                Toggle("Nur Uhrzeiten senden (ohne Titel)", isOn: $kalender.nurZeiten)
                LabeledContent("Name dieses Handys") {
                    TextField("iPhone", text: $kalender.name).multilineTextAlignment(.trailing)
                        .onSubmit { kalender.nachAenderung() }
                }
                LabeledContent("Kürzel am Rahmen") {
                    TextField("D", text: $kalender.kuerzel).multilineTextAlignment(.trailing).textInputAutocapitalization(.characters)
                        .onSubmit { kalender.nachAenderung() }
                }
                ColorPicker("Farbe am Rahmen", selection: Binding(get: { Color(hex: kalender.farbe) ?? .orange }, set: { kalender.farbe = $0.hexWert; kalender.nachAenderung() }), supportsOpacity: false)
            }
            if kalender.zugriffVerweigert {
                Text("Der Zugriff auf den Kalender ist nicht erlaubt. Bitte erlaube ihn in den iOS-Einstellungen unter „Frameside“ → „Kalender“.").font(.footnote).foregroundStyle(.red)
                if let url = URL(string: UIApplication.openSettingsURLString) { Link("iOS-Einstellungen öffnen", destination: url) }
            }
            if let status = kalender.status { Text(status).font(.footnote).foregroundStyle(.secondary) }
        } header: {
            Text("Kalender auf dem Rahmen")
        } footer: {
            Text("Die Termine der nächsten Tage aus den gewählten Kalendern werden an deinen Showcase-Server geschickt; der Rahmen zeigt daraus die nächsten Termine des Tages. Gesendet wird nur, solange das hier eingeschaltet ist.")
        }
    }
}

struct KalenderAuswahlAnsicht: View {
    @ObservedObject var kalender = KalenderSync.gemeinsam
    @State private var liste: [EKCalendar] = []

    private var konten: [String] { Array(Set(liste.map { $0.source.title })).sorted() }

    var body: some View {
        List {
            ForEach(konten, id: \.self) { konto in
                Section(konto) {
                    ForEach(liste.filter { $0.source.title == konto }, id: \.calendarIdentifier) { k in
                        Toggle(isOn: Binding(get: { kalender.auswahl.contains(k.calendarIdentifier) }, set: { an in
                            if an { kalender.auswahl.insert(k.calendarIdentifier) } else { kalender.auswahl.remove(k.calendarIdentifier) }
                        })) {
                            HStack(spacing: 10) {
                                Circle().fill(Color(cgColor: k.cgColor)).frame(width: 12, height: 12)
                                Text(k.title)
                            }
                        }
                    }
                }
            }
            if liste.isEmpty { Text("Keine Kalender gefunden.").foregroundStyle(.secondary) }
        }
        .navigationTitle("Kalender auswählen")
        .onAppear { liste = kalender.kalender() }
        .onDisappear { kalender.nachAenderung() }
    }
}

extension Color {
    /// "#rrggbb" -> Farbe
    init?(hex: String) {
        guard hex.count == 7, hex.hasPrefix("#"), let v = UInt32(hex.dropFirst(), radix: 16) else { return nil }
        self.init(red: Double((v >> 16) & 255) / 255, green: Double((v >> 8) & 255) / 255, blue: Double(v & 255) / 255)
    }

    /// Farbe -> "#rrggbb"
    var hexWert: String {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        UIColor(self).getRed(&r, green: &g, blue: &b, alpha: &a)
        return String(format: "#%02x%02x%02x", Int((r * 255).rounded()), Int((g * 255).rounded()), Int((b * 255).rounded()))
    }
}
