import SwiftUI

struct WurzelAnsicht: View {
    @EnvironmentObject var modell: AppModell
    @Environment(\.scenePhase) private var phase

    var body: some View {
        ZStack {
            Color(red: 0.07, green: 0.08, blue: 0.11).ignoresSafeArea()
            if let server = modell.server {
                WebAnsicht(server: server)
                    .ignoresSafeArea(edges: .bottom)
            } else {
                EinrichtungAnsicht()
            }
            if modell.gesperrt && modell.server != nil { SperrAnsicht() }
        }
        .sheet(isPresented: $modell.einstellungenOffen) { EinstellungenAnsicht() }
        .onChange(of: phase) { _, neu in
            if neu == .background { modell.appWurdeInaktiv() }
            if neu == .active && modell.gesperrt { modell.entsperren() }
        }
    }
}

struct SperrAnsicht: View {
    @EnvironmentObject var modell: AppModell
    var body: some View {
        ZStack {
            Color(red: 0.07, green: 0.08, blue: 0.11).ignoresSafeArea()
            VStack(spacing: 18) {
                Image(systemName: "lock.fill").font(.system(size: 44)).foregroundStyle(.secondary)
                Text("Showcase Immich ist gesperrt").font(.headline)
                Button("Entsperren") { modell.entsperren() }.buttonStyle(.borderedProminent).tint(Color(red: 0.88, green: 0.70, blue: 0.35))
            }
        }
        .onAppear { modell.entsperren() }
    }
}
