import XCTest
@testable import ShowcaseImmich

final class AdresseTests: XCTestCase {
    func testIPBekommtHttp() { XCTAssertEqual(Adresse.normalisieren("192.168.1.20:8090")?.absoluteString, "http://192.168.1.20:8090") }
    func testDomainBekommtHttps() { XCTAssertEqual(Adresse.normalisieren("showcase.example.com")?.absoluteString, "https://showcase.example.com") }
    func testLokalerNameBekommtHttp() {
        XCTAssertEqual(Adresse.normalisieren("meinserver")?.absoluteString, "http://meinserver")
        XCTAssertEqual(Adresse.normalisieren("nas.local:8090")?.absoluteString, "http://nas.local:8090")
    }
    func testSchemaUndSchraegstricheBleiben() {
        XCTAssertEqual(Adresse.normalisieren("  https://x.de/  ")?.absoluteString, "https://x.de")
        XCTAssertEqual(Adresse.normalisieren("http://192.168.1.2//")?.absoluteString, "http://192.168.1.2")
    }
    func testUnsinnWirdAbgelehnt() {
        XCTAssertNil(Adresse.normalisieren(""))
        XCTAssertNil(Adresse.normalisieren("zwei woerter"))
        XCTAssertNil(Adresse.normalisieren("ftp://x.de"))
    }
    func testVerbindungsLink() {
        let u = URL(string: "showcase://verbinden?adresse=http%3A%2F%2F192.168.1.20%3A8090")!
        XCTAssertEqual(Adresse.ausVerbindungsLink(u)?.absoluteString, "http://192.168.1.20:8090")
        XCTAssertNil(Adresse.ausVerbindungsLink(URL(string: "showcase://etwas?adresse=x")!))
        XCTAssertNil(Adresse.ausVerbindungsLink(URL(string: "https://verbinden?adresse=x")!))
    }
    func testQRText() {
        XCTAssertEqual(Adresse.ausQRText("showcase://verbinden?adresse=192.168.1.20:8090")?.absoluteString, "http://192.168.1.20:8090")
        XCTAssertEqual(Adresse.ausQRText("https://tv.example.com")?.absoluteString, "https://tv.example.com")
    }
    func testGehoertZumServer() {
        let s = URL(string: "http://192.168.1.20:8090")!
        XCTAssertTrue(Adresse.gehoertZumServer(URL(string: "http://192.168.1.20:8090/tv/")!, server: s))
        XCTAssertFalse(Adresse.gehoertZumServer(URL(string: "https://github.com/x")!, server: s))
        XCTAssertFalse(Adresse.gehoertZumServer(URL(string: "http://192.168.1.20:2283/")!, server: s))
    }
    func testKandidatenOhneSchemaProbierenBeide() {
        XCTAssertEqual(Adresse.kandidaten("bilderrahmen.example.com").map(\.absoluteString), ["https://bilderrahmen.example.com", "http://bilderrahmen.example.com"])
        XCTAssertEqual(Adresse.kandidaten("192.168.1.20:8090").map(\.absoluteString), ["http://192.168.1.20:8090", "https://192.168.1.20:8090"])
    }
    func testKandidatenMitSchemaNurEiner() {
        XCTAssertEqual(Adresse.kandidaten("https://x.de/").map(\.absoluteString), ["https://x.de"])
        XCTAssertEqual(Adresse.kandidaten("http://192.168.1.2").map(\.absoluteString), ["http://192.168.1.2"])
        XCTAssertTrue(Adresse.kandidaten("zwei woerter").isEmpty)
    }
}
