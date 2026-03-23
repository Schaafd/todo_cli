import XCTest
import SwiftUI
@testable import TodoCLI

final class ThemeTests: XCTestCase {

    // MARK: - ThemeManager Default Values

    func testThemeManagerDefaultAccentColorHex() {
        let theme = ThemeManager()
        // Default accent color is blue (#007AFF)
        // We can check that it returns a valid color
        let color = theme.accentColor
        XCTAssertNotNil(color)
    }

    func testThemeManagerDefaultAppearanceIsSystem() {
        let theme = ThemeManager()
        XCTAssertEqual(theme.appearance, .system)
    }

    func testThemeManagerDefaultListDensityIsComfortable() {
        let theme = ThemeManager()
        XCTAssertEqual(theme.listDensity, .comfortable)
    }

    func testThemeManagerDefaultShowTodaySection() {
        let theme = ThemeManager()
        XCTAssertTrue(theme.showTodaySection)
    }

    func testThemeManagerDefaultShowOverdueSection() {
        let theme = ThemeManager()
        XCTAssertTrue(theme.showOverdueSection)
    }

    func testThemeManagerDefaultShowPinnedSection() {
        let theme = ThemeManager()
        XCTAssertTrue(theme.showPinnedSection)
    }

    func testThemeManagerDefaultShowRecentSection() {
        let theme = ThemeManager()
        XCTAssertTrue(theme.showRecentSection)
    }

    // MARK: - Design Tokens

    func testCardCornerRadius() {
        let theme = ThemeManager()
        XCTAssertEqual(theme.cardCornerRadius, 14)
    }

    func testCardShadowRadius() {
        let theme = ThemeManager()
        XCTAssertEqual(theme.cardShadowRadius, 2)
    }

    func testCardShadowOpacity() {
        let theme = ThemeManager()
        XCTAssertEqual(theme.cardShadowOpacity, 0.08, accuracy: 0.001)
    }

    func testSectionSpacing() {
        let theme = ThemeManager()
        XCTAssertEqual(theme.sectionSpacing, 24)
    }

    func testContentPadding() {
        let theme = ThemeManager()
        XCTAssertEqual(theme.contentPadding, 16)
    }

    // MARK: - Accent Color Presets

    func testPresetColorsCount() {
        XCTAssertEqual(ThemeManager.presetColors.count, 10)
    }

    func testPresetColorsContainsBlue() {
        XCTAssertTrue(ThemeManager.presetColors.contains { $0.name == "Blue" })
    }

    func testPresetColorsContainsAllExpected() {
        let names = ThemeManager.presetColors.map { $0.name }
        XCTAssertTrue(names.contains("Blue"))
        XCTAssertTrue(names.contains("Indigo"))
        XCTAssertTrue(names.contains("Purple"))
        XCTAssertTrue(names.contains("Pink"))
        XCTAssertTrue(names.contains("Red"))
        XCTAssertTrue(names.contains("Orange"))
        XCTAssertTrue(names.contains("Teal"))
        XCTAssertTrue(names.contains("Green"))
        XCTAssertTrue(names.contains("Mint"))
        XCTAssertTrue(names.contains("Cyan"))
    }

    func testPresetColorsHaveNonNilColors() {
        for preset in ThemeManager.presetColors {
            XCTAssertNotNil(preset.color, "Preset color '\(preset.name)' should not be nil")
        }
    }

    // MARK: - Appearance Modes

    func testAppearanceLightDisplayName() {
        XCTAssertEqual(ThemeManager.Appearance.light.displayName, "Light")
    }

    func testAppearanceDarkDisplayName() {
        XCTAssertEqual(ThemeManager.Appearance.dark.displayName, "Dark")
    }

    func testAppearanceSystemDisplayName() {
        XCTAssertEqual(ThemeManager.Appearance.system.displayName, "System")
    }

    func testAppearanceLightIcon() {
        XCTAssertEqual(ThemeManager.Appearance.light.icon, "sun.max.fill")
    }

    func testAppearanceDarkIcon() {
        XCTAssertEqual(ThemeManager.Appearance.dark.icon, "moon.fill")
    }

    func testAppearanceSystemIcon() {
        XCTAssertEqual(ThemeManager.Appearance.system.icon, "circle.lefthalf.filled")
    }

    func testAppearanceAllCases() {
        XCTAssertEqual(ThemeManager.Appearance.allCases.count, 3)
    }

    func testResolvedColorSchemeLight() {
        let theme = ThemeManager()
        theme.appearance = .light
        XCTAssertEqual(theme.resolvedColorScheme, .light)
    }

    func testResolvedColorSchemeDark() {
        let theme = ThemeManager()
        theme.appearance = .dark
        XCTAssertEqual(theme.resolvedColorScheme, .dark)
    }

    func testResolvedColorSchemeSystemIsNil() {
        let theme = ThemeManager()
        theme.appearance = .system
        XCTAssertNil(theme.resolvedColorScheme)
    }

    // MARK: - List Density

    func testListDensityCompactPadding() {
        XCTAssertEqual(ThemeManager.ListDensity.compact.verticalPadding, 8)
    }

    func testListDensityComfortablePadding() {
        XCTAssertEqual(ThemeManager.ListDensity.comfortable.verticalPadding, 14)
    }

    func testListDensityCompactIconSize() {
        XCTAssertEqual(ThemeManager.ListDensity.compact.iconSize, 20)
    }

    func testListDensityComfortableIconSize() {
        XCTAssertEqual(ThemeManager.ListDensity.comfortable.iconSize, 24)
    }

    func testListDensityCompactDisplayName() {
        XCTAssertEqual(ThemeManager.ListDensity.compact.displayName, "Compact")
    }

    func testListDensityComfortableDisplayName() {
        XCTAssertEqual(ThemeManager.ListDensity.comfortable.displayName, "Comfortable")
    }

    func testListDensityAllCases() {
        XCTAssertEqual(ThemeManager.ListDensity.allCases.count, 2)
    }

    // MARK: - Colors Priority Mappings

    func testColorForPriorityCritical() {
        let color = Color.forPriority(.critical)
        XCTAssertNotNil(color)
        // Verify it matches priorityCritical
        XCTAssertEqual(color, Color.priorityCritical)
    }

    func testColorForPriorityHigh() {
        XCTAssertEqual(Color.forPriority(.high), Color.priorityHigh)
    }

    func testColorForPriorityMedium() {
        XCTAssertEqual(Color.forPriority(.medium), Color.priorityMedium)
    }

    func testColorForPriorityLow() {
        XCTAssertEqual(Color.forPriority(.low), Color.priorityLow)
    }

    // MARK: - Status Colors Exist

    func testStatusCompletedColor() {
        let color = Color.statusCompleted
        XCTAssertNotNil(color)
    }

    func testStatusOverdueColor() {
        let color = Color.statusOverdue
        XCTAssertNotNil(color)
    }

    func testStatusDueTodayColor() {
        let color = Color.statusDueToday
        XCTAssertNotNil(color)
    }

    func testStatusActiveColor() {
        let color = Color.statusActive
        XCTAssertNotNil(color)
    }

    // MARK: - Hex Color Parsing

    func testHexColorParsingWithHash() {
        let color = Color(hex: "#FF0000")
        XCTAssertNotNil(color)
    }

    func testHexColorParsingWithoutHash() {
        let color = Color(hex: "00FF00")
        XCTAssertNotNil(color)
    }

    func testHexColorParsingBlue() {
        let color = Color(hex: "#0000FF")
        XCTAssertNotNil(color)
    }

    func testHexColorParsingBlack() {
        let color = Color(hex: "#000000")
        XCTAssertNotNil(color)
    }

    func testHexColorParsingWhite() {
        let color = Color(hex: "#FFFFFF")
        XCTAssertNotNil(color)
    }

    func testHexColorParsingInvalidLength() {
        let color = Color(hex: "#FFF")
        XCTAssertNil(color)
    }

    func testHexColorParsingInvalidCharacters() {
        let color = Color(hex: "#GGGGGG")
        XCTAssertNil(color)
    }

    func testHexColorParsingEmptyString() {
        let color = Color(hex: "")
        XCTAssertNil(color)
    }

    func testHexColorParsingWithWhitespace() {
        let color = Color(hex: "  #FF5733  ")
        XCTAssertNotNil(color)
    }

    func testHexColorParsingTooLong() {
        let color = Color(hex: "#FF5733AA")
        XCTAssertNil(color) // Only 6-char hex supported
    }

    // MARK: - Project SwiftUI Color

    func testProjectSwiftUIColorWithHex() {
        let project = Project(id: "1", name: "Test", color: "#FF5733")
        let color = project.swiftUIColor
        XCTAssertNotNil(color)
    }

    func testProjectSwiftUIColorDefaultsToBlue() {
        let project = Project(id: "1", name: "Test", color: nil)
        XCTAssertEqual(project.swiftUIColor, .blue)
    }
}
