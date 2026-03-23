import Foundation

/// Codable representation of a task for widget display.
/// Kept lightweight for efficient storage in UserDefaults.
struct WidgetTask: Identifiable, Codable {
    let id: String
    let text: String
    let priority: String
    let dueDate: Date?
    let project: String?
    let completed: Bool

    var isOverdue: Bool {
        guard let due = dueDate, !completed else { return false }
        return due < Date()
    }

    var isDueToday: Bool {
        guard let due = dueDate else { return false }
        return Calendar.current.isDateInToday(due)
    }

    var priorityColor: String {
        switch priority.lowercased() {
        case "critical": return "red"
        case "high": return "orange"
        case "medium": return "yellow"
        case "low": return "green"
        default: return "gray"
        }
    }
}

/// Manages data sharing between the main app and the home screen widget
/// via App Group UserDefaults.
class SharedDataManager {
    static let shared = SharedDataManager()

    private let appGroupId = "group.com.todocli.shared"
    private let tasksKey = "widget_tasks"
    private let lastUpdatedKey = "widget_last_updated"
    private let statsKey = "widget_stats"
    private let userDefaults: UserDefaults?

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()

    init() {
        userDefaults = UserDefaults(suiteName: appGroupId)
    }

    /// Saves tasks from the main app for the widget to display.
    /// Filters to only pending tasks, sorted by priority and due date.
    func saveTasksForWidget(_ tasks: [TodoTask]) {
        let widgetTasks = tasks
            .sorted { task1, task2 in
                // Sort by: overdue first, then by priority, then by due date
                if task1.isOverdue != task2.isOverdue {
                    return task1.isOverdue
                }
                if task1.priority != task2.priority {
                    return task1.priority < task2.priority
                }
                if let d1 = task1.dueDate, let d2 = task2.dueDate {
                    return d1 < d2
                }
                return task1.dueDate != nil
            }
            .prefix(20) // Keep only top 20 for widget
            .map { task in
                WidgetTask(
                    id: task.id,
                    text: task.text,
                    priority: task.priority.rawValue,
                    dueDate: task.dueDate,
                    project: task.project,
                    completed: task.completed
                )
            }

        if let data = try? encoder.encode(Array(widgetTasks)) {
            userDefaults?.set(data, forKey: tasksKey)
        }

        // Save stats
        let overdueCount = tasks.filter { $0.isOverdue }.count
        let completedToday = tasks.filter { task in
            task.completed && task.isDueToday
        }.count
        let totalPending = tasks.filter { !$0.completed }.count

        let stats: [String: Int] = [
            "overdue": overdueCount,
            "completedToday": completedToday,
            "totalPending": totalPending
        ]

        if let statsData = try? encoder.encode(stats) {
            userDefaults?.set(statsData, forKey: statsKey)
        }

        userDefaults?.set(Date().timeIntervalSince1970, forKey: lastUpdatedKey)
        userDefaults?.synchronize()
    }

    /// Loads tasks previously saved for the widget.
    func loadTasksForWidget() -> [WidgetTask] {
        guard let data = userDefaults?.data(forKey: tasksKey),
              let tasks = try? decoder.decode([WidgetTask].self, from: data) else {
            return []
        }
        return tasks
    }

    /// Loads cached stats for widget display.
    func loadStats() -> (overdue: Int, completedToday: Int, totalPending: Int) {
        guard let data = userDefaults?.data(forKey: statsKey),
              let stats = try? decoder.decode([String: Int].self, from: data) else {
            return (0, 0, 0)
        }
        return (
            overdue: stats["overdue"] ?? 0,
            completedToday: stats["completedToday"] ?? 0,
            totalPending: stats["totalPending"] ?? 0
        )
    }

    /// Returns when the widget data was last updated.
    func lastUpdated() -> Date? {
        guard let timestamp = userDefaults?.double(forKey: lastUpdatedKey), timestamp > 0 else {
            return nil
        }
        return Date(timeIntervalSince1970: timestamp)
    }
}
