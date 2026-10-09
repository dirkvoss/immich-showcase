import Foundation
import LocalAuthentication
import Security

/// Merkt die PIN des Servers im Schlüsselbund, geschützt durch Face ID bzw. den Gerätecode (nur wenn der Nutzer es in den App-Einstellungen eingeschaltet hat).
enum PinSpeicher {
    private static let dienst = "showcase-pin"

    @discardableResult
    static func speichern(_ pin: String, fuer host: String) -> Bool {
        loeschen(fuer: host)
        guard pin.range(of: #"^\d{6}$"#, options: .regularExpression) != nil,
              let schutz = SecAccessControlCreateWithFlags(nil, kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly, .userPresence, nil) else { return false }
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: dienst, kSecAttrAccount as String: host,
                                kSecValueData as String: Data(pin.utf8), kSecAttrAccessControl as String: schutz]
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }

    static func vorhanden(fuer host: String) -> Bool {
        let k = LAContext(); k.interactionNotAllowed = true
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: dienst, kSecAttrAccount as String: host, kSecUseAuthenticationContext as String: k]
        let st = SecItemCopyMatching(q as CFDictionary, nil)
        return st == errSecSuccess || st == errSecInteractionNotAllowed
    }

    /// Holt die PIN; dabei fragt iOS nach Face ID oder dem Gerätecode.
    static func holen(fuer host: String, grund: String) async -> String? {
        await withCheckedContinuation { c in
            DispatchQueue.global().async {
                let k = LAContext(); k.localizedReason = grund
                let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: dienst, kSecAttrAccount as String: host,
                                        kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne, kSecUseAuthenticationContext as String: k]
                var r: AnyObject?
                guard SecItemCopyMatching(q as CFDictionary, &r) == errSecSuccess, let d = r as? Data else { c.resume(returning: nil); return }
                c.resume(returning: String(data: d, encoding: .utf8))
            }
        }
    }

    static func loeschen(fuer host: String) {
        SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: dienst, kSecAttrAccount as String: host] as CFDictionary)
    }
}
