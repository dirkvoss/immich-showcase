import WidgetKit
import SwiftUI
import AppIntents

@main
struct ShowcaseWidgetBuendel: WidgetBundle {
    var body: some Widget { RahmenWidget() }
}

struct RahmenEintrag: TimelineEntry {
    let date: Date
    let stand: ServerKlient.Stand?
    let fehler: String?
}

struct RahmenAnbieter: TimelineProvider {
    func placeholder(in context: Context) -> RahmenEintrag {
        RahmenEintrag(date: Date(), stand: .init(rahmenName: "Bilderrahmen", laeuft: "Sardinien 2026", anzahl: 296, zurueck: nil, online: true), fehler: nil)
    }
    func getSnapshot(in context: Context, completion: @escaping (RahmenEintrag) -> Void) {
        if context.isPreview { completion(placeholder(in: context)) } else { laden(completion) }
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<RahmenEintrag>) -> Void) {
        laden { e in completion(Timeline(entries: [e], policy: .after(Date().addingTimeInterval(15 * 60)))) }
    }
    private func laden(_ fertig: @escaping (RahmenEintrag) -> Void) {
        Task {
            do { fertig(RahmenEintrag(date: Date(), stand: try await ServerKlient.ausSpeicher().stand(), fehler: nil)) }
            catch { fertig(RahmenEintrag(date: Date(), stand: nil, fehler: error.localizedDescription)) }
        }
    }
}

struct RahmenWidgetAnsicht: View {
    @Environment(\.widgetFamily) private var familie
    let eintrag: RahmenEintrag
    private let gold = Color(red: 0.88, green: 0.70, blue: 0.35)

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: "photo.on.rectangle.angled").foregroundStyle(gold)
                Text(eintrag.stand?.rahmenName ?? "Bilderrahmen").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                Spacer()
                if eintrag.stand?.online == false { Image(systemName: "wifi.slash").font(.caption2).foregroundStyle(.orange) }
            }
            if let s = eintrag.stand {
                if let name = s.laeuft {
                    Text(name).font(.headline).lineLimit(2)
                    if let n = s.anzahl { Text("\(n) Fotos").font(.caption).foregroundStyle(.secondary) }
                } else {
                    Text("Normales Programm").font(.headline)
                }
                Spacer(minLength: 0)
                HStack {
                    if s.laeuft != nil { Button(intent: ShowBeendenIntent()) { Label("Beenden", systemImage: "stop.fill") }.tint(gold) }
                    if familie != .systemSmall, s.zurueck != nil { Button(intent: ZurueckIntent()) { Label("Zurück", systemImage: "arrow.uturn.backward") }.tint(.gray) }
                }
                .font(.caption).buttonStyle(.bordered)
            } else {
                Spacer(minLength: 0)
                Text(eintrag.fehler ?? "Keine Verbindung").font(.caption).foregroundStyle(.secondary).lineLimit(4)
            }
        }
        .containerBackground(Color(red: 0.07, green: 0.08, blue: 0.11), for: .widget)
    }
}

struct RahmenWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "RahmenWidget", provider: RahmenAnbieter()) { RahmenWidgetAnsicht(eintrag: $0) }
            .configurationDisplayName("Bilderrahmen")
            .description("Zeigt, was auf dem Rahmen läuft, und beendet die Show oder springt zurück.")
            .supportedFamilies([.systemSmall, .systemMedium])
    }
}
