import CoreData
import Foundation

@objc(CachedTask)
public class CachedTask: NSManagedObject {
    @NSManaged public var taskId: String
    @NSManaged public var text: String
    @NSManaged public var taskDescription: String?
    @NSManaged public var project: String?
    @NSManaged public var status: String?
    @NSManaged public var completed: Bool
    @NSManaged public var priority: String?
    @NSManaged public var dueDate: Date?
    @NSManaged public var createdAt: Date?
    @NSManaged public var tagsJSON: String?
    @NSManaged public var lastSyncedAt: Date?
}

extension CachedTask {
    var tags: [String] {
        get {
            guard let json = tagsJSON,
                  let data = json.data(using: .utf8),
                  let array = try? JSONDecoder().decode([String].self, from: data) else {
                return []
            }
            return array
        }
        set {
            if let data = try? JSONEncoder().encode(newValue),
               let json = String(data: data, encoding: .utf8) {
                tagsJSON = json
            } else {
                tagsJSON = nil
            }
        }
    }

    /// Converts this CachedTask into a TodoTask model object.
    func toTodoTask() -> TodoTask {
        return TodoTask(
            id: taskId,
            text: text,
            description: taskDescription,
            project: project,
            status: status ?? "pending",
            completed: completed,
            priority: TaskPriority(rawValue: priority ?? "medium") ?? .medium,
            dueDate: dueDate,
            tags: tags,
            createdAt: createdAt
        )
    }

    /// Updates this CachedTask from a TodoTask model object.
    func update(from task: TodoTask) {
        taskId = task.id
        text = task.text
        taskDescription = task.description
        project = task.project
        status = task.status
        completed = task.completed
        priority = task.priority.rawValue
        dueDate = task.dueDate
        createdAt = task.createdAt
        tags = task.tags
        lastSyncedAt = Date()
    }

    @nonobjc public class func fetchRequest() -> NSFetchRequest<CachedTask> {
        return NSFetchRequest<CachedTask>(entityName: "CachedTask")
    }
}

// MARK: - PendingChangeEntity

@objc(PendingChangeEntity)
public class PendingChangeEntity: NSManagedObject {
    @NSManaged public var changeId: UUID
    @NSManaged public var changeType: String
    @NSManaged public var payloadJSON: String
    @NSManaged public var createdAt: Date

    @nonobjc public class func fetchRequest() -> NSFetchRequest<PendingChangeEntity> {
        return NSFetchRequest<PendingChangeEntity>(entityName: "PendingChangeEntity")
    }
}
