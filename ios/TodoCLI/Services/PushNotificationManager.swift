import UserNotifications
import UIKit
import Combine

/// Manages push notification registration, scheduling, and handling for the app.
@MainActor
class PushNotificationManager: NSObject, ObservableObject {
    @Published var isAuthorized: Bool = false
    @Published var deviceToken: String?
    @Published var authorizationStatus: UNAuthorizationStatus = .notDetermined

    @AppStorage("notificationsEnabled") var notificationsEnabled: Bool = false
    @AppStorage("dailySummaryEnabled") var dailySummaryEnabled: Bool = false
    @AppStorage("dailySummaryHour") var dailySummaryHour: Int = 9
    @AppStorage("dailySummaryMinute") var dailySummaryMinute: Int = 0
    @AppStorage("reminderMinutesBefore") var reminderMinutesBefore: Int = 30

    private var apiClient: APIClient?

    override init() {
        super.init()
    }

    /// Configure the manager with dependencies and set up initial state.
    func configure(apiClient: APIClient) {
        self.apiClient = apiClient
        UNUserNotificationCenter.current().delegate = self
        setupNotificationActions()
        Task {
            await refreshAuthorizationStatus()
        }
    }

    // MARK: - Authorization

    /// Refresh the current authorization status from the system.
    func refreshAuthorizationStatus() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        authorizationStatus = settings.authorizationStatus
        isAuthorized = settings.authorizationStatus == .authorized
    }

    /// Request notification permissions from the user.
    /// Returns true if permission was granted.
    @discardableResult
    func requestAuthorization() async -> Bool {
        do {
            let granted = try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .badge, .sound])
            isAuthorized = granted
            notificationsEnabled = granted

            if granted {
                UIApplication.shared.registerForRemoteNotifications()
            }

            await refreshAuthorizationStatus()
            return granted
        } catch {
            isAuthorized = false
            notificationsEnabled = false
            return false
        }
    }

    // MARK: - Device Token Registration

    /// Register the device token received from APNs with the backend server.
    func registerDeviceToken(_ token: Data) {
        let tokenString = token.map { String(format: "%02.2hhx", $0) }.joined()
        self.deviceToken = tokenString

        guard let apiClient = apiClient else { return }

        Task {
            do {
                let body = DeviceTokenRequest(token: tokenString, platform: "ios")
                let _: SuccessResponse = try await apiClient.registerDeviceToken(body)
            } catch {
                // Token registration failure is non-fatal; the app continues to work
                // with local notifications. Registration will be retried on next launch.
                print("Failed to register device token: \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Task Reminders

    /// Schedule a local notification reminder for a task due date.
    /// - Parameters:
    ///   - taskId: The unique identifier of the task.
    ///   - title: The task title to display in the notification.
    ///   - dueDate: When the task is due.
    ///   - minutesBefore: How many minutes before the due date to fire the reminder.
    func scheduleTaskReminder(taskId: String, title: String, dueDate: Date, minutesBefore: Int? = nil) {
        guard isAuthorized else { return }

        let offset = minutesBefore ?? reminderMinutesBefore

        let content = UNMutableNotificationContent()
        content.title = "Task Due Soon"
        content.body = title
        content.sound = .default
        content.userInfo = ["taskId": taskId]
        content.categoryIdentifier = "TASK_REMINDER"

        let triggerDate = dueDate.addingTimeInterval(TimeInterval(-offset * 60))
        guard triggerDate > Date() else { return }

        let components = Calendar.current.dateComponents(
            [.year, .month, .day, .hour, .minute],
            from: triggerDate
        )
        let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: false)

        let request = UNNotificationRequest(
            identifier: "task-\(taskId)",
            content: content,
            trigger: trigger
        )

        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                print("Failed to schedule task reminder: \(error.localizedDescription)")
            }
        }
    }

    /// Remove the scheduled notification for a specific task.
    func cancelTaskReminder(taskId: String) {
        UNUserNotificationCenter.current()
            .removePendingNotificationRequests(withIdentifiers: ["task-\(taskId)"])
    }

    // MARK: - Daily Summary

    /// Schedule a repeating daily summary notification at the configured time.
    func scheduleDailySummary() {
        guard isAuthorized && dailySummaryEnabled else {
            cancelDailySummary()
            return
        }

        // Remove existing before rescheduling
        cancelDailySummary()

        let content = UNMutableNotificationContent()
        content.title = "Daily Task Summary"
        content.body = "Check your tasks for today"
        content.sound = .default
        content.categoryIdentifier = "DAILY_SUMMARY"

        var components = DateComponents()
        components.hour = dailySummaryHour
        components.minute = dailySummaryMinute

        let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: true)
        let request = UNNotificationRequest(
            identifier: "daily-summary",
            content: content,
            trigger: trigger
        )

        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                print("Failed to schedule daily summary: \(error.localizedDescription)")
            }
        }
    }

    /// Cancel the daily summary notification.
    func cancelDailySummary() {
        UNUserNotificationCenter.current()
            .removePendingNotificationRequests(withIdentifiers: ["daily-summary"])
    }

    // MARK: - Test Notification

    /// Send a test notification to verify the setup is working.
    func sendTestNotification() {
        let content = UNMutableNotificationContent()
        content.title = "Test Notification"
        content.body = "Notifications are working correctly!"
        content.sound = .default

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 2, repeats: false)
        let request = UNNotificationRequest(
            identifier: "test-notification",
            content: content,
            trigger: trigger
        )

        UNUserNotificationCenter.current().add(request) { error in
            if let error = error {
                print("Failed to send test notification: \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Remove All

    /// Remove all pending notifications scheduled by the app.
    func removeAllPendingNotifications() {
        UNUserNotificationCenter.current().removeAllPendingNotificationRequests()
    }

    // MARK: - Notification Actions Setup

    /// Configure interactive notification action categories.
    func setupNotificationActions() {
        let completeAction = UNNotificationAction(
            identifier: "COMPLETE_TASK",
            title: "Mark Complete",
            options: []
        )

        let snoozeAction = UNNotificationAction(
            identifier: "SNOOZE_TASK",
            title: "Snooze 1 Hour",
            options: []
        )

        let taskCategory = UNNotificationCategory(
            identifier: "TASK_REMINDER",
            actions: [completeAction, snoozeAction],
            intentIdentifiers: [],
            options: []
        )

        let viewAction = UNNotificationAction(
            identifier: "VIEW_TASKS",
            title: "View Tasks",
            options: [.foreground]
        )

        let dailySummaryCategory = UNNotificationCategory(
            identifier: "DAILY_SUMMARY",
            actions: [viewAction],
            intentIdentifiers: [],
            options: []
        )

        UNUserNotificationCenter.current().setNotificationCategories([
            taskCategory,
            dailySummaryCategory
        ])
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension PushNotificationManager: UNUserNotificationCenterDelegate {
    /// Handle notifications that arrive while the app is in the foreground.
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .badge, .sound])
    }

    /// Handle user interaction with a notification (tap or action button).
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        let taskId = userInfo["taskId"] as? String

        Task { @MainActor in
            switch response.actionIdentifier {
            case "COMPLETE_TASK":
                if let taskId = taskId, let apiClient = self.apiClient {
                    do {
                        _ = try await apiClient.toggleTask(id: taskId)
                    } catch {
                        print("Failed to complete task from notification: \(error.localizedDescription)")
                    }
                }

            case "SNOOZE_TASK":
                if let taskId = taskId {
                    let title = response.notification.request.content.body
                    self.scheduleTaskReminder(
                        taskId: taskId,
                        title: title,
                        dueDate: Date().addingTimeInterval(3600),
                        minutesBefore: 0
                    )
                }

            case "VIEW_TASKS":
                // The app will open to foreground via the .foreground option on the action.
                // Navigation can be handled via NotificationCenter or a shared navigation state.
                NotificationCenter.default.post(
                    name: .navigateToTasks,
                    object: nil
                )

            case UNNotificationDefaultActionIdentifier:
                // User tapped the notification itself
                if let taskId = taskId {
                    NotificationCenter.default.post(
                        name: .navigateToTask,
                        object: nil,
                        userInfo: ["taskId": taskId]
                    )
                }

            default:
                break
            }
        }

        completionHandler()
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let navigateToTasks = Notification.Name("navigateToTasks")
    static let navigateToTask = Notification.Name("navigateToTask")
}

// MARK: - Device Token Request Model

struct DeviceTokenRequest: Codable {
    let token: String
    let platform: String
}
