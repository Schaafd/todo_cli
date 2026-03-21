import SwiftUI

struct ContentView: View {
    @EnvironmentObject var themeManager: ThemeManager
    @EnvironmentObject var apiClient: APIClient
    @State private var selectedTab: Tab = .home
    @State private var showQuickAdd = false

    enum Tab: String, CaseIterable {
        case home = "Home"
        case tasks = "Tasks"
        case projects = "Projects"
        case focus = "Focus"
        case settings = "Settings"

        var icon: String {
            switch self {
            case .home: return "house.fill"
            case .tasks: return "checklist"
            case .projects: return "folder.fill"
            case .focus: return "timer"
            case .settings: return "gearshape.fill"
            }
        }
    }

    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            TabView(selection: $selectedTab) {
                HomeView(showQuickAdd: $showQuickAdd)
                    .tabItem {
                        Label(Tab.home.rawValue, systemImage: Tab.home.icon)
                    }
                    .tag(Tab.home)

                TaskListView()
                    .tabItem {
                        Label(Tab.tasks.rawValue, systemImage: Tab.tasks.icon)
                    }
                    .tag(Tab.tasks)

                ProjectListView()
                    .tabItem {
                        Label(Tab.projects.rawValue, systemImage: Tab.projects.icon)
                    }
                    .tag(Tab.projects)

                FocusTimerView()
                    .tabItem {
                        Label(Tab.focus.rawValue, systemImage: Tab.focus.icon)
                    }
                    .tag(Tab.focus)

                SettingsView()
                    .tabItem {
                        Label(Tab.settings.rawValue, systemImage: Tab.settings.icon)
                    }
                    .tag(Tab.settings)
            }

            // Floating Action Button
            if selectedTab != .settings && selectedTab != .focus {
                fabButton
                    .padding(.trailing, 20)
                    .padding(.bottom, 80)
            }
        }
        .sheet(isPresented: $showQuickAdd) {
            TaskCreateView()
                .environmentObject(apiClient)
                .environmentObject(themeManager)
        }
    }

    private var fabButton: some View {
        Button {
            let generator = UIImpactFeedbackGenerator(style: .medium)
            generator.impactOccurred()
            showQuickAdd = true
        } label: {
            Image(systemName: "plus")
                .font(.title2.weight(.semibold))
                .foregroundStyle(.white)
                .frame(width: 56, height: 56)
                .background(
                    Circle()
                        .fill(themeManager.accentColor)
                        .shadow(color: themeManager.accentColor.opacity(0.4), radius: 8, x: 0, y: 4)
                )
        }
        .accessibilityLabel("Add new task")
    }
}

#Preview {
    ContentView()
        .environmentObject(ThemeManager())
        .environmentObject(APIClient())
}
