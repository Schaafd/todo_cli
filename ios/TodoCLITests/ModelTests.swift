import XCTest
@testable import TodoCLI

final class ModelTests: XCTestCase {

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    // MARK: - TodoTask JSON Decoding

    func testTodoTaskDecodesFullFields() throws {
        let json = """
        {
            "id": "abc-123",
            "text": "Buy milk",
            "description": "From the store",
            "project": "groceries",
            "status": "in_progress",
            "completed": false,
            "priority": "high",
            "due_date": "2026-04-01T10:00:00Z",
            "created_at": "2026-03-20T08:00:00Z",
            "tags": ["shopping", "urgent"]
        }
        """.data(using: .utf8)!

        let task = try decoder.decode(TodoTask.self, from: json)

        XCTAssertEqual(task.id, "abc-123")
        XCTAssertEqual(task.text, "Buy milk")
        XCTAssertEqual(task.description, "From the store")
        XCTAssertEqual(task.project, "groceries")
        XCTAssertEqual(task.status, "in_progress")
        XCTAssertFalse(task.completed)
        XCTAssertEqual(task.priority, .high)
        XCTAssertNotNil(task.dueDate)
        XCTAssertNotNil(task.createdAt)
        XCTAssertEqual(task.tags, ["shopping", "urgent"])
    }

    func testTodoTaskDecodesMinimalFields() throws {
        let json = """
        {
            "id": "1",
            "text": "Simple task"
        }
        """.data(using: .utf8)!

        let task = try decoder.decode(TodoTask.self, from: json)

        XCTAssertEqual(task.id, "1")
        XCTAssertEqual(task.text, "Simple task")
        XCTAssertNil(task.description)
        XCTAssertNil(task.project)
        XCTAssertEqual(task.status, "pending") // default
        XCTAssertFalse(task.completed) // default
        XCTAssertEqual(task.priority, .medium) // default
        XCTAssertNil(task.dueDate)
        XCTAssertNil(task.createdAt)
        XCTAssertTrue(task.tags.isEmpty) // default
    }

    func testTodoTaskDecodesNullFields() throws {
        let json = """
        {
            "id": "2",
            "text": "Null fields",
            "description": null,
            "project": null,
            "status": null,
            "completed": null,
            "priority": null,
            "due_date": null,
            "created_at": null,
            "tags": null
        }
        """.data(using: .utf8)!

        let task = try decoder.decode(TodoTask.self, from: json)

        XCTAssertEqual(task.id, "2")
        XCTAssertEqual(task.text, "Null fields")
        XCTAssertNil(task.description)
        XCTAssertNil(task.project)
        XCTAssertEqual(task.status, "pending")
        XCTAssertFalse(task.completed)
        XCTAssertEqual(task.priority, .medium)
        XCTAssertNil(task.dueDate)
        XCTAssertNil(task.createdAt)
        XCTAssertTrue(task.tags.isEmpty)
    }

    // MARK: - Int vs String ID

    func testTodoTaskHandlesIntId() throws {
        let json = """
        {
            "id": 42,
            "text": "Int ID task"
        }
        """.data(using: .utf8)!

        let task = try decoder.decode(TodoTask.self, from: json)
        XCTAssertEqual(task.id, "42")
    }

    func testTodoTaskHandlesStringId() throws {
        let json = """
        {
            "id": "uuid-string-id",
            "text": "String ID task"
        }
        """.data(using: .utf8)!

        let task = try decoder.decode(TodoTask.self, from: json)
        XCTAssertEqual(task.id, "uuid-string-id")
    }

    // MARK: - Date Parsing Formats

    func testTodoTaskParsesISO8601Date() throws {
        let json = """
        {
            "id": "1",
            "text": "ISO date",
            "due_date": "2026-06-15T14:30:00Z"
        }
        """.data(using: .utf8)!

        let task = try decoder.decode(TodoTask.self, from: json)
        XCTAssertNotNil(task.dueDate)
    }

    func testTodoTaskParsesAPIFormatterDate() throws {
        let json = """
        {
            "id": "1",
            "text": "API date",
            "due_date": "2026-06-15T14:30:00"
        }
        """.data(using: .utf8)!

        let task = try decoder.decode(TodoTask.self, from: json)
        XCTAssertNotNil(task.dueDate)
    }

    // MARK: - Project JSON Decoding

    func testProjectDecodesFullFields() throws {
        let json = """
        {
            "id": "proj-1",
            "name": "Work",
            "description": "Work tasks",
            "color": "#FF5733",
            "task_count": 10,
            "completed_count": 3
        }
        """.data(using: .utf8)!

        let project = try decoder.decode(Project.self, from: json)

        XCTAssertEqual(project.id, "proj-1")
        XCTAssertEqual(project.name, "Work")
        XCTAssertEqual(project.description, "Work tasks")
        XCTAssertEqual(project.color, "#FF5733")
        XCTAssertEqual(project.taskCount, 10)
        XCTAssertEqual(project.completedCount, 3)
    }

    func testProjectProgress() {
        let project = Project(id: "1", name: "Test", taskCount: 10, completedCount: 7)
        XCTAssertEqual(project.progress, 0.7, accuracy: 0.001)
    }

    func testProjectProgressZeroTasks() {
        let project = Project(id: "1", name: "Empty")
        XCTAssertEqual(project.progress, 0.0)
    }

    func testProjectActiveTasks() {
        let project = Project(id: "1", name: "Test", taskCount: 10, completedCount: 3)
        XCTAssertEqual(project.activeTasks, 7)
    }

    // MARK: - Priority Computed Properties

    func testTaskPriorityDisplayName() {
        XCTAssertEqual(TaskPriority.low.displayName, "Low")
        XCTAssertEqual(TaskPriority.medium.displayName, "Medium")
        XCTAssertEqual(TaskPriority.high.displayName, "High")
        XCTAssertEqual(TaskPriority.critical.displayName, "Critical")
    }

    func testTaskPrioritySortOrder() {
        XCTAssertEqual(TaskPriority.critical.sortOrder, 0)
        XCTAssertEqual(TaskPriority.high.sortOrder, 1)
        XCTAssertEqual(TaskPriority.medium.sortOrder, 2)
        XCTAssertEqual(TaskPriority.low.sortOrder, 3)
    }

    func testTaskPriorityComparable() {
        XCTAssertTrue(TaskPriority.critical < TaskPriority.high)
        XCTAssertTrue(TaskPriority.high < TaskPriority.medium)
        XCTAssertTrue(TaskPriority.medium < TaskPriority.low)
        XCTAssertFalse(TaskPriority.low < TaskPriority.critical)
    }

    func testTaskPriorityAllCases() {
        XCTAssertEqual(TaskPriority.allCases.count, 4)
        XCTAssertTrue(TaskPriority.allCases.contains(.low))
        XCTAssertTrue(TaskPriority.allCases.contains(.medium))
        XCTAssertTrue(TaskPriority.allCases.contains(.high))
        XCTAssertTrue(TaskPriority.allCases.contains(.critical))
    }

    // MARK: - Status Computed Properties

    func testIsOverdueWhenPastDueAndIncomplete() {
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date())!
        let task = TodoTask(id: "1", text: "Overdue", completed: false, dueDate: yesterday)
        XCTAssertTrue(task.isOverdue)
    }

    func testIsNotOverdueWhenCompleted() {
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date())!
        let task = TodoTask(id: "1", text: "Done", completed: true, dueDate: yesterday)
        XCTAssertFalse(task.isOverdue)
    }

    func testIsNotOverdueWhenNoDueDate() {
        let task = TodoTask(id: "1", text: "No date")
        XCTAssertFalse(task.isOverdue)
    }

    func testIsNotOverdueWhenFutureDueDate() {
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        let task = TodoTask(id: "1", text: "Future", dueDate: tomorrow)
        XCTAssertFalse(task.isOverdue)
    }

    func testIsDueTodayWhenDueDateIsToday() {
        // Use noon today to be clearly "today"
        let today = Calendar.current.startOfDay(for: Date()).addingTimeInterval(3600 * 12)
        let task = TodoTask(id: "1", text: "Today", dueDate: today)
        XCTAssertTrue(task.isDueToday)
    }

    func testIsDueTodayFalseWhenNoDueDate() {
        let task = TodoTask(id: "1", text: "No date")
        XCTAssertFalse(task.isDueToday)
    }

    func testIsDueTodayFalseWhenDueTomorrow() {
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        let task = TodoTask(id: "1", text: "Tomorrow", dueDate: tomorrow)
        XCTAssertFalse(task.isDueToday)
    }

    // MARK: - TodoTask Equatable

    func testTodoTaskEquality() {
        let task1 = TodoTask(id: "1", text: "Task", priority: .high)
        let task2 = TodoTask(id: "1", text: "Task", priority: .high)
        XCTAssertEqual(task1, task2)
    }

    func testTodoTaskInequality() {
        let task1 = TodoTask(id: "1", text: "Task A")
        let task2 = TodoTask(id: "2", text: "Task B")
        XCTAssertNotEqual(task1, task2)
    }

    // MARK: - Date+Extensions

    func testDateIsToday() {
        XCTAssertTrue(Date().isToday)
    }

    func testDateIsTomorrow() {
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        XCTAssertTrue(tomorrow.isTomorrow)
        XCTAssertFalse(Date().isTomorrow)
    }

    func testDateIsYesterday() {
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date())!
        XCTAssertTrue(yesterday.isYesterday)
        XCTAssertFalse(Date().isYesterday)
    }

    func testDateIsPast() {
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date())!
        XCTAssertTrue(yesterday.isPast)

        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        XCTAssertFalse(tomorrow.isPast)
    }

    func testDateIsThisWeek() {
        XCTAssertTrue(Date().isThisWeek)
    }

    func testRelativeDescriptionToday() {
        let today = Date()
        XCTAssertEqual(today.relativeDescription, "Today")
    }

    func testRelativeDescriptionTomorrow() {
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        XCTAssertEqual(tomorrow.relativeDescription, "Tomorrow")
    }

    func testRelativeDescriptionYesterday() {
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date())!
        XCTAssertEqual(yesterday.relativeDescription, "Yesterday")
    }

    func testRelativeDescriptionDaysAgo() {
        let threeDaysAgo = Calendar.current.date(byAdding: .day, value: -3, to: Date())!
        XCTAssertTrue(threeDaysAgo.relativeDescription.contains("d ago"))
    }

    func testRelativeDescriptionWeeksAgo() {
        let twoWeeksAgo = Calendar.current.date(byAdding: .day, value: -14, to: Date())!
        XCTAssertTrue(twoWeeksAgo.relativeDescription.contains("w ago"))
    }

    func testPomodoroFormatted() {
        XCTAssertEqual(Date.pomodoroFormatted(seconds: 1500), "25:00")
        XCTAssertEqual(Date.pomodoroFormatted(seconds: 0), "00:00")
        XCTAssertEqual(Date.pomodoroFormatted(seconds: 61), "01:01")
        XCTAssertEqual(Date.pomodoroFormatted(seconds: 3599), "59:59")
    }

    func testShortFormatted() {
        // Test that shortFormatted returns a non-empty string
        let date = Date()
        XCTAssertFalse(date.shortFormatted.isEmpty)
    }

    func testTimeFormatted() {
        let date = Date()
        XCTAssertFalse(date.timeFormatted.isEmpty)
    }

    // MARK: - TaskCreateResponse Decoding

    func testTaskCreateResponseWithIntId() throws {
        let json = """
        {
            "success": true,
            "task_id": 42
        }
        """.data(using: .utf8)!

        let response = try decoder.decode(TaskCreateResponse.self, from: json)
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.taskId, "42")
    }

    func testTaskCreateResponseWithStringId() throws {
        let json = """
        {
            "success": true,
            "task_id": "uuid-abc"
        }
        """.data(using: .utf8)!

        let response = try decoder.decode(TaskCreateResponse.self, from: json)
        XCTAssertTrue(response.success)
        XCTAssertEqual(response.taskId, "uuid-abc")
    }

    // MARK: - ToggleResponse

    func testToggleResponseDecoding() throws {
        let json = """
        {"success": true, "completed": true}
        """.data(using: .utf8)!

        let response = try decoder.decode(ToggleResponse.self, from: json)
        XCTAssertTrue(response.success)
        XCTAssertTrue(response.completed)
    }

    // MARK: - DateFormatter Extension

    func testAPIFormatterFormat() {
        let formatter = DateFormatter.apiFormatter
        let date = formatter.date(from: "2026-03-20T14:30:00")
        XCTAssertNotNil(date)
    }

    func testAPIFormatterTimezoneIsUTC() {
        let formatter = DateFormatter.apiFormatter
        XCTAssertEqual(formatter.timeZone, TimeZone(secondsFromGMT: 0))
    }
}
