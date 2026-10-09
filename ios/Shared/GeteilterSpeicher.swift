import Foundation
import Security

/// Kleiner gemeinsamer Speicher (Schlüsselbund-Gruppe) für App, Teilen-Erweiterung und Widget: Server-Adresse und Anmelde-Cookie.
/// Ohne Signierung (Tests im Simulator) gibt es keine Gruppe – dann wird der normale Schlüsselbund der App benutzt.
enum GeteilterSpeicher {
    static let dienst = "showcase-immich"

    static var gruppe: String? {
        guard let g = Bundle.main.object(forInfoDictionaryKey: "KeychainGruppe") as? String, !g.isEmpty, !g.hasPrefix(".") else { return nil }
        return g
    }

    private static func abfrage(_ schluessel: String, mitGruppe: Bool) -> [String: Any] {
        var q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: dienst, kSecAttrAccount as String: schluessel]
        if mitGruppe, let g = gruppe { q[kSecAttrAccessGroup as String] = g }
        return q
    }

    static func lesen(_ schluessel: String) -> String? {
        for mit in [true, false] where mit == false || gruppe != nil {
            var q = abfrage(schluessel, mitGruppe: mit)
            q[kSecReturnData as String] = true
            q[kSecMatchLimit as String] = kSecMatchLimitOne
            var ergebnis: AnyObject?
            if SecItemCopyMatching(q as CFDictionary, &ergebnis) == errSecSuccess, let d = ergebnis as? Data, let s = String(data: d, encoding: .utf8) { return s }
        }
        return nil
    }

    static func schreiben(_ schluessel: String, _ wert: String?) {
        for mit in [true, false] where mit == false || gruppe != nil { SecItemDelete(abfrage(schluessel, mitGruppe: mit) as CFDictionary) }
        guard let wert, let daten = wert.data(using: .utf8) else { return }
        var q = abfrage(schluessel, mitGruppe: true)
        q[kSecValueData as String] = daten
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        if SecItemAdd(q as CFDictionary, nil) != errSecSuccess {
            q = abfrage(schluessel, mitGruppe: false)                                   // ohne Gruppe (unsignierter Lauf)
            q[kSecValueData as String] = daten
            q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
            SecItemAdd(q as CFDictionary, nil)
        }
    }
}
