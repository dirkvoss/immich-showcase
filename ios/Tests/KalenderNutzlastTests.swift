import SwiftUI
import XCTest
@testable import ShowcaseImmich

final class KalenderNutzlastTests: XCTestCase {
    private let zone = TimeZone(identifier: "Europe/Berlin")!
    private func datum(_ s: String) -> Date {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = zone; f.dateFormat = "yyyy-MM-dd HH:mm"
        return f.date(from: s)!
    }
    private func eins(_ e: KalenderNutzlast.Eintrag, nurZeiten: Bool = false) -> [String: Any] {
        KalenderNutzlast.termine([e], nurZeiten: nurZeiten, zone: zone).first!
    }

    func testTerminMitUhrzeit() {
        let t = eins(.init(titel: "Zahnarzt", von: datum("2026-10-10 14:00"), bis: datum("2026-10-10 15:00"), ganztag: false))
        XCTAssertEqual(t["titel"] as? String, "Zahnarzt")
        XCTAssertEqual(t["von"] as? String, "2026-10-10T14:00")
        XCTAssertEqual(t["bis"] as? String, "2026-10-10T15:00")
    }

    func testGanztaegigEndetAmFolgetag() {                     // EventKit: Ende 23:59 am letzten Tag -> Server: Ende ausschließlich am Folgetag
        let t = eins(.init(titel: "Geburtstag", von: datum("2026-10-10 00:00"), bis: datum("2026-10-10 23:59"), ganztag: true))
        XCTAssertEqual(t["von"] as? String, "2026-10-10")
        XCTAssertEqual(t["bis"] as? String, "2026-10-11")
    }

    func testMehrtaegigGanztaegig() {
        let t = eins(.init(titel: "Urlaub", von: datum("2026-10-09 00:00"), bis: datum("2026-10-11 23:59"), ganztag: true))
        XCTAssertEqual(t["von"] as? String, "2026-10-09")
        XCTAssertEqual(t["bis"] as? String, "2026-10-12")
    }

    func testNurZeitenSendetKeinenTitel() {
        let t = eins(.init(titel: "Arzt wegen Rücken", von: datum("2026-10-10 09:00"), bis: datum("2026-10-10 09:30"), ganztag: false), nurZeiten: true)
        XCTAssertEqual(t["titel"] as? String, "Termin")
    }

    func testLeererTitelBekommtPlatzhalter() {
        XCTAssertEqual(eins(.init(titel: "  ", von: datum("2026-10-10 09:00"), bis: datum("2026-10-10 09:30"), ganztag: false))["titel"] as? String, "Termin")
    }

    func testEndeVorBeginnWirdBegradigt() {
        let t = eins(.init(titel: "x", von: datum("2026-10-10 10:00"), bis: datum("2026-10-10 09:00"), ganztag: false))
        XCTAssertEqual(t["bis"] as? String, "2026-10-10T10:00")
    }

    func testHoechstzahl() {
        let e = KalenderNutzlast.Eintrag(titel: "x", von: datum("2026-10-10 09:00"), bis: datum("2026-10-10 10:00"), ganztag: false)
        XCTAssertEqual(KalenderNutzlast.termine(Array(repeating: e, count: 500), nurZeiten: false, zone: zone).count, KalenderNutzlast.maximum)
    }

    func testGeburtstagWirdMarkiert() {
        let g = eins(.init(titel: "Omas Geburtstag", von: datum("2026-10-10 00:00"), bis: datum("2026-10-10 23:59"), ganztag: true, geburtstag: true))
        XCTAssertEqual(g["geburtstag"] as? Bool, true)
        XCTAssertNil(eins(.init(titel: "x", von: datum("2026-10-10 09:00"), bis: datum("2026-10-10 10:00"), ganztag: false))["geburtstag"])
    }

    func testFarbeAlsHex() {
        XCTAssertEqual(Color(hex: "#e0a24a")?.hexWert, "#e0a24a")
        XCTAssertNil(Color(hex: "rot"))
        XCTAssertNil(Color(hex: "#12345"))
    }
}
