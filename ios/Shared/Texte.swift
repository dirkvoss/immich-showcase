import Foundation

/// Übersetzbarer Text für Stellen, an denen ein normaler String gebraucht wird (Fehlermeldungen, Statuszeilen). Die Texte stehen im String-Katalog.
func L(_ schluessel: String.LocalizationValue) -> String { String(localized: schluessel) }
