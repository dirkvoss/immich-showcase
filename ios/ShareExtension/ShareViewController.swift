import UIKit
import SwiftUI
import UniformTypeIdentifiers

/// „Teilen“ in der Fotos-App: die gewählten Fotos gehen zum Showcase-Server (und damit nach Immich) und laufen dann auf dem Rahmen.
final class ShareViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()
        let modell = TeilenModell(kontext: extensionContext)
        let host = UIHostingController(rootView: TeilenAnsicht(modell: modell).preferredColorScheme(.dark))
        addChild(host)
        view.addSubview(host.view)
        host.view.frame = view.bounds
        host.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        host.didMove(toParent: self)
        modell.starten()
    }
}

@MainActor
final class TeilenModell: ObservableObject {
    enum Zustand: Equatable {
        case laedt
        case waehleRahmen([String], [String: String])          // Ids und Namen
        case sendet(Int, Int)
        case fertig(String)
        case fehler(String)
    }

    @Published var zustand: Zustand = .laedt
    private let kontext: NSExtensionContext?
    private var klient: ServerKlient?
    private var anbieter: [NSItemProvider] = []

    init(kontext: NSExtensionContext?) { self.kontext = kontext }

    func starten() {
        anbieter = (kontext?.inputItems as? [NSExtensionItem] ?? []).flatMap { $0.attachments ?? [] }.filter { $0.hasItemConformingToTypeIdentifier(UTType.image.identifier) }
        guard !anbieter.isEmpty else { zustand = .fehler("Es wurden keine Fotos übergeben."); return }
        Task {
            do {
                let k = try ServerKlient.ausSpeicher()
                klient = k
                let rahmen = try await k.rahmen()
                if rahmen.count > 1 { zustand = .waehleRahmen(rahmen.map(\.id), Dictionary(uniqueKeysWithValues: rahmen.map { ($0.id, $0.name) })) }
                else { await senden(an: rahmen.first?.id) }
            } catch { zustand = .fehler(error.localizedDescription) }
        }
    }

    func waehle(_ rahmen: String) { Task { await senden(an: rahmen) } }
    func schliessen() { kontext?.completeRequest(returningItems: nil) }

    private func daten(_ p: NSItemProvider) async -> Data? {
        await withCheckedContinuation { c in
            p.loadDataRepresentation(forTypeIdentifier: UTType.image.identifier) { d, _ in c.resume(returning: d) }
        }
    }

    private func senden(an rahmen: String?) async {
        guard let klient else { return }
        var ids: [String] = [], letzterFehler = "", fehlgeschlagen = 0
        for (i, p) in anbieter.enumerated() {
            zustand = .sendet(i + 1, anbieter.count)
            guard let roh = await daten(p), let jpeg = Bild.alsJPEG(roh) else { fehlgeschlagen += 1; letzterFehler = "Ein Foto ließ sich nicht lesen."; continue }
            do { ids.append(try await klient.hochladen(jpeg, name: p.suggestedName ?? "Foto")) }
            catch { fehlgeschlagen += 1; letzterFehler = error.localizedDescription }
        }
        guard !ids.isEmpty else { zustand = .fehler(letzterFehler.isEmpty ? "Es konnte kein Foto gesendet werden." : letzterFehler); return }
        do {
            let datum = Date().formatted(.dateTime.day().month(.wide).locale(Locale(identifier: "de_DE")))
            let text = try await klient.anzeigen(name: "Geteilt \(datum)", ids: ids, rahmen: rahmen)
            zustand = .fertig(text + (fehlgeschlagen > 0 ? " \(fehlgeschlagen) Foto(s) konnten nicht gesendet werden: \(letzterFehler)" : ""))
            try? await Task.sleep(nanoseconds: 2_500_000_000)
            if fehlgeschlagen == 0 { schliessen() }
        } catch { zustand = .fehler(error.localizedDescription) }
    }
}

struct TeilenAnsicht: View {
    @ObservedObject var modell: TeilenModell
    private let gold = Color(red: 0.88, green: 0.70, blue: 0.35)

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "photo.on.rectangle.angled").font(.system(size: 40)).foregroundStyle(gold)
            switch modell.zustand {
            case .laedt:
                ProgressView()
                Text("Verbinde mit dem Server …").foregroundStyle(.secondary)
            case .waehleRahmen(let ids, let namen):
                Text("Auf welchen Rahmen?").font(.headline)
                ForEach(ids, id: \.self) { id in
                    Button(namen[id] ?? id) { modell.waehle(id) }.buttonStyle(.borderedProminent).tint(gold).foregroundStyle(.black)
                }
            case .sendet(let i, let n):
                ProgressView()
                Text("Foto \(i) von \(n) wird gesendet …").foregroundStyle(.secondary)
            case .fertig(let text):
                Image(systemName: "checkmark.circle.fill").font(.system(size: 36)).foregroundStyle(.green)
                Text(text).multilineTextAlignment(.center)
                Button("Fertig") { modell.schliessen() }.buttonStyle(.bordered)
            case .fehler(let text):
                Image(systemName: "exclamationmark.triangle.fill").font(.system(size: 34)).foregroundStyle(.orange)
                Text(text).multilineTextAlignment(.center)
                Button("Schließen") { modell.schliessen() }.buttonStyle(.bordered)
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(red: 0.07, green: 0.08, blue: 0.11))
    }
}
