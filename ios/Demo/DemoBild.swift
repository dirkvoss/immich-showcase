import UIKit

/// Erfundene Beispielfotos für den Demo-Modus: gemalte Landschaften (keine echten Fotos, keine Rechte Dritter).
enum DemoBild {
    struct Zufall {
        var z: UInt64
        init(_ seed: Int) { z = UInt64(truncatingIfNeeded: seed &* 2654435761 &+ 97) }
        mutating func naechste() -> CGFloat {
            z = z &* 6364136223846793005 &+ 1442695040888963407
            return CGFloat((z >> 33) & 0xFFFFFF) / CGFloat(0xFFFFFF)
        }
    }

    static func farbe(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> UIColor { UIColor(red: r, green: g, blue: b, alpha: a) }

    /// JPEG-Daten, 4:3, `breite` Pixel breit.
    static func jpeg(_ foto: DemoFoto, breite: Int) -> Data {
        zeichne(foto, breite: CGFloat(breite)).jpegData(compressionQuality: 0.82) ?? Data()
    }

    static func zeichne(_ foto: DemoFoto, breite: CGFloat) -> UIImage {
        let hoehe = (breite * 0.75).rounded()
        let format = UIGraphicsImageRendererFormat(); format.scale = 1; format.opaque = true
        return UIGraphicsImageRenderer(size: CGSize(width: breite, height: hoehe), format: format).image { c in
            let ctx = c.cgContext
            var rnd = Zufall(foto.index)
            let pal = foto.ort.palette
            let verschiebung = CGFloat(foto.index % 3) * 0.04
            // Himmel
            let farben = [pal.oben, pal.mitte, pal.unten].map { $0.cgColor } as CFArray
            let verlauf = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: farben, locations: [0, 0.55 + verschiebung, 1])!
            ctx.drawLinearGradient(verlauf, start: .zero, end: CGPoint(x: 0, y: hoehe * 0.8), options: [.drawsAfterEndLocation])
            // Sonne bzw. Mond mit Schein
            let sx = breite * (0.2 + 0.6 * rnd.naechste()), sy = hoehe * (0.22 + 0.2 * rnd.naechste()), sr = breite * 0.07
            for (faktor, alpha) in [(3.2, 0.10), (2.0, 0.18), (1.0, 0.95)] as [(CGFloat, CGFloat)] {
                ctx.setFillColor(pal.sonne.withAlphaComponent(alpha).cgColor)
                ctx.fillEllipse(in: CGRect(x: sx - sr * faktor, y: sy - sr * faktor, width: sr * 2 * faktor, height: sr * 2 * faktor))
            }
            // Landschaft je nach Ort
            switch foto.ort {
            case .alpen:
                kamm(ctx, breite, hoehe, basis: 0.62, amp: 0.30, stufen: 7, farbe: farbe(0.45, 0.55, 0.70), &rnd, schnee: true)
                kamm(ctx, breite, hoehe, basis: 0.74, amp: 0.18, stufen: 9, farbe: farbe(0.25, 0.38, 0.48), &rnd, schnee: false)
                kamm(ctx, breite, hoehe, basis: 0.88, amp: 0.10, stufen: 12, farbe: farbe(0.13, 0.25, 0.22), &rnd, schnee: false)
            case .sardinien:
                kamm(ctx, breite, hoehe, basis: 0.60, amp: 0.14, stufen: 6, farbe: farbe(0.55, 0.38, 0.30), &rnd, schnee: false)
                meer(ctx, breite, hoehe, von: 0.66, farbe: farbe(0.10, 0.45, 0.58), glanz: pal.sonne, sx: sx)
                kamm(ctx, breite, hoehe, basis: 0.93, amp: 0.07, stufen: 10, farbe: farbe(0.86, 0.74, 0.55), &rnd, schnee: false)
            case .nordsee:
                meer(ctx, breite, hoehe, von: 0.55, farbe: farbe(0.30, 0.45, 0.52), glanz: pal.sonne, sx: sx)
                kamm(ctx, breite, hoehe, basis: 0.86, amp: 0.08, stufen: 8, farbe: farbe(0.78, 0.72, 0.58), &rnd, schnee: false)
                kamm(ctx, breite, hoehe, basis: 0.96, amp: 0.05, stufen: 14, farbe: farbe(0.45, 0.50, 0.30), &rnd, schnee: false)
            case .lissabon:
                haeuser(ctx, breite, hoehe, basis: 0.72, farbe: farbe(0.20, 0.12, 0.28), &rnd, hoch: 0.30)
                haeuser(ctx, breite, hoehe, basis: 0.90, farbe: farbe(0.10, 0.06, 0.16), &rnd, hoch: 0.22)
            }
            // sanfter Rand (Vignette)
            let rand = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: [UIColor.clear.cgColor, UIColor.black.withAlphaComponent(0.28).cgColor] as CFArray, locations: [0.55, 1])!
            ctx.drawRadialGradient(rand, startCenter: CGPoint(x: breite / 2, y: hoehe / 2), startRadius: 0, endCenter: CGPoint(x: breite / 2, y: hoehe / 2), endRadius: breite * 0.72, options: [.drawsAfterEndLocation])
        }
    }

    private static func kamm(_ ctx: CGContext, _ b: CGFloat, _ h: CGFloat, basis: CGFloat, amp: CGFloat, stufen: Int, farbe: UIColor, _ rnd: inout Zufall, schnee: Bool) {
        let p = CGMutablePath()
        p.move(to: CGPoint(x: 0, y: h))
        var spitzen: [CGPoint] = []
        for i in 0...stufen {
            let x = b * CGFloat(i) / CGFloat(stufen)
            let y = h * (basis - amp * (i % 2 == 0 ? rnd.naechste() * 0.55 : 0.45 + rnd.naechste() * 0.55))
            p.addLine(to: CGPoint(x: x, y: y)); spitzen.append(CGPoint(x: x, y: y))
        }
        p.addLine(to: CGPoint(x: b, y: h)); p.closeSubpath()
        ctx.setFillColor(farbe.cgColor); ctx.addPath(p); ctx.fillPath()
        if schnee {
            ctx.setFillColor(UIColor.white.withAlphaComponent(0.85).cgColor)
            for s in spitzen where s.y < h * (basis - amp * 0.55) {
                let k = CGMutablePath(); k.move(to: s); k.addLine(to: CGPoint(x: s.x - b * 0.035, y: s.y + h * 0.05)); k.addLine(to: CGPoint(x: s.x + b * 0.035, y: s.y + h * 0.05)); k.closeSubpath()
                ctx.addPath(k); ctx.fillPath()
            }
        }
    }

    private static func meer(_ ctx: CGContext, _ b: CGFloat, _ h: CGFloat, von: CGFloat, farbe: UIColor, glanz: UIColor, sx: CGFloat) {
        ctx.setFillColor(farbe.cgColor); ctx.fill(CGRect(x: 0, y: h * von, width: b, height: h * (1 - von)))
        ctx.setFillColor(glanz.withAlphaComponent(0.35).cgColor)
        for i in 0..<7 {
            let y = h * (von + 0.03 + CGFloat(i) * 0.045), br = b * (0.06 + CGFloat(i) * 0.03)
            ctx.fill(CGRect(x: sx - br / 2, y: y, width: br, height: max(2, h * 0.006)))
        }
    }

    private static func haeuser(_ ctx: CGContext, _ b: CGFloat, _ h: CGFloat, basis: CGFloat, farbe: UIColor, _ rnd: inout Zufall, hoch: CGFloat) {
        var x: CGFloat = 0
        ctx.setFillColor(farbe.cgColor)
        while x < b {
            let w = b * (0.05 + 0.06 * rnd.naechste()), top = h * (basis - hoch * rnd.naechste())
            ctx.fill(CGRect(x: x, y: top, width: w + 1, height: h - top)); x += w
        }
    }
}
