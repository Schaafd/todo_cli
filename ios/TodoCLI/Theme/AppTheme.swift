import SwiftUI

class ThemeManager: ObservableObject {
    @AppStorage("accentColorHex") private var accentColorHex: String = "#007AFF"
    @AppStorage("appearanceMode") private var appearanceMode: String = "system"
    @AppStorage("listDensity") private var listDensityRaw: String = "comfortable"
    @AppStorage("showTodaySection") var showTodaySection: Bool = true
    @AppStorage("showOverdueSection") var showOverdueSection: Bool = true
    @AppStorage("showPinnedSection") var showPinnedSection: Bool = true
    @AppStorage("showRecentSection") var showRecentSection: Bool = true

    // MARK: - Accent Color

    var accentColor: Color {
        get { Color(hex: accentColorHex) ?? .blue }
        set {
            accentColorHex = newValue.toHex() ?? "#007AFF"
            objectWillChange.send()
        }
    }

    static let presetColors: [(name: String, color: Color)] = [
        ("Blue", .blue),
        ("Indigo", .indigo),
        ("Purple", .purple),
        ("Pink", .pink),
        ("Red", .red),
        ("Orange", .orange),
        ("Teal", .teal),
        ("Green", .green),
        ("Mint", .mint),
        ("Cyan", .cyan),
    ]

    // MARK: - Appearance

    enum Appearance: String, CaseIterable {
        case light, dark, system

        var displayName: String { rawValue.capitalized }

        var icon: String {
            switch self {
            case .light: return "sun.max.fill"
            case .dark: return "moon.fill"
            case .system: return "circle.lefthalf.filled"
            }
        }
    }

    var appearance: Appearance {
        get { Appearance(rawValue: appearanceMode) ?? .system }
        set {
            appearanceMode = newValue.rawValue
            objectWillChange.send()
        }
    }

    var resolvedColorScheme: ColorScheme? {
        switch appearance {
        case .light: return .light
        case .dark: return .dark
        case .system: return nil
        }
    }

    // MARK: - List Density

    enum ListDensity: String, CaseIterable {
        case compact, comfortable

        var displayName: String { rawValue.capitalized }

        var verticalPadding: CGFloat {
            switch self {
            case .compact: return 8
            case .comfortable: return 14
            }
        }

        var iconSize: CGFloat {
            switch self {
            case .compact: return 20
            case .comfortable: return 24
            }
        }
    }

    var listDensity: ListDensity {
        get { ListDensity(rawValue: listDensityRaw) ?? .comfortable }
        set {
            listDensityRaw = newValue.rawValue
            objectWillChange.send()
        }
    }

    // MARK: - Design Tokens

    var cardCornerRadius: CGFloat { 14 }
    var cardShadowRadius: CGFloat { 2 }
    var cardShadowOpacity: Double { 0.08 }
    var sectionSpacing: CGFloat { 24 }
    var contentPadding: CGFloat { 16 }
}

// MARK: - View Modifiers

struct MaterialCard: ViewModifier {
    @EnvironmentObject var theme: ThemeManager

    func body(content: Content) -> some View {
        content
            .background(
                RoundedRectangle(cornerRadius: theme.cardCornerRadius, style: .continuous)
                    .fill(.regularMaterial)
                    .shadow(
                        color: .black.opacity(theme.cardShadowOpacity),
                        radius: theme.cardShadowRadius,
                        x: 0,
                        y: 1
                    )
            )
    }
}

extension View {
    func materialCard() -> some View {
        modifier(MaterialCard())
    }
}
