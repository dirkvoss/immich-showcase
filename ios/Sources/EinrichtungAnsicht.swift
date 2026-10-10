import SwiftUI

struct EinrichtungAnsicht: View {
    @EnvironmentObject var modell: AppModell
    @State private var eingabe = ""
    @State private var prueft = false
    @State private var fehler: String?
    @State private var scannerOffen = false
    @State private var suche: Suche = .bereit
    @State private var gefundene: [GefundenerServer] = []
    @State private var bonjour = BonjourSuche()
    @State private var anderesNetz = ""
    @State private var netzHinweis: String?
    enum Suche: Equatable { case bereit, sucht, fertig }
    private let gold = Color(red: 0.88, green: 0.70, blue: 0.35)

    var body: some View {
        ScrollView {
            VStack(spacing: 22) {
                Image(systemName: "photo.on.rectangle.angled").font(.system(size: 54)).foregroundStyle(gold).padding(.top, 40)
                Text("Frameside").font(.system(size: 34, weight: .semibold, design: .serif))
                Text("Verbinde die App mit deinem Frameside-Server.").foregroundStyle(.secondary).multilineTextAlignment(.center)

                VStack(alignment: .leading, spacing: 8) {
                    Label("Wichtig vorab", systemImage: "info.circle.fill").font(.subheadline.weight(.semibold)).foregroundStyle(gold)
                    Text("Diese App verbindet sich **nicht direkt mit Immich**. Sie braucht einen eigenen **Frameside-Server**, den du selbst betreibst (neben deinem Immich, z. B. im Heimnetz).")
                    Text("Ohne diesen Server kann die App nichts anzeigen. Anleitung und Installation findest du auf GitHub.")
                        .foregroundStyle(.secondary)
                    Link("Frameside auf GitHub", destination: URL(string: "https://github.com/dirkvoss/frameside")!).foregroundStyle(gold)
                }
                .font(.footnote).frame(maxWidth: .infinity, alignment: .leading).padding(14)
                .background(.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 12))

                zuletzt
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
                VStack(alignment: .leading, spacing: 8) {
                    Label("So kommst du an den QR-Code", systemImage: "qrcode").font(.subheadline.weight(.semibold)).foregroundStyle(gold)
                    schritt("1", "Öffne die Showcase-Seite deines Servers am Computer oder in einem Browser, zum Beispiel unter der Adresse, die du auch hier eintippen würdest (192.168.1.20:8090).")
                    schritt("2", "Tippe oben rechts auf das **Konto-Symbol** (Person) und wähle **Einstellungen**.")
                    schritt("3", "Ganz unten steht **„iPhone-App verbinden“** mit einem QR-Code.")
                    schritt("4", "Tippe hier auf **QR-Code scannen** und halte die Kamera auf diesen Code. Fertig.")
                    Text("Den Code findest du auch am Ende der Einrichtung des Servers (Seite „/setup/“). Er enthält nur die Adresse, keine PIN und kein Passwort.")
                        .font(.footnote).foregroundStyle(.secondary).padding(.top, 2)
                }
                .font(.footnote).frame(maxWidth: .infinity, alignment: .leading).padding(14)
                .background(.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 12)).padding(.top, 8)
            }.padding(.horizontal, 24).frame(maxWidth: 520)
        }
        .sheet(isPresented: $scannerOffen) {
            QRScanner { text in
                scannerOffen = false
                if let u = Adresse.ausQRText(text) { eingabe = u.absoluteString; verbinden() } else { fehler = L("Dieser QR-Code enthält keine Server-Adresse.") }
            }.ignoresSafeArea()
        }
    }

    @ViewBuilder private var serverSuche: some View {
        VStack(alignment: .leading, spacing: 10) {
            if !gefundene.isEmpty {
                treffer(gefundene, laeuft: suche != .fertig)
            } else if suche != .fertig {
                HStack(spacing: 10) { ProgressView(); Text("Suche Server im WLAN …").foregroundStyle(.secondary) }
            } else {
                Text("Im WLAN wurde kein Server gefunden. Tippe die Adresse ein oder scanne den QR-Code.").font(.footnote).foregroundStyle(.secondary)
                Button("Erneut suchen") { starteSuche() }.font(.footnote)
            }
            if suche == .fertig { anderesNetzSuchen }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .task { if suche == .bereit { starteSuche() } }
        .onDisappear { bonjour.stop() }
    }

    @ViewBuilder private func treffer(_ liste: [GefundenerServer], laeuft: Bool) -> some View {
        let einziger = liste.count == 1 && !laeuft                       // genau ein Server und die Suche ist durch: mit einem Tipp verbinden
        HStack(spacing: 8) {
            Text(einziger ? "Dein Server wurde gefunden" : "Gefunden im WLAN").font(.footnote).foregroundStyle(einziger ? gold : .secondary)
            if laeuft { ProgressView().controlSize(.mini) }
        }
        ForEach(liste) { s in
            Button { eingabe = s.url.absoluteString; verbinden() } label: {
                HStack {
                    VStack(alignment: .leading) {
                        Text(s.name).fontWeight(.semibold)
                        Text(s.anzeigeAdresse).font(.footnote).foregroundStyle(.secondary)
                        if let a = s.anmeldungText { Text(a).font(.caption).foregroundStyle(.secondary) }
                    }
                    Spacer()
                    if einziger { Text("Verbinden").font(.subheadline.weight(.semibold)).foregroundStyle(.black).padding(.horizontal, 14).padding(.vertical, 8).background(gold, in: Capsule()) }
                    else { Image(systemName: "chevron.right").foregroundStyle(.secondary) }
                }
                .padding(12).background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(einziger ? gold : .clear, lineWidth: 1.5))
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
                        else { netzHinweis = L("Bitte ein privates Netz angeben, z. B. 192.168.2 oder 172.16.5.") }
                    }.buttonStyle(.bordered).tint(gold)
                }
                if let netzHinweis { Text(netzHinweis).font(.footnote).foregroundStyle(.red) }
            }
        }
        .font(.footnote).tint(gold)
    }

    @ViewBuilder private var zuletzt: some View {
        if let u = Adresse.normalisieren(modell.letzterServer) {
            Button { eingabe = u.absoluteString; verbinden() } label: {
                HStack { Image(systemName: "clock.arrow.circlepath").foregroundStyle(gold)
                    VStack(alignment: .leading) { Text("Zuletzt verbunden").font(.footnote).foregroundStyle(.secondary); Text(u.host.map { $0 + (u.port.map { ":\($0)" } ?? "") } ?? u.absoluteString).fontWeight(.semibold) }
                    Spacer(); Image(systemName: "chevron.right").foregroundStyle(.secondary) }
                    .padding(12).background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
            }.buttonStyle(.plain).disabled(prueft)
        }
    }

    private func schritt(_ nr: String, _ text: LocalizedStringKey) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text(nr).font(.caption.weight(.bold)).foregroundStyle(.black).frame(width: 20, height: 20).background(gold, in: Circle())
            Text(text).foregroundStyle(.primary)
        }
    }

    private func trefferHinzu(_ s: GefundenerServer) {
        if !gefundene.contains(where: { $0.url == s.url }) { gefundene.append(s); gefundene.sort { $0.anzeigeAdresse.localizedStandardCompare($1.anzeigeAdresse) == .orderedAscending } }
    }

    private func starteSuche(weitere: [String] = []) {
        suche = .sucht
        if weitere.isEmpty {
            gefundene = []
            bonjour.start { url in                                          // Server, die sich per Bonjour melden (auch aus anderen Netzen, wenn der Router weiterleitet)
                Task { if let s = await ServerSuche.bestaetige(url) { await MainActor.run { trefferHinzu(s) } } }
            }
        }
        Task {
            _ = await ServerSuche.suchen(weitere: weitere) { s in Task { @MainActor in trefferHinzu(s) } }
            suche = .fertig
        }
    }

    private func verbinden() {
        let kandidaten = Adresse.kandidaten(eingabe)
        guard !kandidaten.isEmpty else { fehler = L("Bitte eine Adresse wie 192.168.1.20:8090 eingeben."); return }
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
