import SwiftUI

@main
struct TodoCLIApp: App {
    @StateObject private var themeManager = ThemeManager()
    @StateObject private var apiClient = APIClient()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(themeManager)
                .environmentObject(apiClient)
                .preferredColorScheme(themeManager.resolvedColorScheme)
                .tint(themeManager.accentColor)
                .onAppear {
                    configureAppearance()
                }
        }
    }

    private func configureAppearance() {
        let appearance = UITabBarAppearance()
        appearance.configureWithDefaultBackground()
        UITabBar.appearance().scrollEdgeAppearance = appearance
        UITabBar.appearance().standardAppearance = appearance

        let navAppearance = UINavigationBarAppearance()
        navAppearance.configureWithDefaultBackground()
        UINavigationBar.appearance().scrollEdgeAppearance = navAppearance
        UINavigationBar.appearance().standardAppearance = navAppearance
    }
}
