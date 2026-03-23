import SwiftUI

/// Settings subview for configuring biometric lock and app security.
struct AppLockView: View {
    @EnvironmentObject var biometricAuth: BiometricAuthManager
    @State private var showDisableAlert = false
    @State private var biometricAvailable = false

    var body: some View {
        Form {
            // App Lock Toggle
            Section {
                Toggle(isOn: $biometricAuth.isAppLockEnabled) {
                    Label {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("App Lock")
                            Text("Require authentication to open the app")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    } icon: {
                        Image(systemName: "lock.fill")
                            .foregroundStyle(.blue)
                    }
                }
                .onChange(of: biometricAuth.isAppLockEnabled) { _, newValue in
                    if !newValue {
                        // Unlock immediately when disabling app lock
                        biometricAuth.unlock()
                        biometricAuth.isBiometricEnabled = false
                    }
                }
            } header: {
                Text("App Lock")
            } footer: {
                Text("When enabled, you must authenticate each time you open the app.")
            }

            // Biometric Authentication
            if biometricAuth.isAppLockEnabled {
                Section {
                    if biometricAvailable {
                        Toggle(isOn: $biometricAuth.isBiometricEnabled) {
                            Label {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("Use \(biometricAuth.getBiometricTypeName())")
                                    Text("Unlock with \(biometricAuth.getBiometricTypeName()) instead of passcode")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            } icon: {
                                Image(systemName: biometricAuth.getBiometricIconName())
                                    .foregroundStyle(.green)
                            }
                        }
                    } else {
                        Label {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Biometrics Unavailable")
                                Text("Set up \(biometricAuth.getBiometricTypeName()) in device Settings to use this feature.")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        } icon: {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundStyle(.orange)
                        }
                    }
                } header: {
                    Text("Biometric Authentication")
                } footer: {
                    if biometricAvailable {
                        Text("\(biometricAuth.getBiometricTypeName()) provides a fast and secure way to unlock the app.")
                    }
                }

                // Launch Behavior
                Section {
                    Toggle(isOn: $biometricAuth.requireAuthOnLaunch) {
                        Label {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Require on Launch")
                                Text("Authenticate every time the app opens")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        } icon: {
                            Image(systemName: "arrow.clockwise.circle.fill")
                                .foregroundStyle(.purple)
                        }
                    }
                } header: {
                    Text("Behavior")
                } footer: {
                    Text("When enabled, authentication is required each time the app comes to the foreground.")
                }
            }

            // Info Section
            Section {
                HStack {
                    Text("Biometric Type")
                    Spacer()
                    Text(biometricAvailable ? biometricAuth.getBiometricTypeName() : "Not Available")
                        .foregroundStyle(.secondary)
                }

                HStack {
                    Text("Status")
                    Spacer()
                    if biometricAuth.isAppLockEnabled {
                        Text("Protected")
                            .foregroundStyle(.green)
                    } else {
                        Text("Not Protected")
                            .foregroundStyle(.secondary)
                    }
                }
            } header: {
                Text("Security Info")
            }
        }
        .navigationTitle("App Lock")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            biometricAvailable = biometricAuth.checkBiometricAvailability()
        }
    }
}

#Preview {
    NavigationStack {
        AppLockView()
            .environmentObject(BiometricAuthManager())
    }
}
