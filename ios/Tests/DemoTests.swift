import XCTest
@testable import ShowcaseImmich

final class DemoTests: XCTestCase {
    private func get(_ api: DemoAPI, _ pfad: String, _ q: [String: String] = [:]) -> [String: Any] {
        let a = api.antwort(methode: "GET", pfad: pfad, abfrage: q, koerper: [:])
        return (try? JSONSerialization.jsonObject(with: a.daten)) as? [String: Any] ?? [:]
    }
    private func post(_ api: DemoAPI, _ pfad: String, _ k: [String: Any] = [:]) -> (Int, [String: Any]) {
        let a = api.antwort(methode: "POST", pfad: pfad, abfrage: [:], koerper: k)
        return (a.status, (try? JSONSerialization.jsonObject(with: a.daten)) as? [String: Any] ?? [:])
    }

    func testKonfigIstDemoUndNurRahmen() {
        let k = get(DemoAPI(), "/api/config")
        XCTAssertEqual(k["demo"] as? Bool, true)
        XCTAssertEqual(k["modus"] as? String, "rahmen")
        XCTAssertEqual(k["rahmen"] as? [String], ["rahmen"])
        XCTAssertEqual(k["hochladen"] as? Bool, false)
        XCTAssertEqual(get(DemoAPI(), "/api/me")["angemeldet"] as? Bool, true)
    }

    func testFotosGruppiertUndAbsteigendSortiert() {
        let f = get(DemoAPI(), "/api/neueste")["fotos"] as? [[String: Any]] ?? []
        XCTAssertEqual(f.count, DemoDaten.anzahl)
        let tage = f.compactMap { $0["tag"] as? String }
        XCTAssertEqual(tage, tage.sorted(by: >))
        XCTAssertLessThan(Set(tage).count, f.count)                   // mehrere Fotos pro Tag
    }

    func testFilterUndFacetten() {
        let api = DemoAPI()
        let italien = get(api, "/api/neueste", ["ort": "Italy"])["fotos"] as? [[String: Any]] ?? []
        XCTAssertFalse(italien.isEmpty)
        XCTAssertTrue(italien.allSatisfy { DemoDaten.foto(id: $0["id"] as! String)?.ort == .sardinien })
        let fa = get(api, "/api/facetten")
        XCTAssertEqual(fa["gesamt"] as? Int, DemoDaten.anzahl)
        XCTAssertEqual((fa["laender"] as? [[String: Any]])?.count, 4)
        XCTAssertEqual((fa["personen"] as? [[String: Any]])?.count, 2)
        XCTAssertFalse((fa["jahre"] as? [[String: Any]] ?? []).isEmpty)
    }

    func testSuche() {
        let api = DemoAPI()
        let a = get(api, "/api/suche", ["text": "Sardinien 2022"])
        let f = a["fotos"] as? [[String: Any]] ?? []
        XCTAssertTrue(f.allSatisfy { DemoDaten.foto(id: $0["id"] as! String)?.ort == .sardinien && ($0["tag"] as! String).hasPrefix("2022") })
        XCTAssertEqual(get(api, "/api/suche", ["text": ""])["ok"] as? Bool, false)
        XCTAssertEqual((get(api, "/api/suche", ["text": "irgendwas"])["fotos"] as? [Any])?.count, DemoDaten.anzahl)    // unbekannter Text: alle, mit Hinweis
    }

    func testVorschauLiefertJPEG() {
        let api = DemoAPI()
        let a = api.antwort(methode: "GET", pfad: "/api/vorschau/\(DemoDaten.alle[0].id)", abfrage: [:], koerper: [:])
        XCTAssertEqual(a.mime, "image/jpeg")
        XCTAssertEqual(Array(a.daten.prefix(3)), [0xFF, 0xD8, 0xFF])
        XCTAssertEqual(api.antwort(methode: "GET", pfad: "/api/vorschau/gibtsnicht", abfrage: [:], koerper: [:]).status, 404)
    }

    func testAnzeigenStatusNormalZurueck() {
        let api = DemoAPI()
        let ids = DemoDaten.alle.prefix(5).map(\.id)
        let (code, a) = post(api, "/api/anzeigen", ["name": "meine reise", "ids": ids, "speichern": true])
        XCTAssertEqual(code, 200)
        XCTAssertTrue((a["nachricht"] as? String ?? "").contains("Demo"))
        XCTAssertEqual(get(api, "/api/status")["laeuft"] as? String, "meine reise")
        let shows = get(api, "/api/shows")["shows"] as? [[String: Any]] ?? []
        XCTAssertEqual(shows.first?["name"] as? String, "meine reise")
        XCTAssertEqual(shows.first?["laeuft"] as? Bool, true)

        XCTAssertEqual(post(api, "/api/normal").0, 200)
        XCTAssertTrue(get(api, "/api/status")["laeuft"] is NSNull)
        XCTAssertEqual(post(api, "/api/zurueck").0, 200)                           // zurueck zur Show
        XCTAssertEqual(get(api, "/api/status")["laeuft"] as? String, "meine reise")
    }

    func testAnzeigenPruefungen() {
        let api = DemoAPI()
        XCTAssertEqual(post(api, "/api/anzeigen", ["name": "", "ids": ["demo-0001"]]).0, 400)
        XCTAssertEqual(post(api, "/api/anzeigen", ["name": "x", "ids": ["fremd"]]).0, 400)
        XCTAssertEqual(post(api, "/api/zurueck").0, 404)                           // noch nichts da
        XCTAssertEqual(post(api, "/api/tv/video").0, 404)                          // nicht in der Demo
    }

    func testOberflaecheLiegtImPaket() {
        let a = DemoServer.datei("/")
        XCTAssertEqual(a.status, 200)
        XCTAssertTrue(String(data: a.daten, encoding: .utf8)?.contains("Immich Showcase") ?? false)
        XCTAssertEqual(DemoServer.datei("/i18n/en.json").status, 200)
        XCTAssertEqual(DemoServer.datei("/../Info.plist").status, 400)
    }
}
