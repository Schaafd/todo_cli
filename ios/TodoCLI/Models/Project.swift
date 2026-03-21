import Foundation
import SwiftUI

struct Project: Identifiable, Codable, Equatable {
    let id: String
    var name: String
    var description: String?
    var color: String?
    var taskCount: Int
    var completedCount: Int

    enum CodingKeys: String, CodingKey {
        case id, name, description, color
        case taskCount = "task_count"
        case completedCount = "completed_count"
    }

    init(
        id: String,
        name: String,
        description: String? = nil,
        color: String? = nil,
        taskCount: Int = 0,
        completedCount: Int = 0
    ) {
        self.id = id
        self.name = name
        self.description = description
        self.color = color
        self.taskCount = taskCount
        self.completedCount = completedCount
    }

    var progress: Double {
        guard taskCount > 0 else { return 0 }
        return Double(completedCount) / Double(taskCount)
    }

    var activeTasks: Int {
        taskCount - completedCount
    }

    var swiftUIColor: Color {
        guard let hex = color else { return .blue }
        return Color(hex: hex) ?? .blue
    }
}

struct ProjectsResponse: Codable {
    let projects: [Project]
}

struct ProjectCreateRequest: Codable {
    let name: String
    var description: String?
    var color: String?
}

struct ProjectCreateResponse: Codable {
    let success: Bool
    let projectId: String?
    let project: Project?

    enum CodingKeys: String, CodingKey {
        case success
        case projectId = "project_id"
        case project
    }
}
