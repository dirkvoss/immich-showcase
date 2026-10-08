import SwiftUI
import VisionKit

/// Liest einen QR-Code mit der Kamera (nur auf Geräten mit Kamera; im Simulator nicht verfügbar).
struct QRScanner: UIViewControllerRepresentable {
    let gefunden: (String) -> Void

    static var verfuegbar: Bool { DataScannerViewController.isSupported && DataScannerViewController.isAvailable }

    func makeCoordinator() -> Koordinator { Koordinator(gefunden) }
    func makeUIViewController(context: Context) -> DataScannerViewController {
        let c = DataScannerViewController(recognizedDataTypes: [.barcode(symbologies: [.qr])], qualityLevel: .balanced, isHighlightingEnabled: true)
        c.delegate = context.coordinator
        try? c.startScanning()
        return c
    }
    func updateUIViewController(_ c: DataScannerViewController, context: Context) {}

    final class Koordinator: NSObject, DataScannerViewControllerDelegate {
        let gefunden: (String) -> Void
        var erledigt = false
        init(_ g: @escaping (String) -> Void) { gefunden = g }
        func dataScanner(_ s: DataScannerViewController, didAdd items: [RecognizedItem], allItems: [RecognizedItem]) {
            guard !erledigt else { return }
            for case .barcode(let b) in items { if let t = b.payloadStringValue { erledigt = true; gefunden(t); return } }
        }
    }
}
