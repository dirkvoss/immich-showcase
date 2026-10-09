import Foundation
import ImageIO

enum Bild {
    /// Macht aus HEIC, PNG & Co. ein JPEG (wie es der Server und Immich überall lesen können); Aufnahmedatum, Ort und Drehung bleiben erhalten.
    /// JPEG bleibt unverändert. Nil, wenn die Daten kein Bild sind.
    static func alsJPEG(_ daten: Data, qualitaet: Double = 0.92) -> Data? {
        guard let quelle = CGImageSourceCreateWithData(daten as CFData, nil), let typ = CGImageSourceGetType(quelle) else { return nil }
        if (typ as String) == "public.jpeg" { return daten }
        let ziel = NSMutableData()
        guard let ausgabe = CGImageDestinationCreateWithData(ziel, "public.jpeg" as CFString, 1, nil) else { return nil }
        CGImageDestinationAddImageFromSource(ausgabe, quelle, 0, [kCGImageDestinationLossyCompressionQuality: qualitaet] as CFDictionary)
        return CGImageDestinationFinalize(ausgabe) ? ziel as Data : nil
    }
}
