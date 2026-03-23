import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var themeManager: ThemeManager
    @EnvironmentObject var apiClient: APIClient
    @EnvironmentObject var biometricAuth: BiometricAuthManager
    @State private var serverURL: String = ""
    @State private var isTestingConnection = false
    @State private var connectionStatus: ConnectionStatus = .unknown

    enum ConnectionStatus {
        case unknown, testing, success, failure
    }

    var body: some View {
        NavigationStack {
            Form {
                // Appearance
                Section {
                    NavigationLink {
                        ThemePickerView()
                    } label: {
                        Label {
                            VStack(alignment: .leading) {
                                Text("Theme & Appearance")
                                Text("Colors, dark mode, density")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        } icon: {
                            Image(systemName: "paintpalette.fill")
                                .foregroundStyle(themeManager.accentColor)
                        }
                    }
                } header: {
                    Text("Appearance")
                }

                // Notifications
                Section {
                    NavigationLink {
                        NotificationSettingsView()
                    } label: {
                        Label {
                            VStack(alignment: .leading) {
                                Text("Notifications")
                                Text("Reminders, daily summary")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        } icon: {
                            Image(systemName: "bell.badge.fill")
                                .foregroundStyle(.orange)
                        }
                    }
                } header: {
                    Text("Notifications")
                }

                // Home Screen
                Section {
                    Toggle("Today's Tasks", isOn: $themeManager.showTodaySection)
                    Toggle("Overdue Tasks", isOn: $themeManager.showOverdueSection)
                    Toggle("Pinned Tasks", isOn: $themeManager.showPinnedSection)
                    Toggle("Recent Tasks", isOn: $themeManager.showRecentSection)
                } header: {
                    Text("Home Screen Sections")
                } footer: {
                    Text("Choose which sections appear on the home screen.")
                }

                // Server Configuration
                Section {
                    HStack {
                        Image(systemName: "server.rack")
                            .foregroundStyle(.secondary)
                        TextField("http://localhost:8000", text: $serverURL)
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.never)
                            .keyboardType(.URL)
                    }

                    Button {
                        Task { await testConnection() }
                    } label: {
                        HStack {
                            Text("Test Connection")
                            Spacer()
                            switch connectionStatus {
                            case .unknown:
                                EmptyView()
                            case .testing:
                                ProgressView()
                            case .success:
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(.green)
                            case .failure:
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundStyle(.red)
                            }
                        }
                    }

                    Button("Save Server URL") {
                        let trimmed = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
                        guard let url = URL(string: trimmed), url.scheme != nil, url.host != nil else {
                            connectionStatus = .failure
                            return
                        }
                        apiClient.baseURL = trimmed
                        let generator = UINotificationFeedbackGenerator()
                        generator.notificationOccurred(.success)
                    }
                    .disabled(serverURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                } header: {
                    Text("Server")
                } footer: {
                    Text("Configure the URL of your Todo CLI backend server.")
                }

                // Security
                Section {
                    NavigationLink {
                        AppLockView()
                            .environmentObject(biometricAuth)
                    } label: {
                        Label {
                            VStack(alignment: .leading) {
                                Text("App Lock")
                                Text(biometricAuth.isAppLockEnabled
                                     ? "Enabled (\(biometricAuth.isBiometricEnabled ? biometricAuth.getBiometricTypeName() : "Passcode"))"
                                     : "Disabled")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        } icon: {
                            Image(systemName: "lock.shield.fill")
                                .foregroundStyle(.blue)
                        }
                    }

                    Toggle(isOn: $apiClient.isPinningEnabled) {
                        Label {
                            VStack(alignment: .leading) {
                                Text("Certificate Pinning")
                                Text("Validate server certificates against pinned keys")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        } icon: {
                            Image(systemName: "checkmark.shield.fill")
                                .foregroundStyle(.green)
                        }
                    }
                } header: {
                    Text("Security")
                } footer: {
                    Text("App Lock protects access to the app. Certificate Pinning adds extra network security.")
                }

                // Account
                Section("Account") {
                    if apiClient.isAuthenticated {
                        Button(role: .destructive) {
                            apiClient.logout()
                        } label: {
                            Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                        }
                    } else {
                        Label {
                            Text("Not signed in")
                                .foregroundStyle(.secondary)
                        } icon: {
                            Image(systemName: "person.crop.circle")
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                // About
                Section("About") {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundStyle(.secondary)
                    }

                    HStack {
                        Text("Build")
                        Spacer()
                        Text("1")
                            .foregroundStyle(.secondary)
                    }

                    Link(destination: URL(string: "https://github.com/todo-cli/todo-cli")!) {
                        Label("GitHub Repository", systemImage: "link")
                    }
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .onAppear {
                serverURL = apiClient.baseURL
            }
        }
    }

    private func testConnection() async {
        connectionStatus = .testing
        isTestingConnection = true

        // Simple health check
        let testURL = serverURL.hasSuffix("/")
            ? "\(serverURL)health"
            : "\(serverURL)/health"

        guard let url = URL(string: testURL) else {
            connectionStatus = .failure
            isTestingConnection = false
            return
        }

        do {
            let (_, response) = try await URLSession.shared.data(from: url)
            if let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 {
                connectionStatus = .success
                let generator = UINotificationFeedbackGenerator()
                generator.notificationOccurred(.success)
            } else {
                connectionStatus = .failure
            }
        } catch {
            connectionStatus = .failure
        }

        isTestingConnection = false
    }
}

#Preview {
    SettingsView()
        .environmentObject(ThemeManager())
        .environmentObject(APIClient())
        .environmentObject(BiometricAuthManager())
}
