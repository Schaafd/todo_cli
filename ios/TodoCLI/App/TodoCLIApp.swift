import SwiftUI
import WidgetKit
import UserNotifications

@main
struct TodoCLIApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var themeManager = ThemeManager()
    @StateObject private var apiClient = APIClient()
    @StateObject private var biometricAuth = BiometricAuthManager()
    @StateObject private var pushNotificationManager = PushNotificationManager()
    @StateObject private var offlineManager = OfflineManager()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ZStack {
                ContentView()
                    .environmentObject(themeManager)
                    .environmentObject(apiClient)
                    .environmentObject(biometricAuth)
                    .environmentObject(pushNotificationManager)
                    .environmentObject(offlineManager)
                    .preferredColorScheme(themeManager.resolvedColorScheme)
                    .tint(themeManager.accentColor)
                    .onAppear {
                        configureAppearance()
                        pushNotificationManager.configure(apiClient: apiClient)
                        appDelegate.pushNotificationManager = pushNotificationManager
                        offlineManager.startMonitoring()
                    }

                // Lock screen overlay
                if biometricAuth.isAppLockEnabled && biometricAuth.isLocked {
                    LockScreenView()
                        .environmentObject(biometricAuth)
                        .transition(.opacity)
                }
            }
            .animation(.easeInOut(duration: 0.3), value: biometricAuth.isLocked)
            .onChange(of: scenePhase) { _, newPhase in
                switch newPhase {
                case .active:
                    if biometricAuth.isAppLockEnabled && biometricAuth.isLocked && biometricAuth.requireAuthOnLaunch {
                        Task {
                            await biometricAuth.authenticate()
                        }
                    }
                case .background:
                    biometricAuth.lockIfEnabled()
                    // Refresh widget data when app goes to background
                    WidgetCenter.shared.reloadAllTimelines()
                case .inactive:
                    break
                @unknown default:
                    break
                }
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

// MARK: - Lock Screen View

struct LockScreenView: View {
    @EnvironmentObject var biometricAuth: BiometricAuthManager
    @State private var isAuthenticating = false

    var body: some View {
        ZStack {
            // Blurred background
            Rectangle()
                .fill(.ultraThinMaterial)
                .ignoresSafeArea()

            VStack(spacing: 24) {
                Spacer()

                // App icon / lock icon
                Image(systemName: "lock.circle.fill")
                    .font(.system(size: 64))
                    .foregroundStyle(.blue)

                Text("Todo CLI")
                    .font(.title2.bold())

                Text("Locked")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                if let error = biometricAuth.authError {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.red)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 32)
                }

                Spacer()

                // Unlock button
                Button {
                    guard !isAuthenticating else { return }
                    isAuthenticating = true
                    Task {
                        await biometricAuth.authenticate()
                        isAuthenticating = false
                    }
                } label: {
                    HStack(spacing: 8) {
                        if isAuthenticating {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Image(systemName: biometricAuth.isBiometricEnabled
                                  ? biometricAuth.getBiometricIconName()
                                  : "lock.open.fill")
                        }
                        Text(biometricAuth.isBiometricEnabled
                             ? "Unlock with \(biometricAuth.getBiometricTypeName())"
                             : "Unlock")
                    }
                    .font(.headline)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(.blue)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .padding(.horizontal, 40)
                }
                .disabled(isAuthenticating)

                Spacer()
                    .frame(height: 40)
            }
        }
    }
}

// MARK: - App Delegate for Push Notification Token Handling

class AppDelegate: NSObject, UIApplicationDelegate {
    var pushNotificationManager: PushNotificationManager?

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        Task { @MainActor in
            pushNotificationManager?.registerDeviceToken(deviceToken)
        }
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        // Remote notification registration failure is non-fatal.
        // The app continues to work with local notifications only.
        print("Failed to register for remote notifications: \(error.localizedDescription)")
    }
}
