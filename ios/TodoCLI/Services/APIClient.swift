import Foundation
import Combine

@MainActor
class APIClient: ObservableObject {
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var lastError: String?

    private var token: String? {
        didSet {
            if let token = token {
                UserDefaults.standard.set(token, forKey: "auth_token")
            } else {
                UserDefaults.standard.removeObject(forKey: "auth_token")
            }
            isAuthenticated = token != nil
        }
    }

    var baseURL: String {
        get {
            UserDefaults.standard.string(forKey: "server_url") ?? "http://localhost:8000"
        }
        set {
            UserDefaults.standard.set(newValue, forKey: "server_url")
        }
    }

    private let session: URLSession
    private let decoder: JSONDecoder

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 30
        session = URLSession(configuration: config)

        decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        // Restore token
        token = UserDefaults.standard.string(forKey: "auth_token")
    }

    // MARK: - Authentication

    func login(username: String, password: String) async throws -> Bool {
        let body = LoginRequest(username: username, password: password, remember: true)
        let _: TokenResponse = try await post("/api/auth/login", body: body, authenticated: false)
        // If we get a cookie-based auth, the token might be in the cookie
        // For now, assume the response gives us a token
        return true
    }

    func logout() {
        token = nil
    }

    // MARK: - Tasks

    func fetchTasks(project: String? = nil, status: String? = nil, priority: String? = nil) async throws -> [TodoTask] {
        var params: [String: String] = [:]
        if let project = project { params["project"] = project }
        if let status = status { params["status"] = status }
        if let priority = priority { params["priority"] = priority }

        let response: TasksResponse = try await get("/api/tasks", params: params)
        return response.tasks
    }

    func fetchTask(id: String) async throws -> TodoTask {
        let response: TaskResponse = try await get("/api/tasks/\(id)")
        return response.task
    }

    func createTask(_ request: TaskCreateRequest) async throws -> TaskCreateResponse {
        return try await post("/api/tasks", body: request)
    }

    func updateTask(id: String, _ request: TaskUpdateRequest) async throws -> SuccessResponse {
        return try await put("/api/tasks/\(id)", body: request)
    }

    func toggleTask(id: String) async throws -> ToggleResponse {
        return try await post("/api/tasks/\(id)/toggle")
    }

    func deleteTask(id: String) async throws -> SuccessResponse {
        return try await delete("/api/tasks/\(id)")
    }

    // MARK: - Projects

    func fetchProjects() async throws -> [Project] {
        let response: ProjectsResponse = try await get("/api/projects")
        return response.projects
    }

    func createProject(_ request: ProjectCreateRequest) async throws -> ProjectCreateResponse {
        return try await post("/api/projects", body: request)
    }

    // MARK: - Pomodoro

    func fetchPomodoroStatus() async throws -> PomodoroStatus {
        return try await get("/api/pomodoro/status")
    }

    func startPomodoro(taskId: String? = nil) async throws -> PomodoroStatus {
        var params: [String: String] = [:]
        if let taskId = taskId { params["task_id"] = taskId }
        return try await post("/api/pomodoro/start", params: params)
    }

    func stopPomodoro() async throws -> PomodoroStatus {
        return try await post("/api/pomodoro/stop")
    }

    func pausePomodoro() async throws -> PomodoroStatus {
        return try await post("/api/pomodoro/pause")
    }

    func resumePomodoro() async throws -> PomodoroStatus {
        return try await post("/api/pomodoro/resume")
    }

    // MARK: - AI

    func fetchAIStatus() async throws -> AIStatus {
        return try await get("/api/ai/status")
    }

    // MARK: - Dashboards

    func fetchDashboards() async throws -> [DashboardItem] {
        let response: DashboardsResponse = try await get("/api/dashboards")
        return response.dashboards
    }

    // MARK: - Generic HTTP Methods

    private func get<T: Decodable>(_ path: String, params: [String: String] = [:]) async throws -> T {
        let url = try buildURL(path, params: params)
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        addAuthHeaders(&request)
        return try await perform(request)
    }

    private func post<T: Decodable>(_ path: String, params: [String: String] = [:]) async throws -> T {
        let url = try buildURL(path, params: params)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeaders(&request)
        return try await perform(request)
    }

    private func post<B: Encodable, T: Decodable>(_ path: String, body: B, authenticated: Bool = true, params: [String: String] = [:]) async throws -> T {
        let url = try buildURL(path, params: params)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if authenticated { addAuthHeaders(&request) }
        request.httpBody = try JSONEncoder().encode(body)
        return try await perform(request)
    }

    private func put<B: Encodable, T: Decodable>(_ path: String, body: B) async throws -> T {
        let url = try buildURL(path)
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeaders(&request)
        request.httpBody = try JSONEncoder().encode(body)
        return try await perform(request)
    }

    private func delete<T: Decodable>(_ path: String) async throws -> T {
        let url = try buildURL(path)
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        addAuthHeaders(&request)
        return try await perform(request)
    }

    // MARK: - Helpers

    private func buildURL(_ path: String, params: [String: String] = [:]) throws -> URL {
        guard var components = URLComponents(string: baseURL + path) else {
            throw APIError.invalidURL
        }
        if !params.isEmpty {
            components.queryItems = params.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        guard let url = components.url else {
            throw APIError.invalidURL
        }
        return url
    }

    private func addAuthHeaders(_ request: inout URLRequest) {
        if let token = token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        // Also include cookie-based auth
        if let cookieToken = UserDefaults.standard.string(forKey: "auth_cookie") {
            request.setValue("access_token=Bearer \(cookieToken)", forHTTPHeaderField: "Cookie")
        }
    }

    private func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        isLoading = true
        lastError = nil

        defer { isLoading = false }

        do {
            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }

            switch httpResponse.statusCode {
            case 200...299:
                return try decoder.decode(T.self, from: data)
            case 401:
                token = nil
                throw APIError.unauthorized
            case 403:
                throw APIError.forbidden
            case 404:
                throw APIError.notFound
            case 422:
                throw APIError.validationError(String(data: data, encoding: .utf8) ?? "Validation error")
            default:
                let message = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw APIError.serverError(httpResponse.statusCode, message)
            }
        } catch let error as APIError {
            lastError = error.localizedDescription
            throw error
        } catch let error as DecodingError {
            lastError = "Failed to parse response"
            throw APIError.decodingError(error)
        } catch {
            if (error as NSError).code == NSURLErrorNotConnectedToInternet {
                lastError = "No internet connection"
                throw APIError.offline
            }
            lastError = error.localizedDescription
            throw APIError.networkError(error)
        }
    }
}

enum APIError: LocalizedError {
    case invalidURL
    case invalidResponse
    case unauthorized
    case forbidden
    case notFound
    case offline
    case validationError(String)
    case serverError(Int, String)
    case decodingError(Error)
    case networkError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid server URL. Check your settings."
        case .invalidResponse:
            return "Received an invalid response from the server."
        case .unauthorized:
            return "Please log in to continue."
        case .forbidden:
            return "You don't have permission for this action."
        case .notFound:
            return "The requested resource was not found."
        case .offline:
            return "You appear to be offline. Check your connection."
        case .validationError(let msg):
            return "Validation error: \(msg)"
        case .serverError(let code, let msg):
            return "Server error (\(code)): \(msg)"
        case .decodingError:
            return "Failed to process server response."
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        }
    }
}
