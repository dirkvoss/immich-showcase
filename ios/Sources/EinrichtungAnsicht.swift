import SwiftUI

struct EinrichtungAnsicht: View {
    @EnvironmentObject var modell: AppModell
    @State private var eingabe = ""
    @State private var prueft = false
    @State private var fehler: String?
    @State private var scannerOffen = false
    @State private var suche: Suche = .bereit
    @State private var anderesNetz = ""
    @State private var netzHinweis: String?
    enum Suche: Equatable { case bereit, sucht([GefundenerServer]), fertig([GefundenerServer]) }
    private let gold = Color(red: 0.88, green: 0.70, blue: 0.35)

    var body: some View {
        ScrollView {
            VStack(spacing: 22) {
                Image(systemName: "photo.on.rectangle.angled").font(.system(size: 54)).foregroundStyle(gold).padding(.top, 40)
                Text("Showcase Immich").font(.system(size: 34, weight: .semibold, design: .serif))
                Text("Verbinde die App mit deinem Immich-Showcase-Server.").foregroundStyle(.secondary).multilineTextAlignment(.center)

                VStack(alignment: .leading, spacing: 8) {
                    Label("Wichtig vorab", systemImage: "info.circle.fill").font(.subheadline.weight(.semibold)).foregroundStyle(gold)
                    Text("Diese App verbindet sich **nicht direkt mit Immich**. Sie braucht einen eigenen **Immich-Showcase-Server**, den du selbst betreibst (neben deinem Immich, z. B. im Heimnetz).")
                    Text("Ohne diesen Server kann die App nichts anzeigen. Anleitung und Installation findest du auf GitHub.")
                        .foregroundStyle(.secondary)
                    Link("Immich Showcase auf GitHub", destination: URL(string: "https://github.com/dirkvoss/immich-showcase")!).foregroundStyle(gold)
                }
                .font(.footnote).frame(maxWidth: .infinity, alignment: .leading).padding(14)
                .background(.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 12))

                serverSuche

                VStack(alignment: .leading, spacing: 8) {
                    Text("Adresse des Servers").font(.footnote).foregroundStyle(.secondary)
                    TextField("192.168.1.20:8090", text: $eingabe)
                        .textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
                        .padding(14).background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
                        .onSubmit { verbinden() }
                    if let fehler { Text(fehler).font(.footnote).foregroundStyle(.red) }
                }
                Button { verbinden() } label: {
                    HStack { if prueft { ProgressView().tint(.black) }; Text("Verbinden").fontWeight(.semibold) }.frame(maxWidth: .infinity).padding(.vertical, 14)
                }.buttonStyle(.borderedProminent).tint(gold).foregroundStyle(.black).disabled(prueft || eingabe.trimmingCharacters(in: .whitespaces).isEmpty)

                Button { modell.demoStarten() } label: { Label("Demo ausprobieren (ohne Server)", systemImage: "play.circle").frame(maxWidth: .infinity).padding(.vertical, 12) }
                    .buttonStyle(.bordered).tint(gold)
                if QRScanner.verfuegbar {
                    Button { scannerOffen = true } label: { Label("QR-Code scannen", systemImage: "qrcode.viewfinder").frame(maxWidth: .infinity).padding(.vertical, 12) }
                        .buttonStyle(.bordered).tint(gold)
                }
                Text("Die Adresse und den QR-Code findest du in der Web-App unter Konto → Einstellungen → „iPhone-App verbinden“.")
                    .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center).padding(.top, 8)
            }.padding(.horizontal, 24).frame(maxWidth: 520)
        }
        .sheet(isPresented: $scannerOffen) {
            QRScanner { text in
                scannerOffen = false
                if let u = Adresse.ausQRText(text) { eingabe = u.absoluteString; verbinden() } else { fehler = "Dieser QR-Code enthält keine Server-Adresse." }
            }.ignoresSafeArea()
        }
    }

    @ViewBuilder private var serverSuche: some View {
        VStack(alignment: .leading, spacing: 10) {
            switch suche {
            case .bereit:
                HStack(spacing: 10) { ProgressView(); Text("Suche Server im WLAN …").foregroundStyle(.secondary) }
            case .sucht(let liste):
                if liste.isEmpty { HStack(spacing: 10) { ProgressView(); Text("Suche Server im WLAN …").foregroundStyle(.secondary) } }
                else { treffer(liste, laeuft: true) }
            case .fertig(let liste) where liste.isEmpty:
                Text("Im WLAN wurde kein Server gefunden. Tippe die Adresse ein oder scanne den QR-Code.").font(.footnote).foregroundStyle(.secondary)
                Button("Erneut suchen") { starteSuche() }.font(.footnote)
            case .fertig(let liste):
                treffer(liste, laeuft: false)
            }
            if case .fertig = suche { anderesNetzSuchen }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .task { if suche == .bereit { starteSuche() } }
    }

    @ViewBuilder private func treffer(_ liste: [GefundenerServer], laeuft: Bool) -> some View {
        HStack(spacing: 8) { Text("Gefunden im WLAN").font(.footnote).foregroundStyle(.secondary); if laeuft { ProgressView().controlSize(.mini) } }
        ForEach(liste) { s in
            Button { eingabe = s.url.absoluteString; verbinden() } label: {
                HStack { VStack(alignment: .leading) { Text(s.name).fontWeight(.semibold); Text(s.anzeigeAdresse).font(.footnote).foregroundStyle(.secondary) }; Spacer(); Image(systemName: "chevron.right").foregroundStyle(.secondary) }
                    .padding(12).background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
            }.buttonStyle(.plain).disabled(prueft)
        }
    }

    @ViewBuilder private var anderesNetzSuchen: some View {
        DisclosureGroup("Server in einem anderen Netz suchen") {
            VStack(alignment: .leading, spacing: 8) {
                Text("Steht der Server in einem anderen Netz (z. B. einem eigenen Server-Netz), gib dessen Anfang an, zum Beispiel 192.168.2").font(.footnote).foregroundStyle(.secondary)
                HStack {
                    TextField("192.168.2", text: $anderesNetz).textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.numbersAndPunctuation)
                        .padding(10).background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
                    Button("Suchen") {
                        if let p = ServerSuche.praefix(aus: anderesNetz) { netzHinweis = nil; starteSuche(weitere: [p]) }
                        else { netzHinweis = "Bitte ein privates Netz angeben, z. B. 192.168.2 oder 172.16.5." }
                    }.buttonStyle(.bordered).tint(gold)
                }
                if let netzHinweis { Text(netzHinweis).font(.footnote).foregroundStyle(.red) }
            }
        }
        .font(.footnote).tint(gold)
    }

    private func starteSuche(weitere: [String] = []) {
        suche = .sucht([])
        Task {
            let alle = await ServerSuche.suchen(weitere: weitere) { treffer in
                Task { @MainActor in if case .sucht(let l) = suche { suche = .sucht(l + [treffer]) } }
            }
            suche = .fertig(alle)
        }
    }

    private func verbinden() {
        let kandidaten = Adresse.kandidaten(eingabe)
        guard !kandidaten.isEmpty else { fehler = "Bitte eine Adresse wie 192.168.1.20:8090 eingeben."; return }
        fehler = nil; prueft = true
        Task {
            var letzter: AppModell.Fehler = .nichtErreichbar
            for url in kandidaten {
                switch await modell.pruefen(url) {
                case .success: modell.serverSetzen(url); prueft = false; return
                case .failure(let f): letzter = f
                }
            }
            fehler = letzter.text
            prueft = false
        }
    }
}
