import SwiftUI

struct TaskDetailView: View {
    @EnvironmentObject var apiClient: APIClient
    @EnvironmentObject var themeManager: ThemeManager
    @Environment(\.dismiss) private var dismiss

    let task: TodoTask

    @State private var title: String
    @State private var description: String
    @State private var priority: TaskPriority
    @State private var dueDate: Date?
    @State private var hasDueDate: Bool
    @State private var tags: [String]
    @State private var newTag: String = ""
    @State private var isSaving = false
    @State private var showDeleteConfirm = false

    init(task: TodoTask) {
        self.task = task
        _title = State(initialValue: task.text)
        _description = State(initialValue: task.description ?? "")
        _priority = State(initialValue: task.priority)
        _dueDate = State(initialValue: task.dueDate)
        _hasDueDate = State(initialValue: task.dueDate != nil)
        _tags = State(initialValue: task.tags)
    }

    var body: some View {
        Form {
            // Title Section
            Section {
                TextField("Task title", text: $title, axis: .vertical)
                    .font(.headline)
                    .lineLimit(1...4)

                TextField("Description (optional)", text: $description, axis: .vertical)
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .lineLimit(2...8)
            }

            // Priority Section
            Section("Priority") {
                Picker("Priority", selection: $priority) {
                    ForEach(TaskPriority.allCases, id: \.self) { p in
                        HStack {
                            Circle()
                                .fill(Color.forPriority(p))
                                .frame(width: 10, height: 10)
                            Text(p.displayName)
                        }
                        .tag(p)
                    }
                }
                .pickerStyle(.segmented)
            }

            // Due Date Section
            Section("Due Date") {
                Toggle("Has due date", isOn: $hasDueDate.animation())

                if hasDueDate {
                    DatePicker(
                        "Due date",
                        selection: Binding(
                            get: { dueDate ?? Date() },
                            set: { dueDate = $0 }
                        ),
                        displayedComponents: [.date, .hourAndMinute]
                    )
                    .datePickerStyle(.graphical)
                    .tint(themeManager.accentColor)
                }
            }

            // Tags Section
            Section("Tags") {
                FlowLayout(spacing: 8) {
                    ForEach(tags, id: \.self) { tag in
                        HStack(spacing: 4) {
                            Text(tag)
                                .font(.subheadline)
                            Button {
                                withAnimation {
                                    tags.removeAll { $0 == tag }
                                }
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.caption)
                            }
                        }
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(
                            Capsule()
                                .fill(themeManager.accentColor.opacity(0.15))
                        )
                        .foregroundStyle(themeManager.accentColor)
                    }
                }

                HStack {
                    TextField("Add tag", text: $newTag)
                        .onSubmit { addTag() }

                    Button("Add") { addTag() }
                        .disabled(newTag.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }

            // Status Section
            Section {
                HStack {
                    Text("Status")
                    Spacer()
                    Text(task.completed ? "Completed" : "Active")
                        .foregroundStyle(task.completed ? .statusCompleted : .statusActive)
                        .font(.subheadline.weight(.medium))
                }

                if let created = task.createdAt {
                    HStack {
                        Text("Created")
                        Spacer()
                        Text(created.shortFormatted)
                            .foregroundStyle(.secondary)
                    }
                }

                if let project = task.project {
                    HStack {
                        Text("Project")
                        Spacer()
                        Text(project)
                            .foregroundStyle(.secondary)
                    }
                }
            }

            // Actions
            Section {
                Button {
                    Task { await toggleCompletion() }
                } label: {
                    Label(
                        task.completed ? "Mark as Active" : "Mark as Complete",
                        systemImage: task.completed ? "arrow.uturn.backward.circle" : "checkmark.circle"
                    )
                    .foregroundStyle(task.completed ? .statusActive : .statusCompleted)
                }

                Button(role: .destructive) {
                    showDeleteConfirm = true
                } label: {
                    Label("Delete Task", systemImage: "trash")
                }
            }
        }
        .navigationTitle("Task Details")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Task { await saveChanges() }
                } label: {
                    if isSaving {
                        ProgressView()
                    } else {
                        Text("Save")
                            .font(.body.weight(.semibold))
                    }
                }
                .disabled(title.trimmingCharacters(in: .whitespaces).isEmpty || isSaving)
            }
        }
        .alert("Delete Task", isPresented: $showDeleteConfirm) {
            Button("Cancel", role: .cancel) { }
            Button("Delete", role: .destructive) {
                Task {
                    await deleteTask()
                    dismiss()
                }
            }
        } message: {
            Text("This action cannot be undone.")
        }
    }

    private func addTag() {
        let tag = newTag.trimmingCharacters(in: .whitespaces).lowercased()
        guard !tag.isEmpty, !tags.contains(tag) else { return }
        withAnimation { tags.append(tag) }
        newTag = ""
    }

    private func saveChanges() async {
        isSaving = true
        let request = TaskUpdateRequest(
            title: title,
            description: description.isEmpty ? nil : description,
            priority: priority.rawValue,
            dueDate: hasDueDate ? dueDate : nil,
            tags: tags
        )
        do {
            _ = try await apiClient.updateTask(id: task.id, request)
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.success)
            dismiss()
        } catch {
            // Error handled by apiClient
        }
        isSaving = false
    }

    private func toggleCompletion() async {
        do {
            _ = try await apiClient.toggleTask(id: task.id)
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.impactOccurred()
            dismiss()
        } catch {
            // Error handled by apiClient
        }
    }

    private func deleteTask() async {
        do {
            _ = try await apiClient.deleteTask(id: task.id)
        } catch {
            // Error handled by apiClient
        }
    }
}

// MARK: - Flow Layout for Tags

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrangeSubviews(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrangeSubviews(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(
                at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y),
                proposal: ProposedViewSize(result.sizes[index])
            )
        }
    }

    private func arrangeSubviews(proposal: ProposedViewSize, subviews: Subviews) -> ArrangementResult {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var sizes: [CGSize] = []
        var currentX: CGFloat = 0
        var currentY: CGFloat = 0
        var lineHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentX + size.width > maxWidth && currentX > 0 {
                currentX = 0
                currentY += lineHeight + spacing
                lineHeight = 0
            }
            positions.append(CGPoint(x: currentX, y: currentY))
            sizes.append(size)
            lineHeight = max(lineHeight, size.height)
            currentX += size.width + spacing
        }

        return ArrangementResult(
            positions: positions,
            sizes: sizes,
            size: CGSize(width: maxWidth, height: currentY + lineHeight)
        )
    }

    struct ArrangementResult {
        var positions: [CGPoint]
        var sizes: [CGSize]
        var size: CGSize
    }
}

#Preview {
    NavigationStack {
        TaskDetailView(
            task: TodoTask(
                id: "1",
                text: "Design new landing page",
                description: "Create wireframes and high-fidelity mockups",
                project: "work",
                priority: .high,
                dueDate: Date().addingTimeInterval(86400),
                tags: ["design", "urgent"],
                createdAt: Date().addingTimeInterval(-86400 * 3)
            )
        )
    }
    .environmentObject(APIClient())
    .environmentObject(ThemeManager())
}
