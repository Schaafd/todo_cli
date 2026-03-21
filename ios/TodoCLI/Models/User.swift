import Foundation

struct User: Codable, Identifiable {
    let id: String
    let username: String
    let email: String
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, username, email
        case createdAt = "created_at"
    }
}

struct LoginRequest: Codable {
    let username: String
    let password: String
    let remember: Bool
}

struct RegisterRequest: Codable {
    let username: String
    let email: String
    let password: String
}

struct TokenResponse: Codable {
    let accessToken: String
    let tokenType: String

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
    }
}

struct PomodoroStatus: Codable {
    let isRunning: Bool
    let isPaused: Bool
    let timeRemaining: Int
    let currentSession: Int
    let totalSessions: Int
    let sessionType: String

    enum CodingKeys: String, CodingKey {
        case isRunning = "is_running"
        case isPaused = "is_paused"
        case timeRemaining = "time_remaining"
        case currentSession = "current_session"
        case totalSessions = "total_sessions"
        case sessionType = "session_type"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        isRunning = try container.decodeIfPresent(Bool.self, forKey: .isRunning) ?? false
        isPaused = try container.decodeIfPresent(Bool.self, forKey: .isPaused) ?? false
        timeRemaining = try container.decodeIfPresent(Int.self, forKey: .timeRemaining) ?? 1500
        currentSession = try container.decodeIfPresent(Int.self, forKey: .currentSession) ?? 0
        totalSessions = try container.decodeIfPresent(Int.self, forKey: .totalSessions) ?? 4
        sessionType = try container.decodeIfPresent(String.self, forKey: .sessionType) ?? "work"
    }

    init(
        isRunning: Bool = false,
        isPaused: Bool = false,
        timeRemaining: Int = 1500,
        currentSession: Int = 0,
        totalSessions: Int = 4,
        sessionType: String = "work"
    ) {
        self.isRunning = isRunning
        self.isPaused = isPaused
        self.timeRemaining = timeRemaining
        self.currentSession = currentSession
        self.totalSessions = totalSessions
        self.sessionType = sessionType
    }
}

struct AIStatus: Codable {
    let enabled: Bool
    let provider: String?
    let model: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        enabled = try container.decodeIfPresent(Bool.self, forKey: .enabled) ?? false
        provider = try container.decodeIfPresent(String.self, forKey: .provider)
        model = try container.decodeIfPresent(String.self, forKey: .model)
    }

    init(enabled: Bool = false, provider: String? = nil, model: String? = nil) {
        self.enabled = enabled
        self.provider = provider
        self.model = model
    }
}

struct DashboardItem: Codable, Identifiable {
    let id: String
    let name: String
    let description: String?
    let widgets: [String]?
}

struct DashboardsResponse: Codable {
    let dashboards: [DashboardItem]

    init(from decoder: Decoder) throws {
        // Handle both array and object responses
        if let container = try? decoder.singleValueContainer(),
           let items = try? container.decode([DashboardItem].self) {
            dashboards = items
        } else {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            dashboards = try container.decodeIfPresent([DashboardItem].self, forKey: .dashboards) ?? []
        }
    }

    enum CodingKeys: String, CodingKey {
        case dashboards
    }
}
