import CoreData

class CoreDataStack {
    static let shared = CoreDataStack()

    lazy var persistentContainer: NSPersistentContainer = {
        let model = Self.createManagedObjectModel()
        let container = NSPersistentContainer(name: "TodoCLI", managedObjectModel: model)
        container.loadPersistentStores { storeDescription, error in
            if let error = error as NSError? {
                print("CoreData error: \(error), \(error.userInfo)")
            }
        }
        container.viewContext.automaticallyMergesChangesFromParent = true
        container.viewContext.mergePolicy = NSMergeByPropertyObjectTrumpMergePolicy
        return container
    }()

    var viewContext: NSManagedObjectContext {
        persistentContainer.viewContext
    }

    func newBackgroundContext() -> NSManagedObjectContext {
        persistentContainer.newBackgroundContext()
    }

    func saveContext() {
        let context = viewContext
        guard context.hasChanges else { return }
        do {
            try context.save()
        } catch {
            let nsError = error as NSError
            print("CoreData save error: \(nsError), \(nsError.userInfo)")
        }
    }

    // MARK: - Programmatic Core Data Model

    /// Creates the NSManagedObjectModel programmatically instead of using .xcdatamodeld files.
    static func createManagedObjectModel() -> NSManagedObjectModel {
        let model = NSManagedObjectModel()

        // -- CachedTask Entity --
        let cachedTaskEntity = NSEntityDescription()
        cachedTaskEntity.name = "CachedTask"
        cachedTaskEntity.managedObjectClassName = NSStringFromClass(CachedTask.self)

        let taskId = NSAttributeDescription()
        taskId.name = "taskId"
        taskId.attributeType = .stringAttributeType
        taskId.isOptional = false

        let text = NSAttributeDescription()
        text.name = "text"
        text.attributeType = .stringAttributeType
        text.isOptional = false

        let taskDescription = NSAttributeDescription()
        taskDescription.name = "taskDescription"
        taskDescription.attributeType = .stringAttributeType
        taskDescription.isOptional = true

        let project = NSAttributeDescription()
        project.name = "project"
        project.attributeType = .stringAttributeType
        project.isOptional = true

        let status = NSAttributeDescription()
        status.name = "status"
        status.attributeType = .stringAttributeType
        status.isOptional = true

        let completed = NSAttributeDescription()
        completed.name = "completed"
        completed.attributeType = .booleanAttributeType
        completed.defaultValue = false

        let priority = NSAttributeDescription()
        priority.name = "priority"
        priority.attributeType = .stringAttributeType
        priority.isOptional = true

        let dueDate = NSAttributeDescription()
        dueDate.name = "dueDate"
        dueDate.attributeType = .dateAttributeType
        dueDate.isOptional = true

        let createdAt = NSAttributeDescription()
        createdAt.name = "createdAt"
        createdAt.attributeType = .dateAttributeType
        createdAt.isOptional = true

        let tagsJSON = NSAttributeDescription()
        tagsJSON.name = "tagsJSON"
        tagsJSON.attributeType = .stringAttributeType
        tagsJSON.isOptional = true

        let lastSyncedAt = NSAttributeDescription()
        lastSyncedAt.name = "lastSyncedAt"
        lastSyncedAt.attributeType = .dateAttributeType
        lastSyncedAt.isOptional = true

        cachedTaskEntity.properties = [
            taskId, text, taskDescription, project, status,
            completed, priority, dueDate, createdAt, tagsJSON, lastSyncedAt
        ]

        // -- PendingChangeEntity --
        let pendingChangeEntity = NSEntityDescription()
        pendingChangeEntity.name = "PendingChangeEntity"
        pendingChangeEntity.managedObjectClassName = NSStringFromClass(PendingChangeEntity.self)

        let changeId = NSAttributeDescription()
        changeId.name = "changeId"
        changeId.attributeType = .UUIDAttributeType
        changeId.isOptional = false

        let changeType = NSAttributeDescription()
        changeType.name = "changeType"
        changeType.attributeType = .stringAttributeType
        changeType.isOptional = false

        let payloadJSON = NSAttributeDescription()
        payloadJSON.name = "payloadJSON"
        payloadJSON.attributeType = .stringAttributeType
        payloadJSON.isOptional = false

        let changeCreatedAt = NSAttributeDescription()
        changeCreatedAt.name = "createdAt"
        changeCreatedAt.attributeType = .dateAttributeType
        changeCreatedAt.isOptional = false

        pendingChangeEntity.properties = [changeId, changeType, payloadJSON, changeCreatedAt]

        model.entities = [cachedTaskEntity, pendingChangeEntity]

        return model
    }
}
