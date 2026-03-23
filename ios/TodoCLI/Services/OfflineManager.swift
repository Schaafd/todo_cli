import Foundation
import CoreData
import Network
import Combine

/// Represents a pending change that needs to be synced when connectivity is restored.
enum PendingChange: Codable {
    case create(task: TodoTask)
    case update(task: TodoTask)
    case delete(taskId: String)
    case toggleComplete(taskId: String)

    // MARK: - Codable

    enum CodingKeys: String, CodingKey {
        case type, task, taskId
    }

    enum ChangeType: String, Codable {
        case create, update, delete, toggleComplete
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        switch self {
        case .create(let task):
            try container.encode(ChangeType.create, forKey: .type)
            try container.encode(task, forKey: .task)
        case .update(let task):
            try container.encode(ChangeType.update, forKey: .type)
            try container.encode(task, forKey: .task)
        case .delete(let taskId):
            try container.encode(ChangeType.delete, forKey: .type)
            try container.encode(taskId, forKey: .taskId)
        case .toggleComplete(let taskId):
            try container.encode(ChangeType.toggleComplete, forKey: .type)
            try container.encode(taskId, forKey: .taskId)
        }
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(ChangeType.self, forKey: .type)
        switch type {
        case .create:
            let task = try container.decode(TodoTask.self, forKey: .task)
            self = .create(task: task)
        case .update:
            let task = try container.decode(TodoTask.self, forKey: .task)
            self = .update(task: task)
        case .delete:
            let taskId = try container.decode(String.self, forKey: .taskId)
            self = .delete(taskId: taskId)
        case .toggleComplete:
            let taskId = try container.decode(String.self, forKey: .taskId)
            self = .toggleComplete(taskId: taskId)
        }
    }

    /// The change type as a string for CoreData storage.
    var changeTypeString: String {
        switch self {
        case .create: return "create"
        case .update: return "update"
        case .delete: return "delete"
        case .toggleComplete: return "toggleComplete"
        }
    }
}

@MainActor
class OfflineManager: ObservableObject {
    @Published var isOffline: Bool = false
    @Published var pendingChangesCount: Int = 0

    private let coreDataStack: CoreDataStack
    private let monitor: NWPathMonitor
    private let monitorQueue = DispatchQueue(label: "com.todocli.networkmonitor")
    private var cancellables = Set<AnyCancellable>()

    init(coreDataStack: CoreDataStack = .shared) {
        self.coreDataStack = coreDataStack
        self.monitor = NWPathMonitor()
        updatePendingChangesCount()
    }

    deinit {
        monitor.cancel()
    }

    // MARK: - Network Monitoring

    func startMonitoring() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor [weak self] in
                guard let self = self else { return }
                let wasOffline = self.isOffline
                self.isOffline = (path.status != .satisfied)

                // If we just came back online, trigger a sync
                if wasOffline && !self.isOffline {
                    // Caller should invoke syncPendingChanges after detecting this change
                    NotificationCenter.default.post(name: .connectivityRestored, object: nil)
                }
            }
        }
        monitor.start(queue: monitorQueue)
    }

    func stopMonitoring() {
        monitor.cancel()
    }

    // MARK: - Cache Tasks

    /// Caches tasks from an API response into CoreData for offline access.
    func cacheTasks(_ tasks: [TodoTask]) {
        let context = coreDataStack.viewContext

        // Delete existing cached tasks
        let fetchRequest: NSFetchRequest<NSFetchRequestResult> = CachedTask.fetchRequest()
        let deleteRequest = NSBatchDeleteRequest(fetchRequest: fetchRequest)
        do {
            try context.execute(deleteRequest)
        } catch {
            print("Failed to clear cached tasks: \(error)")
        }

        // Insert new cached tasks
        for task in tasks {
            let cachedTask = CachedTask(context: context)
            cachedTask.update(from: task)
        }

        coreDataStack.saveContext()
    }

    // MARK: - Get Cached Tasks

    /// Returns cached tasks for offline display.
    func getCachedTasks() -> [TodoTask] {
        let context = coreDataStack.viewContext
        let fetchRequest: NSFetchRequest<CachedTask> = CachedTask.fetchRequest()
        fetchRequest.sortDescriptors = [
            NSSortDescriptor(key: "completed", ascending: true),
            NSSortDescriptor(key: "priority", ascending: true),
            NSSortDescriptor(key: "dueDate", ascending: true),
        ]

        do {
            let cached = try context.fetch(fetchRequest)
            return cached.map { $0.toTodoTask() }
        } catch {
            print("Failed to fetch cached tasks: \(error)")
            return []
        }
    }

    // MARK: - Queue Changes

    /// Queues a change for later sync when connectivity is restored.
    func queueChange(_ change: PendingChange) {
        let context = coreDataStack.viewContext

        let entity = PendingChangeEntity(context: context)
        entity.changeId = UUID()
        entity.changeType = change.changeTypeString
        entity.createdAt = Date()

        do {
            let data = try JSONEncoder().encode(change)
            entity.payloadJSON = String(data: data, encoding: .utf8) ?? "{}"
        } catch {
            print("Failed to encode pending change: \(error)")
            return
        }

        coreDataStack.saveContext()
        updatePendingChangesCount()

        // Also update local cache for immediate UI feedback
        applyChangeToCache(change)
    }

    /// Applies a pending change to the local cache so the UI stays consistent.
    private func applyChangeToCache(_ change: PendingChange) {
        let context = coreDataStack.viewContext

        switch change {
        case .create(let task):
            let cachedTask = CachedTask(context: context)
            cachedTask.update(from: task)

        case .update(let task):
            let fetchRequest: NSFetchRequest<CachedTask> = CachedTask.fetchRequest()
            fetchRequest.predicate = NSPredicate(format: "taskId == %@", task.id)
            if let existing = try? context.fetch(fetchRequest).first {
                existing.update(from: task)
            }

        case .delete(let taskId):
            let fetchRequest: NSFetchRequest<CachedTask> = CachedTask.fetchRequest()
            fetchRequest.predicate = NSPredicate(format: "taskId == %@", taskId)
            if let existing = try? context.fetch(fetchRequest).first {
                context.delete(existing)
            }

        case .toggleComplete(let taskId):
            let fetchRequest: NSFetchRequest<CachedTask> = CachedTask.fetchRequest()
            fetchRequest.predicate = NSPredicate(format: "taskId == %@", taskId)
            if let existing = try? context.fetch(fetchRequest).first {
                existing.completed.toggle()
            }
        }

        coreDataStack.saveContext()
    }

    // MARK: - Sync Pending Changes

    /// Syncs all pending changes with the server when connectivity is restored.
    func syncPendingChanges(apiClient: APIClient) async {
        let context = coreDataStack.viewContext
        let fetchRequest: NSFetchRequest<PendingChangeEntity> = PendingChangeEntity.fetchRequest()
        fetchRequest.sortDescriptors = [NSSortDescriptor(key: "createdAt", ascending: true)]

        guard let pendingEntities = try? context.fetch(fetchRequest), !pendingEntities.isEmpty else {
            return
        }

        for entity in pendingEntities {
            guard let data = entity.payloadJSON.data(using: .utf8),
                  let change = try? JSONDecoder().decode(PendingChange.self, from: data) else {
                // Remove corrupted entries
                context.delete(entity)
                continue
            }

            do {
                try await applyChangeToServer(change, apiClient: apiClient)
                // Remove successfully synced change
                context.delete(entity)
                coreDataStack.saveContext()
                updatePendingChangesCount()
            } catch {
                // Stop syncing on first failure (likely still offline or server issue)
                print("Sync failed for change \(entity.changeId): \(error)")
                break
            }
        }
    }

    private func applyChangeToServer(_ change: PendingChange, apiClient: APIClient) async throws {
        switch change {
        case .create(let task):
            let request = TaskCreateRequest(
                title: task.text,
                description: task.description,
                priority: task.priority.rawValue,
                dueDate: task.dueDate,
                projectId: task.project,
                tags: task.tags.isEmpty ? nil : task.tags
            )
            _ = try await apiClient.createTask(request)

        case .update(let task):
            let request = TaskUpdateRequest(
                title: task.text,
                description: task.description,
                priority: task.priority.rawValue,
                dueDate: task.dueDate,
                tags: task.tags.isEmpty ? nil : task.tags,
                completed: task.completed
            )
            _ = try await apiClient.updateTask(id: task.id, request)

        case .delete(let taskId):
            _ = try await apiClient.deleteTask(id: taskId)

        case .toggleComplete(let taskId):
            _ = try await apiClient.toggleTask(id: taskId)
        }
    }

    // MARK: - Helpers

    private func updatePendingChangesCount() {
        let context = coreDataStack.viewContext
        let fetchRequest: NSFetchRequest<PendingChangeEntity> = PendingChangeEntity.fetchRequest()
        pendingChangesCount = (try? context.count(for: fetchRequest)) ?? 0
    }

    /// Clears all pending changes (e.g., after a full sync or user request).
    func clearPendingChanges() {
        let context = coreDataStack.viewContext
        let fetchRequest: NSFetchRequest<NSFetchRequestResult> = PendingChangeEntity.fetchRequest()
        let deleteRequest = NSBatchDeleteRequest(fetchRequest: fetchRequest)
        do {
            try context.execute(deleteRequest)
            coreDataStack.saveContext()
            updatePendingChangesCount()
        } catch {
            print("Failed to clear pending changes: \(error)")
        }
    }
}

// MARK: - Notification Name

extension Notification.Name {
    static let connectivityRestored = Notification.Name("com.todocli.connectivityRestored")
}
