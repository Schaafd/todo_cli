import SwiftUI

struct TaskCreateView: View {
    @EnvironmentObject var apiClient: APIClient
    @EnvironmentObject var themeManager: ThemeManager
    @Environment(\.dismiss) private var dismiss

    @State private var title = ""
    @State private var description = ""
    @State private var priority: TaskPriority = .medium
    @State private var project: String = ""
    @State private var hasDueDate = false
    @State private var dueDate = Date()
    @State private var tagInput = ""
    @State private var tags: [String] = []
    @State private var isCreating = false
    @State private var projects: [Project] = []

    @FocusState private var titleFocused: Bool

    var body: some View {
        NavigationStack {
            Form {
                // Title - most prominent
                Section {
                    TextField("What needs to be done?", text: $title, axis: .vertical)
                        .font(.title3.weight(.medium))
                        .lineLimit(1...3)
                        .focused($titleFocused)

                    TextField("Add notes (optional)", text: $description, axis: .vertical)
                        .font(.body)
                        .foregroundStyle(.secondary)
                        .lineLimit(1...5)
                }

                // Quick options
                Section("Options") {
                    // Priority picker
                    HStack {
                        Label("Priority", systemImage: "flag.fill")
                            .foregroundStyle(.primary)
                        Spacer()
                        Picker("Priority", selection: $priority) {
                            ForEach(TaskPriority.allCases, id: \.self) { p in
                                Text(p.displayName).tag(p)
                            }
                        }
                        .pickerStyle(.segmented)
                        .frame(maxWidth: 240)
                    }

                    // Project picker
                    if !projects.isEmpty {
                        Picker(selection: $project) {
                            Text("Inbox").tag("")
                            ForEach(projects) { proj in
                                Text(proj.name).tag(proj.id)
                            }
                        } label: {
                            Label("Project", systemImage: "folder.fill")
                        }
                    }

                    // Due date
                    Toggle(isOn: $hasDueDate.animation()) {
                        Label("Due date", systemImage: "calendar")
                    }

                    if hasDueDate {
                        DatePicker(
                            "Due",
                            selection: $dueDate,
                            displayedComponents: [.date, .hourAndMinute]
                        )
                        .tint(themeManager.accentColor)

                        // Quick date buttons
                        HStack(spacing: 8) {
                            quickDateButton("Today", date: Date())
                            quickDateButton("Tomorrow", date: Calendar.current.date(byAdding: .day, value: 1, to: Date())!)
                            quickDateButton("Next Week", date: Calendar.current.date(byAdding: .weekOfYear, value: 1, to: Date())!)
                        }
                    }
                }

                // Tags
                Section("Tags") {
                    if !tags.isEmpty {
                        FlowLayout(spacing: 8) {
                            ForEach(tags, id: \.self) { tag in
                                HStack(spacing: 4) {
                                    Text(tag)
                                        .font(.subheadline)
                                    Button {
                                        withAnimation { tags.removeAll { $0 == tag } }
                                    } label: {
                                        Image(systemName: "xmark.circle.fill")
                                            .font(.caption)
                                    }
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(
                                    Capsule().fill(themeManager.accentColor.opacity(0.15))
                                )
                                .foregroundStyle(themeManager.accentColor)
                            }
                        }
                    }

                    HStack {
                        TextField("Add tag", text: $tagInput)
                            .onSubmit { addTag() }
                        Button("Add") { addTag() }
                            .disabled(tagInput.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                }
            }
            .navigationTitle("New Task")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await createTask() }
                    } label: {
                        if isCreating {
                            ProgressView()
                        } else {
                            Text("Create")
                                .font(.body.weight(.semibold))
                        }
                    }
                    .disabled(title.trimmingCharacters(in: .whitespaces).isEmpty || isCreating)
                }
            }
            .task {
                titleFocused = true
                await loadProjects()
            }
        }
    }

    private func quickDateButton(_ label: String, date: Date) -> some View {
        Button {
            dueDate = date
            let generator = UISelectionFeedbackGenerator()
            generator.selectionChanged()
        } label: {
            Text(label)
                .font(.caption.weight(.medium))
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(
                    Capsule()
                        .fill(Calendar.current.isDate(dueDate, inSameDayAs: date)
                            ? themeManager.accentColor
                            : Color(.systemGray6))
                )
                .foregroundStyle(Calendar.current.isDate(dueDate, inSameDayAs: date) ? .white : .primary)
        }
        .buttonStyle(.plain)
    }

    private func addTag() {
        let tag = tagInput.trimmingCharacters(in: .whitespaces).lowercased()
        guard !tag.isEmpty, !tags.contains(tag) else { return }
        withAnimation { tags.append(tag) }
        tagInput = ""
    }

    private func loadProjects() async {
        do {
            projects = try await apiClient.fetchProjects()
        } catch {
            // Silently fail - projects picker just won't show
        }
    }

    private func createTask() async {
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedTitle.isEmpty else { return }

        isCreating = true

        let request = TaskCreateRequest(
            title: trimmedTitle,
            description: description.isEmpty ? nil : description,
            priority: priority.rawValue,
            dueDate: hasDueDate ? dueDate : nil,
            projectId: project.isEmpty ? nil : project,
            tags: tags.isEmpty ? nil : tags
        )

        do {
            _ = try await apiClient.createTask(request)
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.success)
            dismiss()
        } catch {
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.error)
        }

        isCreating = false
    }
}

#Preview {
    TaskCreateView()
        .environmentObject(APIClient())
        .environmentObject(ThemeManager())
}
