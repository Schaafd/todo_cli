import SwiftUI

struct TaskListView: View {
    @EnvironmentObject var apiClient: APIClient
    @EnvironmentObject var themeManager: ThemeManager
    @EnvironmentObject var offlineManager: OfflineManager
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
                // Offline Banner
                if offlineManager.isOffline {
                    offlineBanner
                }

                // Filter chips
                filterBar

                // Task list
                if isLoading && tasks.isEmpty {
                    ScrollView {
                        VStack(spacing: 2) {
                            ForEach(0..<6, id: \.self) { _ in
                                TaskRowSkeleton()
                            }
                        }
                        .padding(.horizontal, themeManager.contentPadding)
                        .padding(.top, 8)
                    }
                    .transition(.opacity)
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
                    ZStack(alignment: .topTrailing) {
                        Button {
                            showCreateSheet = true
                        } label: {
                            Image(systemName: "plus")
                        }

                        if offlineManager.pendingChangesCount > 0 {
                            Text("\(offlineManager.pendingChangesCount)")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(.white)
                                .frame(width: 16, height: 16)
                                .background(Circle().fill(.orange))
                                .offset(x: 6, y: -6)
                        }
                    }
                }
            }
            .sheet(isPresented: $showCreateSheet) {
                TaskCreateView()
                    .environmentObject(apiClient)
                    .environmentObject(themeManager)
            }
            .alert("Error", isPresented: .constant(errorMessage != nil)) {
                Button("OK") { errorMessage = nil }
            } message: {
                Text(errorMessage ?? "An unknown error occurred.")
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

    // MARK: - Offline Banner

    private var offlineBanner: some View {
        HStack(spacing: 8) {
            Image(systemName: "wifi.slash")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.white)

            Text("Offline mode")
                .font(.caption.weight(.medium))
                .foregroundStyle(.white)

            Spacer()

            if offlineManager.pendingChangesCount > 0 {
                Text("\(offlineManager.pendingChangesCount) pending")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(.white.opacity(0.9))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(.white.opacity(0.2)))
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.orange)
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
            // Cache for offline use
            offlineManager.cacheTasks(tasks)
        } catch {
            // Fall back to cached data when offline
            let cached = offlineManager.getCachedTasks()
            if !cached.isEmpty {
                tasks = cached
                errorMessage = "Showing cached data (offline)"
            } else {
                errorMessage = error.localizedDescription
            }
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
            if offlineManager.isOffline {
                offlineManager.queueChange(.toggleComplete(taskId: task.id))
                if let index = tasks.firstIndex(where: { $0.id == task.id }) {
                    tasks[index].completed.toggle()
                }
            } else {
                errorMessage = error.localizedDescription
            }
        }
    }

    private func deleteTask(_ task: TodoTask) async {
        do {
            _ = try await apiClient.deleteTask(id: task.id)
            let generator = UIImpactFeedbackGenerator(style: .medium)
            generator.impactOccurred()
            tasks.removeAll { $0.id == task.id }
        } catch {
            if offlineManager.isOffline {
                offlineManager.queueChange(.delete(taskId: task.id))
                tasks.removeAll { $0.id == task.id }
            } else {
                errorMessage = error.localizedDescription
            }
        }
    }
}

#Preview {
    TaskListView()
        .environmentObject(APIClient())
        .environmentObject(ThemeManager())
        .environmentObject(OfflineManager())
}
