import SwiftUI

struct TaskRowView: View {
    @EnvironmentObject var themeManager: ThemeManager
    let task: TodoTask
    var onToggle: (() async -> Void)?
    var onDelete: (() async -> Void)?

    @State private var checkScale: CGFloat = 1.0
    @State private var isCompleting = false

    var body: some View {
        HStack(spacing: 12) {
            // Priority indicator bar
            RoundedRectangle(cornerRadius: 2)
                .fill(Color.forPriority(task.priority))
                .frame(width: 4)
                .frame(maxHeight: .infinity)
                .padding(.vertical, 4)

            // Completion toggle
            Button {
                Task {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.5)) {
                        checkScale = 0.8
                        isCompleting = true
                    }
                    await onToggle?()
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.5)) {
                        checkScale = 1.0
                        isCompleting = false
                    }
                }
            } label: {
                ZStack {
                    Circle()
                        .strokeBorder(
                            task.completed ? Color.statusCompleted : Color(.systemGray3),
                            lineWidth: 2
                        )
                        .frame(
                            width: themeManager.listDensity.iconSize,
                            height: themeManager.listDensity.iconSize
                        )

                    if task.completed {
                        Circle()
                            .fill(Color.statusCompleted)
                            .frame(
                                width: themeManager.listDensity.iconSize - 4,
                                height: themeManager.listDensity.iconSize - 4
                            )

                        Image(systemName: "checkmark")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(.white)
                    }
                }
                .scaleEffect(checkScale)
            }
            .buttonStyle(.plain)

            // Task content
            VStack(alignment: .leading, spacing: 4) {
                Text(task.text)
                    .font(.body.weight(task.completed ? .regular : .medium))
                    .foregroundStyle(task.completed ? .secondary : .primary)
                    .strikethrough(task.completed, color: .secondary)
                    .lineLimit(2)

                HStack(spacing: 8) {
                    // Due date
                    if let dueDate = task.dueDate {
                        HStack(spacing: 3) {
                            Image(systemName: "calendar")
                                .font(.caption2)
                            Text(dueDate.relativeDescription)
                                .font(.caption)
                        }
                        .foregroundStyle(dueDateColor(dueDate))
                    }

                    // Project
                    if let project = task.project, !project.isEmpty {
                        HStack(spacing: 3) {
                            Image(systemName: "folder.fill")
                                .font(.caption2)
                            Text(project)
                                .font(.caption)
                        }
                        .foregroundStyle(.secondary)
                    }

                    // Tags
                    if !task.tags.isEmpty {
                        HStack(spacing: 4) {
                            ForEach(task.tags.prefix(2), id: \.self) { tag in
                                TagChip(text: tag)
                            }
                            if task.tags.count > 2 {
                                Text("+\(task.tags.count - 2)")
                                    .font(.caption2.weight(.medium))
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }

            Spacer(minLength: 4)

            // Priority badge (compact)
            PriorityBadge(priority: task.priority)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, themeManager.listDensity.verticalPadding)
        .background(
            RoundedRectangle(cornerRadius: themeManager.cardCornerRadius, style: .continuous)
                .fill(.regularMaterial)
        )
        .swipeActions(edge: .trailing, allowsFullSwipe: true) {
            Button {
                Task { await onToggle?() }
            } label: {
                Label(task.completed ? "Undo" : "Complete", systemImage: task.completed ? "arrow.uturn.backward" : "checkmark")
            }
            .tint(.statusCompleted)
        }
        .swipeActions(edge: .leading, allowsFullSwipe: true) {
            Button(role: .destructive) {
                Task { await onDelete?() }
            } label: {
                Label("Delete", systemImage: "trash")
            }
        }
        .opacity(task.completed ? 0.7 : 1.0)
    }

    private func dueDateColor(_ date: Date) -> Color {
        if task.completed { return .secondary }
        if date < Date() { return .statusOverdue }
        if date.isToday { return .statusDueToday }
        return .secondary
    }
}

#Preview {
    VStack(spacing: 4) {
        TaskRowView(
            task: TodoTask(
                id: "1",
                text: "Design new landing page for product launch",
                project: "work",
                priority: .high,
                dueDate: Date(),
                tags: ["design", "urgent"]
            )
        )
        TaskRowView(
            task: TodoTask(
                id: "2",
                text: "Buy groceries",
                completed: true,
                priority: .low,
                tags: ["personal"]
            )
        )
        TaskRowView(
            task: TodoTask(
                id: "3",
                text: "Fix critical bug in auth flow",
                priority: .critical,
                dueDate: Date().addingTimeInterval(-86400),
                tags: ["bug"]
            )
        )
    }
    .padding()
    .environmentObject(ThemeManager())
}
