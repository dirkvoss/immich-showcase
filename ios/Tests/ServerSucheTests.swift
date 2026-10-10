import XCTest
@testable import ShowcaseImmich

final class ServerSucheTests: XCTestCase {
    func testPraefixeNurPrivateNetzeOhneDoppelte() {
        XCTAssertEqual(ServerSuche.praefixe(adressen: ["192.168.1.34", "192.168.1.99", "10.0.5.7", "172.20.3.4", "8.8.8.8", "169.254.1.1", "kaputt", "300.1.1.1"]),
                       ["192.168.1.", "10.0.5.", "172.20.3."])
        XCTAssertTrue(ServerSuche.praefixe(adressen: []).isEmpty)
    }

    func testKandidatenSindAlleHostsMitBeidenPorts() {
        let u = ServerSuche.kandidaten(praefixe: ["192.168.1."])
        XCTAssertEqual(u.count, 254 * 2)
        XCTAssertTrue(u.contains(URL(string: "http://192.168.1.20:8090")!))
        XCTAssertTrue(u.contains(URL(string: "http://192.168.1.20")!))
    }

    func testShowcaseErkennung() {
        XCTAssertEqual(ServerSuche.showcaseName(Data(#"{"name":"Frameside","version":"2.14.3","modus":"beides"}"#.utf8)), "Frameside")
        XCTAssertNil(ServerSuche.showcaseName(Data(#"{"name":"Fremdgeraet"}"#.utf8)))
        XCTAssertNil(ServerSuche.showcaseName(Data("<html>".utf8)))
    }

    func testLeereAdressenSuchenNichts() async {
        let r = await ServerSuche.suchen(adressen: [])
        XCTAssertTrue(r.isEmpty)
    }

    func testPraefixAusEingabe() {
        XCTAssertEqual(ServerSuche.praefix(aus: "192.168.2"), "192.168.2.")
        XCTAssertEqual(ServerSuche.praefix(aus: " 192.168.2. "), "192.168.2.")
        XCTAssertEqual(ServerSuche.praefix(aus: "172.16.5.77"), "172.16.5.")
        XCTAssertNil(ServerSuche.praefix(aus: "8.8.8"))          // kein privates Netz
        XCTAssertNil(ServerSuche.praefix(aus: "10.10"))
        XCTAssertNil(ServerSuche.praefix(aus: "abc.def.1"))
        XCTAssertNil(ServerSuche.praefix(aus: "192.168.300"))
    }

    func testNamenKandidaten() {
        let u = ServerSuche.namenKandidaten(["showcase"])
        XCTAssertEqual(Set(u), [URL(string: "http://showcase:8090")!, URL(string: "http://showcase")!])
        XCTAssertEqual(ServerSuche.namenKandidaten().count, ServerSuche.bekannteNamen.count * 2)
    }

    func testAnmeldeartWirdGelesen() {
        let i = ServerSuche.showcaseInfo(Data(#"{"name":"S","version":"1","modus":"beides","auth":"immich"}"#.utf8))
        XCTAssertEqual(i?.auth, "immich")
        XCTAssertEqual(GefundenerServer(url: URL(string: "http://x")!, name: "S", anmeldung: "immich").anmeldungText, "Anmeldung mit Immich-Konto")
        XCTAssertNil(GefundenerServer(url: URL(string: "http://x")!, name: "S").anmeldungText)
    }

    func testBonjourUrl() {
        XCTAssertEqual(BonjourSuche.url(host: "192.168.1.20", port: 8090)?.absoluteString, "http://192.168.1.20:8090")
        XCTAssertEqual(BonjourSuche.url(host: "192.168.1.20", port: 80)?.absoluteString, "http://192.168.1.20")
        XCTAssertEqual(BonjourSuche.url(host: "192.168.1.20%en0", port: 8090)?.absoluteString, "http://192.168.1.20:8090")
        XCTAssertNil(BonjourSuche.url(host: "fe80::1", port: 8090))                     // IPv6 lassen wir weg
        XCTAssertNil(BonjourSuche.url(host: "", port: 8090))
    }

    func testVerbindungspruefungDeutetFehlerVerstaendlich() {
        XCTAssertTrue(Verbindungspruefung.deute(.timedOut).0.contains("antwortet nicht"))
        XCTAssertTrue(Verbindungspruefung.deute(.cannotFindHost).1.contains("VPN"))
        XCTAssertTrue(Verbindungspruefung.deute(.notConnectedToInternet).0.contains("nicht mit dem Netz"))
        XCTAssertTrue(Verbindungspruefung.deuteStatus(403).1.contains("Heimnetz"))
        XCTAssertTrue(Verbindungspruefung.deuteStatus(502).0.contains("502"))
        XCTAssertEqual(Verbindungspruefung.netzSchritt(erfuellt: false, wlan: false, mobil: false).stand, .fehler)
        XCTAssertEqual(Verbindungspruefung.netzSchritt(erfuellt: true, wlan: true, mobil: false).stand, .ok)
        XCTAssertEqual(Verbindungspruefung.netzSchritt(erfuellt: true, wlan: false, mobil: true).stand, .warnung)
    }

    func testPinSpeicher() throws {
        XCTAssertFalse(PinSpeicher.speichern("abc", fuer: "test.example"))                 // nur 6 Ziffern
        let ok = PinSpeicher.speichern("123456", fuer: "test.example")
        try XCTSkipUnless(ok, "Kein Schlüsselbund mit Gerätecode im Testlauf")
        XCTAssertTrue(PinSpeicher.vorhanden(fuer: "test.example"))
        PinSpeicher.loeschen(fuer: "test.example")
        XCTAssertFalse(PinSpeicher.vorhanden(fuer: "test.example"))
    }
}
