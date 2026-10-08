import SwiftUI

struct EinrichtungAnsicht: View {
    @EnvironmentObject var modell: AppModell
    @State private var eingabe = ""
    @State private var prueft = false
    @State private var fehler: String?
    @State private var scannerOffen = false
    private let gold = Color(red: 0.88, green: 0.70, blue: 0.35)

    var body: some View {
        ScrollView {
            VStack(spacing: 22) {
                Image(systemName: "photo.on.rectangle.angled").font(.system(size: 54)).foregroundStyle(gold).padding(.top, 40)
                Text("Showcase Immich").font(.system(size: 34, weight: .semibold, design: .serif))
                Text("Verbinde die App mit deinem Immich-Showcase-Server.").foregroundStyle(.secondary).multilineTextAlignment(.center)

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

    private func verbinden() {
        guard let url = Adresse.normalisieren(eingabe) else { fehler = "Bitte eine Adresse wie 192.168.1.20:8090 eingeben."; return }
        fehler = nil; prueft = true
        Task {
            switch await modell.pruefen(url) {
            case .success: modell.serverSetzen(url)
            case .failure(let f): fehler = f.text
            }
            prueft = false
        }
    }
}
