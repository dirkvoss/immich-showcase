import Foundation
import UIKit

enum DemoOrt: CaseIterable {
    case sardinien, alpen, nordsee, lissabon
    var land: String { switch self { case .sardinien: return "Italy"; case .alpen: return "Austria"; case .nordsee: return "Germany"; case .lissabon: return "Portugal" } }
    var landDE: String { switch self { case .sardinien: return "Italien"; case .alpen: return "Österreich"; case .nordsee: return "Deutschland"; case .lissabon: return "Portugal" } }
    var stichworte: [String] {
        switch self {
        case .sardinien: return ["sardinien", "italien", "strand", "meer", "sommer"]
        case .alpen: return ["alpen", "österreich", "oesterreich", "berge", "winter", "wandern"]
        case .nordsee: return ["nordsee", "deutschland", "strand", "meer", "dünen"]
        case .lissabon: return ["lissabon", "portugal", "stadt", "abend"]
        }
    }
    struct Palette { let oben, mitte, unten, sonne: UIColor }
    var palette: Palette {
        switch self {
        case .sardinien: return .init(oben: DemoBild.farbe(0.18, 0.36, 0.62), mitte: DemoBild.farbe(0.93, 0.65, 0.42), unten: DemoBild.farbe(0.99, 0.88, 0.69), sonne: DemoBild.farbe(1, 0.95, 0.80))
        case .alpen: return .init(oben: DemoBild.farbe(0.25, 0.45, 0.78), mitte: DemoBild.farbe(0.62, 0.78, 0.95), unten: DemoBild.farbe(0.95, 0.97, 1.0), sonne: DemoBild.farbe(1, 1, 0.92))
        case .nordsee: return .init(oben: DemoBild.farbe(0.42, 0.52, 0.64), mitte: DemoBild.farbe(0.74, 0.79, 0.82), unten: DemoBild.farbe(0.92, 0.90, 0.84), sonne: DemoBild.farbe(1, 0.98, 0.90))
        case .lissabon: return .init(oben: DemoBild.farbe(0.28, 0.20, 0.45), mitte: DemoBild.farbe(0.95, 0.50, 0.40), unten: DemoBild.farbe(1.0, 0.80, 0.50), sonne: DemoBild.farbe(1, 0.92, 0.70))
        }
    }
}

struct DemoFoto {
    let index: Int
    var id: String { String(format: "demo-%04d", index) }
    /// 12 „Reisen“ mit je 3 Fotos am selben Tag: gleicher Ort, gleiches Datum.
    private var reise: Int { index / 3 }
    var ort: DemoOrt { DemoOrt.allCases[reise % 4] }
    var jahr: Int { 2021 + reise * 5 / 12 }
    var tag: String { String(format: "%04d-%02d-%02d", jahr, 1 + (reise * 5) % 12, 3 + (reise * 7) % 24) }
    var personen: [String] { index % 2 == 0 ? (index % 3 == 0 ? ["Anna Beispiel", "Opa Karl"] : ["Anna Beispiel"]) : [] }
    var favorit: Bool { index % 5 == 0 }
    var json: [String: Any] { ["id": id, "tag": tag, "fav": favorit] }
}

enum DemoDaten {
    static let anzahl = 36
    /// Neueste zuerst.
    static let alle: [DemoFoto] = (0..<anzahl).map { DemoFoto(index: $0) }.sorted { $0.tag > $1.tag }
    static func foto(id: String) -> DemoFoto? { alle.first { $0.id == id } }
    static let personen = ["Anna Beispiel", "Opa Karl"]
}
