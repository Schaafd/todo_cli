import SwiftUI
import UserNotifications

struct NotificationSettingsView: View {
    @EnvironmentObject var pushManager: PushNotificationManager
    @State private var showPermissionAlert = false
    @State private var testSent = false
    @State private var summaryTime = Date()

    var body: some View {
        Form {
            // Permission Section
            permissionSection

            // Reminder Settings
            if pushManager.isAuthorized {
                reminderSection
                dailySummarySection
                testSection
            }
        }
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            // Build a Date from the stored hour/minute for the picker
            var components = DateComponents()
            components.hour = pushManager.dailySummaryHour
            components.minute = pushManager.dailySummaryMinute
            if let date = Calendar.current.date(from: components) {
                summaryTime = date
            }
        }
        .alert("Notifications Disabled", isPresented: $showPermissionAlert) {
            Button("Open Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            }
            Button("Cancel", role: .cancel) { }
        } message: {
            Text("Notifications are disabled in system settings. Please enable them to receive task reminders.")
        }
    }

    // MARK: - Permission Section

    private var permissionSection: some View {
        Section {
            HStack {
                Label {
                    Text("Status")
                } icon: {
                    Image(systemName: statusIcon)
                        .foregroundStyle(statusColor)
                }

                Spacer()

                Text(statusText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            if !pushManager.isAuthorized {
                Button {
                    Task {
                        await requestPermission()
                    }
                } label: {
                    HStack {
                        Image(systemName: "bell.badge.fill")
                            .foregroundStyle(.blue)
                        Text("Enable Notifications")
                            .font(.body.weight(.medium))
                    }
                }
            }
        } header: {
            Text("Permission")
        } footer: {
            if pushManager.isAuthorized {
                Text("Notifications are enabled. You will receive reminders for upcoming tasks.")
            } else {
                Text("Enable notifications to receive reminders before tasks are due.")
            }
        }
    }

    // MARK: - Reminder Settings Section

    private var reminderSection: some View {
        Section {
            Picker("Remind Before Due", selection: $pushManager.reminderMinutesBefore) {
                Text("15 minutes").tag(15)
                Text("30 minutes").tag(30)
                Text("1 hour").tag(60)
                Text("2 hours").tag(120)
                Text("1 day").tag(1440)
            }
        } header: {
            Text("Task Reminders")
        } footer: {
            Text("How far in advance to remind you before a task is due.")
        }
    }

    // MARK: - Daily Summary Section

    private var dailySummarySection: some View {
        Section {
            Toggle("Daily Summary", isOn: $pushManager.dailySummaryEnabled)
                .onChange(of: pushManager.dailySummaryEnabled) { _, enabled in
                    if enabled {
                        pushManager.scheduleDailySummary()
                    } else {
                        pushManager.cancelDailySummary()
                    }
                }

            if pushManager.dailySummaryEnabled {
                DatePicker(
                    "Summary Time",
                    selection: $summaryTime,
                    displayedComponents: .hourAndMinute
                )
                .onChange(of: summaryTime) { _, newValue in
                    let components = Calendar.current.dateComponents([.hour, .minute], from: newValue)
                    pushManager.dailySummaryHour = components.hour ?? 9
                    pushManager.dailySummaryMinute = components.minute ?? 0
                    pushManager.scheduleDailySummary()
                }
            }
        } header: {
            Text("Daily Summary")
        } footer: {
            if pushManager.dailySummaryEnabled {
                Text("You'll receive a daily notification at the selected time to review your tasks.")
            } else {
                Text("Enable to receive a daily reminder to check your tasks.")
            }
        }
    }

    // MARK: - Test Section

    private var testSection: some View {
        Section {
            Button {
                pushManager.sendTestNotification()
                testSent = true
                let generator = UINotificationFeedbackGenerator()
                generator.notificationOccurred(.success)

                // Reset after a delay
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                    testSent = false
                }
            } label: {
                HStack {
                    Image(systemName: "bell.and.waves.left.and.right")
                        .foregroundStyle(.orange)
                    Text("Send Test Notification")

                    Spacer()

                    if testSent {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                            .transition(.scale.combined(with: .opacity))
                    }
                }
            }
            .disabled(testSent)
            .animation(.easeInOut, value: testSent)
        } header: {
            Text("Testing")
        } footer: {
            Text("Send a test notification to verify everything is working. It will arrive in about 2 seconds.")
        }
    }

    // MARK: - Helpers

    private var statusIcon: String {
        switch pushManager.authorizationStatus {
        case .authorized: return "checkmark.circle.fill"
        case .denied: return "xmark.circle.fill"
        case .provisional: return "checkmark.circle"
        case .ephemeral: return "clock.fill"
        case .notDetermined: return "questionmark.circle"
        @unknown default: return "questionmark.circle"
        }
    }

    private var statusColor: Color {
        switch pushManager.authorizationStatus {
        case .authorized, .provisional, .ephemeral: return .green
        case .denied: return .red
        case .notDetermined: return .orange
        @unknown default: return .gray
        }
    }

    private var statusText: String {
        switch pushManager.authorizationStatus {
        case .authorized: return "Authorized"
        case .denied: return "Denied"
        case .provisional: return "Provisional"
        case .ephemeral: return "Ephemeral"
        case .notDetermined: return "Not Requested"
        @unknown default: return "Unknown"
        }
    }

    private func requestPermission() async {
        let granted = await pushManager.requestAuthorization()
        if !granted {
            // Check if the user previously denied -- if so, direct them to Settings
            await pushManager.refreshAuthorizationStatus()
            if pushManager.authorizationStatus == .denied {
                showPermissionAlert = true
            }
        }
    }
}

#Preview {
    NavigationStack {
        NotificationSettingsView()
            .environmentObject(PushNotificationManager())
    }
}
