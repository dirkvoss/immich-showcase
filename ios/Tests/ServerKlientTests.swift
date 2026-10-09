import XCTest
@testable import ShowcaseImmich

final class ServerKlientTests: XCTestCase {
    let basis = URL(string: "https://bilderrahmen.example.com")!

    func testSchreibendeAnfrageHatCsrfHeaderUndJSON() throws {
        let k = ServerKlient(basis: basis)
        let r = k.anfrage("POST", "normal", koerper: ["ziel": "flur"])
        XCTAssertEqual(r.url?.absoluteString, "https://bilderrahmen.example.com/api/normal")
        XCTAssertEqual(r.httpMethod, "POST")
        XCTAssertEqual(r.value(forHTTPHeaderField: "X-Rahmen"), "1")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Content-Type"), "application/json")
        XCTAssertEqual(try JSONSerialization.jsonObject(with: r.httpBody!) as? [String: String], ["ziel": "flur"])
    }

    func testSuchanfrageKodiertDenText() {
        let r = ServerKlient(basis: basis).anfrage("GET", "suche", abfrage: [URLQueryItem(name: "text", value: "Sommer 2022 & Strand")])
        XCTAssertTrue(r.url!.absoluteString.hasPrefix("https://bilderrahmen.example.com/api/suche?text=Sommer%202022"))
        XCTAssertFalse(r.url!.absoluteString.contains(" "))
    }

    func testCookieWirdNurFuerDenServerMitgeschickt() {
        let meins = HTTPCookie(properties: [.name: "rw_session", .value: "abc", .domain: "bilderrahmen.example.com", .path: "/"])!
        let fremd = HTTPCookie(properties: [.name: "x", .value: "geheim", .domain: "andere-seite.de", .path: "/"])!
        let kopf = ServerKlient.cookieKopf(aus: [meins, fremd], fuer: basis)
        XCTAssertEqual(kopf, "rw_session=abc")
        let r = ServerKlient(basis: basis, cookieKopf: kopf).anfrage("GET", "config")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Cookie"), "rw_session=abc")
        XCTAssertNil(ServerKlient(basis: basis).anfrage("GET", "config").value(forHTTPHeaderField: "Cookie"))
    }

    func testCookieDerElternDomainGilt() {
        let c = HTTPCookie(properties: [.name: "a", .value: "1", .domain: ".example.com", .path: "/"])!
        XCTAssertEqual(ServerKlient.cookieKopf(aus: [c], fuer: basis), "a=1")
    }

    func testBildWirdZuJPEG() throws {
        let png = UIGraphicsImageRenderer(size: CGSize(width: 40, height: 30)).pngData { c in UIColor.orange.setFill(); c.fill(CGRect(x: 0, y: 0, width: 40, height: 30)) }
        let jpeg = try XCTUnwrap(Bild.alsJPEG(png))
        XCTAssertEqual(Array(jpeg.prefix(3)), [0xFF, 0xD8, 0xFF])
        XCTAssertEqual(Bild.alsJPEG(jpeg), jpeg)                                  // JPEG bleibt unveraendert
        XCTAssertNil(Bild.alsJPEG(Data("kein Bild".utf8)))
    }

    func testGeteilterSpeicherSchreibenLesenLoeschen() throws {
        GeteilterSpeicher.schreiben("test-schluessel", "wert1")
        try XCTSkipIf(GeteilterSpeicher.lesen("test-schluessel") == nil, "Kein Schlüsselbund im unsignierten Testlauf")
        XCTAssertEqual(GeteilterSpeicher.lesen("test-schluessel"), "wert1")
        GeteilterSpeicher.schreiben("test-schluessel", "wert2")
        XCTAssertEqual(GeteilterSpeicher.lesen("test-schluessel"), "wert2")
        GeteilterSpeicher.schreiben("test-schluessel", nil)
        XCTAssertNil(GeteilterSpeicher.lesen("test-schluessel"))
    }

    func testFehlerTexteSindVerstaendlich() {
        XCTAssertTrue(ServerKlient.KlientFehler.keinServer.errorDescription!.contains("Server"))
        XCTAssertTrue(ServerKlient.KlientFehler.anmeldungNoetig.errorDescription!.contains("PIN"))
    }
}
