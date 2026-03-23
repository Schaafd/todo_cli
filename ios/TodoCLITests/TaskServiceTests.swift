import XCTest
@testable import TodoCLI

// MARK: - Mock APIClient for TaskService Tests

@MainActor
final class MockAPIClient: APIClient {
    var mockTasks: [TodoTask] = []
    var mockToggleResponse = ToggleResponse(success: true, completed: true)
    var mockDeleteResponse = SuccessResponse(success: true)
    var mockCreateResponse: TaskCreateResponse?
    var shouldThrowError: APIError?
    var lastCreateRequest: TaskCreateRequest?
    var lastToggleId: String?
    var lastDeleteId: String?

    override func fetchTasks(project: String? = nil, status: String? = nil, priority: String? = nil) async throws -> [TodoTask] {
        if let error = shouldThrowError { throw error }
        var filtered = mockTasks
        if let project = project {
            filtered = filtered.filter { $0.project == project }
        }
        return filtered
    }

    override func createTask(_ request: TaskCreateRequest) async throws -> TaskCreateResponse {
        if let error = shouldThrowError { throw error }
        lastCreateRequest = request
        if let response = mockCreateResponse {
            return response
        }
        // Return a default success response
        let json = """
        {"success": true, "task_id": "new-1"}
        """.data(using: .utf8)!
        return try JSONDecoder().decode(TaskCreateResponse.self, from: json)
    }

    override func toggleTask(id: String) async throws -> ToggleResponse {
        if let error = shouldThrowError { throw error }
        lastToggleId = id
        return mockToggleResponse
    }

    override func deleteTask(id: String) async throws -> SuccessResponse {
        if let error = shouldThrowError { throw error }
        lastDeleteId = id
        return mockDeleteResponse
    }

    override func updateTask(id: String, _ request: TaskUpdateRequest) async throws -> SuccessResponse {
        if let error = shouldThrowError { throw error }
        return SuccessResponse(success: true)
    }
}

// MARK: - TaskService Tests

@MainActor
final class TaskServiceTests: XCTestCase {

    var mockClient: MockAPIClient!
    var taskService: TaskService!

    override func setUp() {
        super.setUp()
        KeychainManager.deleteAll()
        UserDefaults.standard.removeObject(forKey: "server_url")
        mockClient = MockAPIClient()
        taskService = TaskService(apiClient: mockClient)
    }

    override func tearDown() {
        KeychainManager.deleteAll()
        mockClient = nil
        taskService = nil
        super.tearDown()
    }

    // MARK: - Fetch Tasks

    func testFetchTasksParsesResponse() async {
        let task1 = TodoTask(id: "1", text: "Buy groceries", priority: .high)
        let task2 = TodoTask(id: "2", text: "Clean house", priority: .low)
        mockClient.mockTasks = [task1, task2]

        await taskService.loadTasks()

        XCTAssertEqual(taskService.tasks.count, 2)
        XCTAssertNil(taskService.error)
        XCTAssertFalse(taskService.isLoading)
    }

    func testFetchTasksSetsErrorOnFailure() async {
        mockClient.shouldThrowError = .networkError(NSError(domain: "test", code: -1))

        await taskService.loadTasks()

        XCTAssertNotNil(taskService.error)
        XCTAssertTrue(taskService.tasks.isEmpty)
    }

    // MARK: - Sorting Logic

    func testSortingIncompletedBeforeCompleted() async {
        let completed = TodoTask(id: "1", text: "Done task", completed: true, priority: .high)
        let active = TodoTask(id: "2", text: "Active task", completed: false, priority: .low)
        mockClient.mockTasks = [completed, active]

        await taskService.loadTasks()

        XCTAssertEqual(taskService.tasks.first?.id, "2") // Active first
        XCTAssertEqual(taskService.tasks.last?.id, "1")  // Completed last
    }

    func testSortingByPriority() async {
        let low = TodoTask(id: "1", text: "Low task", priority: .low)
        let critical = TodoTask(id: "2", text: "Critical task", priority: .critical)
        let medium = TodoTask(id: "3", text: "Medium task", priority: .medium)
        mockClient.mockTasks = [low, critical, medium]

        await taskService.loadTasks()

        // Priority sort: critical (0) < high (1) < medium (2) < low (3)
        XCTAssertEqual(taskService.tasks[0].id, "2") // critical
        XCTAssertEqual(taskService.tasks[1].id, "3") // medium
        XCTAssertEqual(taskService.tasks[2].id, "1") // low
    }

    func testSortingByDueDate() async {
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date())!
        let nextWeek = Calendar.current.date(byAdding: .day, value: 7, to: Date())!

        let laterTask = TodoTask(id: "1", text: "Later", priority: .medium, dueDate: nextWeek)
        let soonerTask = TodoTask(id: "2", text: "Sooner", priority: .medium, dueDate: tomorrow)
        mockClient.mockTasks = [laterTask, soonerTask]

        await taskService.loadTasks()

        XCTAssertEqual(taskService.tasks[0].id, "2") // Sooner due date first
        XCTAssertEqual(taskService.tasks[1].id, "1")
    }

    func testSortingTasksWithDueDateBeforeWithout() async {
        let withDate = TodoTask(id: "1", text: "Has date", priority: .medium, dueDate: Date())
        let withoutDate = TodoTask(id: "2", text: "No date", priority: .medium)
        mockClient.mockTasks = [withoutDate, withDate]

        await taskService.loadTasks()

        XCTAssertEqual(taskService.tasks[0].id, "1") // Has due date comes first
        XCTAssertEqual(taskService.tasks[1].id, "2")
    }

    func testSortingFallsBackToTextAlphabetical() async {
        let taskB = TodoTask(id: "1", text: "Banana", priority: .medium)
        let taskA = TodoTask(id: "2", text: "Apple", priority: .medium)
        mockClient.mockTasks = [taskB, taskA]

        await taskService.loadTasks()

        XCTAssertEqual(taskService.tasks[0].id, "2") // "Apple" before "Banana"
        XCTAssertEqual(taskService.tasks[1].id, "1")
    }

    // MARK: - Create Task

    func testCreateTaskSendsProperPayload() async {
        mockClient.mockTasks = [] // For the reload after create

        let success = await taskService.createTask(
            title: "New Task",
            description: "A description",
            priority: .high,
            project: "project-1",
            dueDate: nil,
            tags: ["urgent", "work"]
        )

        XCTAssertTrue(success)
        XCTAssertEqual(mockClient.lastCreateRequest?.title, "New Task")
        XCTAssertEqual(mockClient.lastCreateRequest?.description, "A description")
        XCTAssertEqual(mockClient.lastCreateRequest?.priority, "high")
        XCTAssertEqual(mockClient.lastCreateRequest?.projectId, "project-1")
        XCTAssertEqual(mockClient.lastCreateRequest?.tags, ["urgent", "work"])
    }

    func testCreateTaskWithEmptyTagsSendsNilTags() async {
        mockClient.mockTasks = []

        _ = await taskService.createTask(title: "Simple Task", tags: [])

        XCTAssertNil(mockClient.lastCreateRequest?.tags)
    }

    func testCreateTaskReturnsFalseOnError() async {
        mockClient.shouldThrowError = .serverError(500, "Server down")

        let success = await taskService.createTask(title: "Failing Task")

        XCTAssertFalse(success)
        XCTAssertNotNil(taskService.error)
    }

    // MARK: - Toggle Complete

    func testToggleTaskCallsAPIWithCorrectId() async {
        let task = TodoTask(id: "task-42", text: "Toggle me")
        mockClient.mockTasks = [] // For the reload

        await taskService.toggleTask(task)

        XCTAssertEqual(mockClient.lastToggleId, "task-42")
    }

    func testToggleTaskSetsErrorOnFailure() async {
        let task = TodoTask(id: "1", text: "Fail toggle")
        mockClient.shouldThrowError = .networkError(NSError(domain: "test", code: -1))

        await taskService.toggleTask(task)

        XCTAssertNotNil(taskService.error)
    }

    // MARK: - Delete Task

    func testDeleteTaskCallsAPIWithCorrectId() async {
        let task = TodoTask(id: "task-99", text: "Delete me")
        mockClient.mockTasks = [task]
        await taskService.loadTasks()

        mockClient.shouldThrowError = nil
        await taskService.deleteTask(task)

        XCTAssertEqual(mockClient.lastDeleteId, "task-99")
    }

    func testDeleteTaskRemovesFromLocalList() async {
        let task1 = TodoTask(id: "1", text: "Keep")
        let task2 = TodoTask(id: "2", text: "Remove")
        mockClient.mockTasks = [task1, task2]
        await taskService.loadTasks()
        XCTAssertEqual(taskService.tasks.count, 2)

        await taskService.deleteTask(task2)

        XCTAssertEqual(taskService.tasks.count, 1)
        XCTAssertEqual(taskService.tasks.first?.id, "1")
    }

    func testDeleteTaskSetsErrorOnFailure() async {
        let task = TodoTask(id: "1", text: "Fail delete")
        mockClient.shouldThrowError = .forbidden

        await taskService.deleteTask(task)

        XCTAssertNotNil(taskService.error)
    }

    // MARK: - Task Categorization

    func testTodayTasksCategorized() async {
        let today = Calendar.current.startOfDay(for: Date()).addingTimeInterval(3600 * 12) // Noon today
        let todayTask = TodoTask(id: "1", text: "Today task", dueDate: today)
        let futureTask = TodoTask(id: "2", text: "Future task", dueDate: Calendar.current.date(byAdding: .day, value: 5, to: Date()))
        mockClient.mockTasks = [todayTask, futureTask]

        await taskService.loadTasks()

        XCTAssertEqual(taskService.todayTasks.count, 1)
        XCTAssertEqual(taskService.todayTasks.first?.id, "1")
    }

    func testOverdueTasksCategorized() async {
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date())!
        let overdueTask = TodoTask(id: "1", text: "Overdue task", dueDate: yesterday)
        let futureTask = TodoTask(id: "2", text: "Future task", dueDate: Calendar.current.date(byAdding: .day, value: 5, to: Date()))
        mockClient.mockTasks = [overdueTask, futureTask]

        await taskService.loadTasks()

        XCTAssertEqual(taskService.overdueTasks.count, 1)
        XCTAssertEqual(taskService.overdueTasks.first?.id, "1")
    }

    func testCompletedTasksNotInTodayOrOverdue() async {
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date())!
        let completedOverdue = TodoTask(id: "1", text: "Done overdue", completed: true, dueDate: yesterday)
        mockClient.mockTasks = [completedOverdue]

        await taskService.loadTasks()

        XCTAssertTrue(taskService.todayTasks.isEmpty)
        XCTAssertTrue(taskService.overdueTasks.isEmpty)
    }
}
