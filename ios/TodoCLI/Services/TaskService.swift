import Foundation
import SwiftUI

@MainActor
class TaskService: ObservableObject {
    @Published var tasks: [TodoTask] = []
    @Published var todayTasks: [TodoTask] = []
    @Published var overdueTasks: [TodoTask] = []
    @Published var isLoading = false
    @Published var error: String?

    private let apiClient: APIClient

    init(apiClient: APIClient) {
        self.apiClient = apiClient
    }

    func loadTasks(project: String? = nil) async {
        isLoading = true
        error = nil

        do {
            let fetched = try await apiClient.fetchTasks(project: project)
            tasks = fetched.sorted { t1, t2 in
                if t1.completed != t2.completed { return !t1.completed }
                if t1.priority != t2.priority { return t1.priority < t2.priority }
                if let d1 = t1.dueDate, let d2 = t2.dueDate { return d1 < d2 }
                if t1.dueDate != nil { return true }
                if t2.dueDate != nil { return false }
                return t1.text < t2.text
            }

            categorizeTasks()
        } catch {
            self.error = error.localizedDescription
        }

        isLoading = false
    }

    func createTask(title: String, description: String? = nil, priority: TaskPriority = .medium, project: String? = nil, dueDate: Date? = nil, tags: [String] = []) async -> Bool {
        let request = TaskCreateRequest(
            title: title,
            description: description,
            priority: priority.rawValue,
            dueDate: dueDate,
            projectId: project,
            tags: tags.isEmpty ? nil : tags
        )

        do {
            _ = try await apiClient.createTask(request)
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.success)
            await loadTasks()
            return true
        } catch {
            self.error = error.localizedDescription
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.error)
            return false
        }
    }

    func toggleTask(_ task: TodoTask) async {
        do {
            _ = try await apiClient.toggleTask(id: task.id)
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.impactOccurred()
            await loadTasks()
        } catch {
            self.error = error.localizedDescription
        }
    }

    func deleteTask(_ task: TodoTask) async {
        do {
            _ = try await apiClient.deleteTask(id: task.id)
            let generator = UIImpactFeedbackGenerator(style: .medium)
            generator.impactOccurred()
            tasks.removeAll { $0.id == task.id }
            categorizeTasks()
        } catch {
            self.error = error.localizedDescription
        }
    }

    func updateTask(_ task: TodoTask, title: String? = nil, priority: TaskPriority? = nil, dueDate: Date? = nil, tags: [String]? = nil) async {
        let request = TaskUpdateRequest(
            title: title,
            priority: priority?.rawValue,
            dueDate: dueDate,
            tags: tags
        )

        do {
            _ = try await apiClient.updateTask(id: task.id, request)
            await loadTasks()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func categorizeTasks() {
        let active = tasks.filter { !$0.completed }
        todayTasks = active.filter { $0.isDueToday }
        overdueTasks = active.filter { $0.isOverdue }
    }
}
