import SwiftUI

struct HomeView: View {
    @EnvironmentObject var apiClient: APIClient
    @EnvironmentObject var themeManager: ThemeManager
    @Binding var showQuickAdd: Bool
    @State private var quickAddText = ""
    @State private var tasks: [TodoTask] = []
    @State private var isLoading = false
    @State private var collapsedSections: Set<String> = []
    @State private var errorMessage: String?

    var todayTasks: [TodoTask] {
        tasks.filter { !$0.completed && $0.isDueToday }
    }

    var overdueTasks: [TodoTask] {
        tasks.filter { !$0.completed && $0.isOverdue }
    }

    var activeTasks: [TodoTask] {
        Array(tasks.filter { !$0.completed }.prefix(10))
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: themeManager.sectionSpacing) {
                    // Quick Add Bar
                    QuickAddBar(text: $quickAddText) {
                        await addQuickTask()
                    }
                    .padding(.horizontal, themeManager.contentPadding)

                    // Today Section
                    if themeManager.showTodaySection {
                        taskSection(
                            title: "Today",
                            icon: "sun.max.fill",
                            iconColor: .statusDueToday,
                            tasks: todayTasks,
                            sectionId: "today"
                        )
                    }

                    // Overdue Section
                    if themeManager.showOverdueSection && !overdueTasks.isEmpty {
                        taskSection(
                            title: "Overdue",
                            icon: "exclamationmark.triangle.fill",
                            iconColor: .statusOverdue,
                            tasks: overdueTasks,
                            sectionId: "overdue"
                        )
                    }

                    // Recent / All Active Section
                    if themeManager.showRecentSection {
                        taskSection(
                            title: "Active Tasks",
                            icon: "list.bullet",
                            iconColor: .statusActive,
                            tasks: activeTasks,
                            sectionId: "recent"
                        )
                    }

                    // Stats summary
                    statsCard

                    Spacer(minLength: 100)
                }
                .padding(.top, 8)
            }
            .refreshable {
                await loadTasks()
            }
            .navigationTitle("Home")
            .navigationBarTitleDisplayMode(.large)
            .task {
                await loadTasks()
            }
        }
    }

    // MARK: - Task Section

    private func taskSection(title: String, icon: String, iconColor: Color, tasks: [TodoTask], sectionId: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Button {
                withAnimation(.easeInOut(duration: 0.25)) {
                    if collapsedSections.contains(sectionId) {
                        collapsedSections.remove(sectionId)
                    } else {
                        collapsedSections.insert(sectionId)
                    }
                }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: icon)
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(iconColor)

                    Text(title)
                        .font(.headline)
                        .foregroundStyle(.primary)

                    Text("\(tasks.count)")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(.quaternary))

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.tertiary)
                        .rotationEffect(.degrees(collapsedSections.contains(sectionId) ? 0 : 90))
                }
                .padding(.horizontal, themeManager.contentPadding)
            }
            .buttonStyle(.plain)

            if !collapsedSections.contains(sectionId) {
                if tasks.isEmpty {
                    EmptyStateView(
                        icon: "checkmark.circle",
                        title: "All clear!",
                        subtitle: "No tasks in this section"
                    )
                    .padding(.horizontal, themeManager.contentPadding)
                } else {
                    LazyVStack(spacing: 2) {
                        ForEach(tasks) { task in
                            TaskRowView(task: task) {
                                await toggleTask(task)
                            } onDelete: {
                                await deleteTask(task)
                            }
                        }
                    }
                    .padding(.horizontal, themeManager.contentPadding)
                    .clipShape(RoundedRectangle(cornerRadius: themeManager.cardCornerRadius, style: .continuous))
                }
            }
        }
    }

    // MARK: - Stats Card

    private var statsCard: some View {
        let total = tasks.count
        let completed = tasks.filter(\.completed).count
        let active = total - completed
        let rate = total > 0 ? Double(completed) / Double(total) : 0

        return VStack(spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "chart.bar.fill")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(themeManager.accentColor)

                Text("Overview")
                    .font(.headline)

                Spacer()
            }

            HStack(spacing: 16) {
                statPill(value: "\(active)", label: "Active", color: .statusActive)
                statPill(value: "\(completed)", label: "Done", color: .statusCompleted)
                statPill(value: "\(Int(rate * 100))%", label: "Rate", color: themeManager.accentColor)
                statPill(value: "\(overdueTasks.count)", label: "Overdue", color: .statusOverdue)
            }
        }
        .padding(themeManager.contentPadding)
        .background(
            RoundedRectangle(cornerRadius: themeManager.cardCornerRadius, style: .continuous)
                .fill(.regularMaterial)
                .shadow(color: .black.opacity(0.06), radius: 2, x: 0, y: 1)
        )
        .padding(.horizontal, themeManager.contentPadding)
    }

    private func statPill(value: String, label: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3.weight(.bold).monospacedDigit())
                .foregroundStyle(color)
            Text(label)
                .font(.caption2.weight(.medium))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Actions

    private func addQuickTask() async {
        let text = quickAddText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }

        let request = TaskCreateRequest(title: text)
        do {
            _ = try await apiClient.createTask(request)
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.success)
            quickAddText = ""
            await loadTasks()
        } catch {
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.error)
        }
    }

    private func loadTasks() async {
        isLoading = true
        do {
            let fetched = try await apiClient.fetchTasks()
            tasks = fetched.sorted { t1, t2 in
                if t1.completed != t2.completed { return !t1.completed }
                if t1.priority != t2.priority { return t1.priority < t2.priority }
                if let d1 = t1.dueDate, let d2 = t2.dueDate { return d1 < d2 }
                if t1.dueDate != nil { return true }
                if t2.dueDate != nil { return false }
                return t1.text < t2.text
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    private func toggleTask(_ task: TodoTask) async {
        do {
            _ = try await apiClient.toggleTask(id: task.id)
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.impactOccurred()
            await loadTasks()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func deleteTask(_ task: TodoTask) async {
        do {
            _ = try await apiClient.deleteTask(id: task.id)
            let generator = UIImpactFeedbackGenerator(style: .medium)
            generator.impactOccurred()
            tasks.removeAll { $0.id == task.id }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

#Preview {
    HomeView(showQuickAdd: .constant(false))
        .environmentObject(ThemeManager())
        .environmentObject(APIClient())
}
