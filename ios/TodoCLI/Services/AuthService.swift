import Foundation
import SwiftUI

@MainActor
class AuthService: ObservableObject {
    @Published var currentUser: User?
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let apiClient: APIClient

    init(apiClient: APIClient) {
        self.apiClient = apiClient
        self.isAuthenticated = apiClient.isAuthenticated
    }

    func login(username: String, password: String) async {
        isLoading = true
        errorMessage = nil

        do {
            let success = try await apiClient.login(username: username, password: password)
            isAuthenticated = success
        } catch {
            errorMessage = error.localizedDescription
            isAuthenticated = false
        }

        isLoading = false
    }

    func logout() {
        apiClient.logout()
        currentUser = nil
        isAuthenticated = false
    }

    func register(username: String, email: String, password: String) async {
        isLoading = true
        errorMessage = nil

        // Registration would use a similar flow
        // For now, delegate to login after registration
        do {
            let success = try await apiClient.login(username: username, password: password)
            isAuthenticated = success
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }
}
