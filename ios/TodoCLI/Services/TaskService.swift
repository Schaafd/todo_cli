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
    private var offlineManager: OfflineManager?
    private weak var pushNotificationManager: PushNotificationManager?

    init(apiClient: APIClient, offlineManager: OfflineManager? = nil, pushNotificationManager: PushNotificationManager? = nil) {
        self.apiClient = apiClient
        self.offlineManager = offlineManager
        self.pushNotificationManager = pushNotificationManager
    }

    func setOfflineManager(_ manager: OfflineManager) {
        self.offlineManager = manager
    }

    func setPushNotificationManager(_ manager: PushNotificationManager) {
        self.pushNotificationManager = manager
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

            // Cache tasks for offline use
            offlineManager?.cacheTasks(tasks)
            categorizeTasks()
        } catch {
            // If offline, return cached data
            if let offlineManager = offlineManager {
                let cached = offlineManager.getCachedTasks()
                if !cached.isEmpty {
                    tasks = cached
                    categorizeTasks()
                    self.error = "Showing cached data (offline)"
                } else {
                    self.error = error.localizedDescription
                }
            } else {
                self.error = error.localizedDescription
            }
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
            let response = try await apiClient.createTask(request)
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.success)

            // Schedule a reminder notification if the task has a due date
            if let dueDate = dueDate {
                let taskId = response.taskId ?? response.task?.id ?? ""
                if !taskId.isEmpty {
                    pushNotificationManager?.scheduleTaskReminder(
                        taskId: taskId,
                        title: title,
                        dueDate: dueDate
                    )
                }
            }

            await loadTasks()
            return true
        } catch {
            // If offline, queue the change
            if let offlineManager = offlineManager, offlineManager.isOffline {
                let task = TodoTask(
                    id: UUID().uuidString,
                    text: title,
                    description: description,
                    project: project,
                    priority: priority,
                    dueDate: dueDate,
                    tags: tags,
                    createdAt: Date()
                )
                offlineManager.queueChange(.create(task: task))
                tasks.append(task)
                categorizeTasks()

                // Schedule reminder even when offline (local notification)
                if let dueDate = dueDate {
                    pushNotificationManager?.scheduleTaskReminder(
                        taskId: task.id,
                        title: title,
                        dueDate: dueDate
                    )
                }

                let generator = UINotificationFeedbackGenerator()
                generator.notificationOccurred(.success)
                return true
            }

            self.error = error.localizedDescription
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.error)
            return false
        }
    }

    func toggleTask(_ task: TodoTask) async {
        do {
            let response = try await apiClient.toggleTask(id: task.id)
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.impactOccurred()

            // If the task was just completed, cancel its reminder.
            // If it was uncompleted and has a due date, reschedule.
            if response.completed {
                pushNotificationManager?.cancelTaskReminder(taskId: task.id)
            } else if let dueDate = task.dueDate {
                pushNotificationManager?.scheduleTaskReminder(
                    taskId: task.id,
                    title: task.text,
                    dueDate: dueDate
                )
            }

            await loadTasks()
        } catch {
            // If offline, queue the change
            if let offlineManager = offlineManager, offlineManager.isOffline {
                offlineManager.queueChange(.toggleComplete(taskId: task.id))
                if let index = tasks.firstIndex(where: { $0.id == task.id }) {
                    let willBeCompleted = !tasks[index].completed
                    tasks[index].completed.toggle()
                    categorizeTasks()

                    if willBeCompleted {
                        pushNotificationManager?.cancelTaskReminder(taskId: task.id)
                    } else if let dueDate = task.dueDate {
                        pushNotificationManager?.scheduleTaskReminder(
                            taskId: task.id,
                            title: task.text,
                            dueDate: dueDate
                        )
                    }
                }
                let generator = UIImpactFeedbackGenerator(style: .light)
                generator.impactOccurred()
                return
            }
            self.error = error.localizedDescription
        }
    }

    func deleteTask(_ task: TodoTask) async {
        do {
            _ = try await apiClient.deleteTask(id: task.id)
            let generator = UIImpactFeedbackGenerator(style: .medium)
            generator.impactOccurred()

            // Cancel any scheduled reminder for the deleted task
            pushNotificationManager?.cancelTaskReminder(taskId: task.id)

            tasks.removeAll { $0.id == task.id }
            categorizeTasks()
        } catch {
            // If offline, queue the change
            if let offlineManager = offlineManager, offlineManager.isOffline {
                offlineManager.queueChange(.delete(taskId: task.id))

                // Cancel the reminder even when offline
                pushNotificationManager?.cancelTaskReminder(taskId: task.id)

                tasks.removeAll { $0.id == task.id }
                categorizeTasks()
                let generator = UIImpactFeedbackGenerator(style: .medium)
                generator.impactOccurred()
                return
            }
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

            // If the due date changed, update the reminder notification
            if let newDueDate = dueDate {
                pushNotificationManager?.cancelTaskReminder(taskId: task.id)
                pushNotificationManager?.scheduleTaskReminder(
                    taskId: task.id,
                    title: title ?? task.text,
                    dueDate: newDueDate
                )
            }

            await loadTasks()
        } catch {
            // If offline, queue the change
            if let offlineManager = offlineManager, offlineManager.isOffline {
                var updatedTask = task
                if let title = title { updatedTask.text = title }
                if let priority = priority { updatedTask.priority = priority }
                if let dueDate = dueDate { updatedTask.dueDate = dueDate }
                if let tags = tags { updatedTask.tags = tags }
                offlineManager.queueChange(.update(task: updatedTask))
                if let index = tasks.firstIndex(where: { $0.id == task.id }) {
                    tasks[index] = updatedTask
                    categorizeTasks()
                }

                // Update reminder even when offline
                if let newDueDate = dueDate {
                    pushNotificationManager?.cancelTaskReminder(taskId: task.id)
                    pushNotificationManager?.scheduleTaskReminder(
                        taskId: task.id,
                        title: title ?? task.text,
                        dueDate: newDueDate
                    )
                }

                return
            }
            self.error = error.localizedDescription
        }
    }

    /// Syncs any pending offline changes when connectivity is restored.
    func syncPendingChanges() async {
        guard let offlineManager = offlineManager else { return }
        await offlineManager.syncPendingChanges(apiClient: apiClient)
        // Reload fresh data from server
        await loadTasks()
    }

    private func categorizeTasks() {
        let active = tasks.filter { !$0.completed }
        todayTasks = active.filter { $0.isDueToday }
        overdueTasks = active.filter { $0.isOverdue }
    }
}
