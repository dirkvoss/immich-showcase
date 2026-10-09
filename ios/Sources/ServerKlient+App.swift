import Foundation
import WebKit

extension ServerKlient {
    /// Im Hauptprogramm: Anmeldung (Cookie) aus dem Speicher der Web-Ansicht.
    @MainActor static func erstellen() async throws -> ServerKlient {
        guard let basis = gespeicherterServer() ?? GeteilterSpeicher.lesen("server").flatMap(Adresse.normalisieren) else { throw KlientFehler.keinServer }
        let alle = await WKWebsiteDataStore.default().httpCookieStore.allCookies()
        return ServerKlient(basis: basis, cookieKopf: cookieKopf(aus: alle, fuer: basis) ?? GeteilterSpeicher.lesen("cookie"))
    }

    /// Legt Server und Anmeldung im gemeinsamen Speicher ab, damit Teilen-Erweiterung und Widget sie nutzen können.
    @MainActor static func fuerErweiterungenSichern(server: URL?) async {
        GeteilterSpeicher.schreiben("server", server?.absoluteString)
        guard let server else { GeteilterSpeicher.schreiben("cookie", nil); return }
        let alle = await WKWebsiteDataStore.default().httpCookieStore.allCookies()
        GeteilterSpeicher.schreiben("cookie", cookieKopf(aus: alle, fuer: server))
    }
}
