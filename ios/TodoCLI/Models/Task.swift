import Foundation

struct TodoTask: Identifiable, Codable, Equatable {
    let id: String
    var text: String
    var description: String?
    var project: String?
    var status: String
    var completed: Bool
    var priority: TaskPriority
    var dueDate: Date?
    var tags: [String]
    var createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, text, description, project, status, completed, priority, tags
        case dueDate = "due_date"
        case createdAt = "created_at"
    }

    init(
        id: String,
        text: String,
        description: String? = nil,
        project: String? = nil,
        status: String = "pending",
        completed: Bool = false,
        priority: TaskPriority = .medium,
        dueDate: Date? = nil,
        tags: [String] = [],
        createdAt: Date? = nil
    ) {
        self.id = id
        self.text = text
        self.description = description
        self.project = project
        self.status = status
        self.completed = completed
        self.priority = priority
        self.dueDate = dueDate
        self.tags = tags
        self.createdAt = createdAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // id can be Int or String from backend
        if let intId = try? container.decode(Int.self, forKey: .id) {
            id = String(intId)
        } else {
            id = try container.decode(String.self, forKey: .id)
        }

        text = try container.decode(String.self, forKey: .text)
        description = try container.decodeIfPresent(String.self, forKey: .description)
        project = try container.decodeIfPresent(String.self, forKey: .project)
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? "pending"
        completed = try container.decodeIfPresent(Bool.self, forKey: .completed) ?? false

        let priorityString = try container.decodeIfPresent(String.self, forKey: .priority) ?? "medium"
        priority = TaskPriority(rawValue: priorityString) ?? .medium

        tags = try container.decodeIfPresent([String].self, forKey: .tags) ?? []

        if let dateString = try container.decodeIfPresent(String.self, forKey: .dueDate) {
            dueDate = ISO8601DateFormatter().date(from: dateString)
                ?? DateFormatter.apiFormatter.date(from: dateString)
        } else {
            dueDate = nil
        }

        if let dateString = try container.decodeIfPresent(String.self, forKey: .createdAt) {
            createdAt = ISO8601DateFormatter().date(from: dateString)
                ?? DateFormatter.apiFormatter.date(from: dateString)
        } else {
            createdAt = nil
        }
    }

    var isOverdue: Bool {
        guard let due = dueDate, !completed else { return false }
        return due < Date()
    }

    var isDueToday: Bool {
        guard let due = dueDate else { return false }
        return Calendar.current.isDateInToday(due)
    }
}

enum TaskPriority: String, Codable, CaseIterable, Comparable {
    case low
    case medium
    case high
    case critical

    var displayName: String {
        rawValue.capitalized
    }

    var sortOrder: Int {
        switch self {
        case .critical: return 0
        case .high: return 1
        case .medium: return 2
        case .low: return 3
        }
    }

    static func < (lhs: TaskPriority, rhs: TaskPriority) -> Bool {
        lhs.sortOrder < rhs.sortOrder
    }
}

struct TaskCreateRequest: Codable {
    let title: String
    var description: String?
    var priority: String?
    var dueDate: Date?
    var projectId: String?
    var tags: [String]?

    enum CodingKeys: String, CodingKey {
        case title, description, priority, tags
        case dueDate = "due_date"
        case projectId = "project_id"
    }
}

struct TaskUpdateRequest: Codable {
    var title: String?
    var description: String?
    var priority: String?
    var dueDate: Date?
    var projectId: String?
    var tags: [String]?
    var completed: Bool?

    enum CodingKeys: String, CodingKey {
        case title, description, priority, tags, completed
        case dueDate = "due_date"
        case projectId = "project_id"
    }
}

struct TasksResponse: Codable {
    let tasks: [TodoTask]
}

struct TaskResponse: Codable {
    let task: TodoTask
}

struct TaskCreateResponse: Codable {
    let success: Bool
    let taskId: String?
    let task: TodoTask?

    enum CodingKeys: String, CodingKey {
        case success
        case taskId = "task_id"
        case task
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        success = try container.decode(Bool.self, forKey: .success)
        task = try container.decodeIfPresent(TodoTask.self, forKey: .task)

        if let intId = try? container.decodeIfPresent(Int.self, forKey: .taskId) {
            taskId = String(intId)
        } else {
            taskId = try container.decodeIfPresent(String.self, forKey: .taskId)
        }
    }
}

struct ToggleResponse: Codable {
    let success: Bool
    let completed: Bool
}

struct SuccessResponse: Codable {
    let success: Bool
}

extension DateFormatter {
    static let apiFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        return formatter
    }()
}
