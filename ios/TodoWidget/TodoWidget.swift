import WidgetKit
import SwiftUI

// MARK: - Timeline Entry

struct TaskEntry: TimelineEntry {
    let date: Date
    let tasks: [WidgetTask]
    let overdueCount: Int
    let completedToday: Int
    let totalPending: Int

    static var placeholder: TaskEntry {
        TaskEntry(
            date: Date(),
            tasks: [
                WidgetTask(id: "1", text: "Review pull request", priority: "high", dueDate: Date(), project: "Work", completed: false),
                WidgetTask(id: "2", text: "Buy groceries", priority: "medium", dueDate: Date(), project: "Personal", completed: false),
                WidgetTask(id: "3", text: "Update documentation", priority: "low", dueDate: nil, project: "Work", completed: false),
                WidgetTask(id: "4", text: "Schedule dentist", priority: "medium", dueDate: Date().addingTimeInterval(86400), project: nil, completed: false),
                WidgetTask(id: "5", text: "Fix login bug", priority: "critical", dueDate: Date(), project: "Work", completed: false),
            ],
            overdueCount: 2,
            completedToday: 3,
            totalPending: 12
        )
    }

    static var empty: TaskEntry {
        TaskEntry(
            date: Date(),
            tasks: [],
            overdueCount: 0,
            completedToday: 0,
            totalPending: 0
        )
    }
}

// MARK: - Timeline Provider

struct TodoProvider: TimelineProvider {
    private let dataManager = SharedDataManager.shared

    func placeholder(in context: Context) -> TaskEntry {
        TaskEntry.placeholder
    }

    func getSnapshot(in context: Context, completion: @escaping (TaskEntry) -> Void) {
        if context.isPreview {
            completion(TaskEntry.placeholder)
            return
        }
        let entry = buildEntry()
        completion(entry)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<TaskEntry>) -> Void) {
        let entry = buildEntry()

        // Refresh every 30 minutes
        let nextUpdate = Calendar.current.date(byAdding: .minute, value: 30, to: Date()) ?? Date()
        let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))
        completion(timeline)
    }

    private func buildEntry() -> TaskEntry {
        let tasks = dataManager.loadTasksForWidget()
        let stats = dataManager.loadStats()

        return TaskEntry(
            date: Date(),
            tasks: tasks.filter { !$0.completed },
            overdueCount: stats.overdue,
            completedToday: stats.completedToday,
            totalPending: stats.totalPending
        )
    }
}

// MARK: - Small Widget View

struct TodoWidgetSmallView: View {
    let entry: TaskEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // Header
            HStack {
                Image(systemName: "checklist")
                    .font(.caption)
                    .foregroundStyle(.blue)
                Text("Todo")
                    .font(.caption.bold())
                Spacer()
                if entry.overdueCount > 0 {
                    Text("\(entry.overdueCount)")
                        .font(.caption2.bold())
                        .padding(.horizontal, 5)
                        .padding(.vertical, 1)
                        .background(.red.opacity(0.2))
                        .foregroundStyle(.red)
                        .clipShape(Capsule())
                }
            }

            if entry.tasks.isEmpty {
                Spacer()
                VStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(.green)
                    Text("All done!")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                Spacer()
            } else {
                // Show top 3 tasks
                ForEach(entry.tasks.prefix(3)) { task in
                    SmallTaskRow(task: task)
                }
                Spacer(minLength: 0)

                // Remaining count
                let remaining = entry.totalPending - min(3, entry.tasks.count)
                if remaining > 0 {
                    Text("+\(remaining) more")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .containerBackground(.fill.tertiary, for: .widget)
    }
}

struct SmallTaskRow: View {
    let task: WidgetTask

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(colorForPriority(task.priority))
                .frame(width: 6, height: 6)
            Text(task.text)
                .font(.caption2)
                .lineLimit(1)
                .foregroundStyle(task.isOverdue ? .red : .primary)
        }
    }

    private func colorForPriority(_ priority: String) -> Color {
        switch priority.lowercased() {
        case "critical": return .red
        case "high": return .orange
        case "medium": return .yellow
        case "low": return .green
        default: return .gray
        }
    }
}

// MARK: - Medium Widget View

struct TodoWidgetMediumView: View {
    let entry: TaskEntry

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Stats Bar
            HStack(spacing: 12) {
                Image(systemName: "checklist")
                    .foregroundStyle(.blue)
                Text("Todo CLI")
                    .font(.subheadline.bold())

                Spacer()

                StatBadge(icon: "clock.badge.exclamationmark", value: entry.overdueCount, color: .red)
                StatBadge(icon: "checkmark.circle", value: entry.completedToday, color: .green)
                StatBadge(icon: "list.bullet", value: entry.totalPending, color: .blue)
            }

            Divider()

            if entry.tasks.isEmpty {
                HStack {
                    Spacer()
                    VStack(spacing: 4) {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.title3)
                            .foregroundStyle(.green)
                        Text("No pending tasks")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                }
                .frame(maxHeight: .infinity)
            } else {
                // Show top 4 tasks
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(entry.tasks.prefix(4)) { task in
                        MediumTaskRow(task: task)
                    }
                }

                Spacer(minLength: 0)

                // Remaining count
                let remaining = entry.totalPending - min(4, entry.tasks.count)
                if remaining > 0 {
                    Text("+\(remaining) more tasks")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .containerBackground(.fill.tertiary, for: .widget)
    }
}

struct StatBadge: View {
    let icon: String
    let value: Int
    let color: Color

    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: icon)
                .font(.caption2)
                .foregroundStyle(color)
            Text("\(value)")
                .font(.caption2.bold())
                .foregroundStyle(color)
        }
    }
}

struct MediumTaskRow: View {
    let task: WidgetTask

    var body: some View {
        HStack(spacing: 6) {
            // Priority indicator
            RoundedRectangle(cornerRadius: 1.5)
                .fill(colorForPriority(task.priority))
                .frame(width: 3, height: 14)

            Text(task.text)
                .font(.caption)
                .lineLimit(1)
                .foregroundStyle(task.isOverdue ? .red : .primary)

            Spacer()

            if let project = task.project {
                Text(project)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            if let dueDate = task.dueDate {
                Text(formatDueDate(dueDate))
                    .font(.caption2)
                    .foregroundStyle(task.isOverdue ? .red : .secondary)
            }
        }
    }

    private func colorForPriority(_ priority: String) -> Color {
        switch priority.lowercased() {
        case "critical": return .red
        case "high": return .orange
        case "medium": return .yellow
        case "low": return .green
        default: return .gray
        }
    }

    private func formatDueDate(_ date: Date) -> String {
        if Calendar.current.isDateInToday(date) {
            let formatter = DateFormatter()
            formatter.dateFormat = "h:mm a"
            return formatter.string(from: date)
        } else if Calendar.current.isDateInTomorrow(date) {
            return "Tomorrow"
        } else {
            let formatter = DateFormatter()
            formatter.dateFormat = "MMM d"
            return formatter.string(from: date)
        }
    }
}

// MARK: - Entry View (selects layout based on widget family)

struct TodoWidgetEntryView: View {
    @Environment(\.widgetFamily) var family
    let entry: TaskEntry

    var body: some View {
        switch family {
        case .systemSmall:
            TodoWidgetSmallView(entry: entry)
        case .systemMedium:
            TodoWidgetMediumView(entry: entry)
        default:
            TodoWidgetMediumView(entry: entry)
        }
    }
}

// MARK: - Widget Definition

@main
struct TodoWidget: Widget {
    let kind = "TodoWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: TodoProvider()) { entry in
            TodoWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Todo Tasks")
        .description("View your upcoming tasks and track progress at a glance.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

// MARK: - Previews

#Preview("Small", as: .systemSmall) {
    TodoWidget()
} timeline: {
    TaskEntry.placeholder
    TaskEntry.empty
}

#Preview("Medium", as: .systemMedium) {
    TodoWidget()
} timeline: {
    TaskEntry.placeholder
    TaskEntry.empty
}
