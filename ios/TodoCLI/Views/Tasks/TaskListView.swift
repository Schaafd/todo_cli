import SwiftUI

struct TaskListView: View {
    @EnvironmentObject var apiClient: APIClient
    @EnvironmentObject var themeManager: ThemeManager
    @State private var tasks: [TodoTask] = []
    @State private var isLoading = false
    @State private var searchText = ""
    @State private var selectedFilter: TaskFilter = .all
    @State private var selectedPriority: TaskPriority?
    @State private var showCreateSheet = false
    @State private var errorMessage: String?

    enum TaskFilter: String, CaseIterable {
        case all = "All"
        case active = "Active"
        case completed = "Completed"
        case overdue = "Overdue"
        case today = "Today"
    }

    var filteredTasks: [TodoTask] {
        var result = tasks

        // Apply status filter
        switch selectedFilter {
        case .all: break
        case .active: result = result.filter { !$0.completed }
        case .completed: result = result.filter { $0.completed }
        case .overdue: result = result.filter { $0.isOverdue }
        case .today: result = result.filter { $0.isDueToday }
        }

        // Apply priority filter
        if let priority = selectedPriority {
            result = result.filter { $0.priority == priority }
        }

        // Apply search
        if !searchText.isEmpty {
            let query = searchText.lowercased()
            result = result.filter {
                $0.text.lowercased().contains(query)
                || $0.tags.contains { $0.lowercased().contains(query) }
                || ($0.project?.lowercased().contains(query) ?? false)
            }
        }

        return result
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Filter chips
                filterBar

                // Task list
                if isLoading && tasks.isEmpty {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if filteredTasks.isEmpty {
                    emptyState
                } else {
                    taskList
                }
            }
            .navigationTitle("Tasks")
            .navigationBarTitleDisplayMode(.large)
            .searchable(text: $searchText, prompt: "Search tasks...")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showCreateSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showCreateSheet) {
                TaskCreateView()
                    .environmentObject(apiClient)
                    .environmentObject(themeManager)
            }
            .refreshable {
                await loadTasks()
            }
            .task {
                await loadTasks()
            }
            .onChange(of: showCreateSheet) { _, isShowing in
                if !isShowing {
                    Task { await loadTasks() }
                }
            }
        }
    }

    // MARK: - Filter Bar

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(TaskFilter.allCases, id: \.self) { filter in
                    filterChip(filter.rawValue, isSelected: selectedFilter == filter) {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            selectedFilter = filter
                        }
                    }
                }

                Divider()
                    .frame(height: 20)

                ForEach(TaskPriority.allCases, id: \.self) { priority in
                    filterChip(priority.displayName, isSelected: selectedPriority == priority, color: .forPriority(priority)) {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            selectedPriority = selectedPriority == priority ? nil : priority
                        }
                    }
                }
            }
            .padding(.horizontal, themeManager.contentPadding)
            .padding(.vertical, 8)
        }
        .background(.bar)
    }

    private func filterChip(_ label: String, isSelected: Bool, color: Color? = nil, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(.subheadline.weight(isSelected ? .semibold : .regular))
                .foregroundStyle(isSelected ? .white : .primary)
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .background(
                    Capsule()
                        .fill(isSelected ? (color ?? themeManager.accentColor) : Color(.systemGray6))
                )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Task List

    private var taskList: some View {
        ScrollView {
            LazyVStack(spacing: 2) {
                ForEach(filteredTasks) { task in
                    NavigationLink {
                        TaskDetailView(task: task)
                    } label: {
                        TaskRowView(task: task) {
                            await toggleTask(task)
                        } onDelete: {
                            await deleteTask(task)
                        }
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, themeManager.contentPadding)
            .padding(.top, 8)
            .padding(.bottom, 100)
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack {
            Spacer()
            if searchText.isEmpty {
                EmptyStateView(
                    icon: "checklist",
                    title: "No tasks yet",
                    subtitle: "Tap + to create your first task"
                )
            } else {
                EmptyStateView(
                    icon: "magnifyingglass",
                    title: "No results",
                    subtitle: "Try a different search term"
                )
            }
            Spacer()
        }
    }

    // MARK: - Actions

    private func loadTasks() async {
        isLoading = true
        do {
            tasks = try await apiClient.fetchTasks()
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
    TaskListView()
        .environmentObject(APIClient())
        .environmentObject(ThemeManager())
}
