import SwiftUI

// MARK: - Semantic Colors

extension Color {
    static let surfacePrimary = Color("SurfacePrimary", bundle: nil)
    static let surfaceSecondary = Color("SurfaceSecondary", bundle: nil)

    // Priority colors
    static let priorityCritical = Color(red: 0.88, green: 0.19, blue: 0.19)
    static let priorityHigh = Color(red: 1.0, green: 0.47, blue: 0.0)
    static let priorityMedium = Color(red: 1.0, green: 0.76, blue: 0.03)
    static let priorityLow = Color(red: 0.30, green: 0.69, blue: 0.31)

    static func forPriority(_ priority: TaskPriority) -> Color {
        switch priority {
        case .critical: return .priorityCritical
        case .high: return .priorityHigh
        case .medium: return .priorityMedium
        case .low: return .priorityLow
        }
    }

    // Status colors
    static let statusCompleted = Color(red: 0.30, green: 0.69, blue: 0.31)
    static let statusOverdue = Color(red: 0.88, green: 0.19, blue: 0.19)
    static let statusDueToday = Color(red: 1.0, green: 0.47, blue: 0.0)
    static let statusActive = Color(red: 0.13, green: 0.59, blue: 0.95)

    // Background tints
    static let backgroundSuccess = Color(red: 0.30, green: 0.69, blue: 0.31).opacity(0.1)
    static let backgroundWarning = Color(red: 1.0, green: 0.76, blue: 0.03).opacity(0.1)
    static let backgroundError = Color(red: 0.88, green: 0.19, blue: 0.19).opacity(0.1)
    static let backgroundInfo = Color(red: 0.13, green: 0.59, blue: 0.95).opacity(0.1)
}

// MARK: - Hex Color Support

extension Color {
    init?(hex: String) {
        var hexSanitized = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        hexSanitized = hexSanitized.replacingOccurrences(of: "#", with: "")

        guard hexSanitized.count == 6 else { return nil }

        var rgb: UInt64 = 0
        guard Scanner(string: hexSanitized).scanHexInt64(&rgb) else { return nil }

        let r = Double((rgb & 0xFF0000) >> 16) / 255.0
        let g = Double((rgb & 0x00FF00) >> 8) / 255.0
        let b = Double(rgb & 0x0000FF) / 255.0

        self.init(red: r, green: g, blue: b)
    }

    func toHex() -> String? {
        guard let components = UIColor(self).cgColor.components else { return nil }
        let r = components.count > 0 ? components[0] : 0
        let g = components.count > 1 ? components[1] : 0
        let b = components.count > 2 ? components[2] : 0

        return String(
            format: "#%02lX%02lX%02lX",
            lround(Double(r) * 255),
            lround(Double(g) * 255),
            lround(Double(b) * 255)
        )
    }
}
