import Foundation
import LocalAuthentication
import SwiftUI

/// Manages biometric authentication (Face ID / Touch ID) for app lock functionality.
class BiometricAuthManager: ObservableObject {
    @Published var isLocked: Bool = true
    @Published var biometricType: LABiometryType = .none
    @Published var authError: String?

    @AppStorage("biometric_enabled") var isBiometricEnabled: Bool = false
    @AppStorage("app_lock_enabled") var isAppLockEnabled: Bool = false
    @AppStorage("require_auth_on_launch") var requireAuthOnLaunch: Bool = true

    init() {
        updateBiometricType()
        // If app lock is not enabled, start unlocked
        if !isAppLockEnabled {
            isLocked = false
        }
    }

    /// Checks whether biometric authentication is available on this device.
    func checkBiometricAvailability() -> Bool {
        let context = LAContext()
        var error: NSError?
        let canEvaluate = context.canEvaluatePolicy(
            .deviceOwnerAuthenticationWithBiometrics,
            error: &error
        )
        if canEvaluate {
            biometricType = context.biometryType
        }
        return canEvaluate
    }

    /// Updates the stored biometric type based on device capabilities.
    func updateBiometricType() {
        let context = LAContext()
        var error: NSError?
        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            biometricType = context.biometryType
        } else {
            biometricType = .none
        }
    }

    /// Attempts biometric authentication. Returns true on success.
    func authenticate(reason: String = "Unlock Todo CLI") async -> Bool {
        let context = LAContext()
        context.localizedFallbackTitle = "Use Passcode"
        var error: NSError?

        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            // Fall back to device passcode if biometrics unavailable
            return await authenticateWithPasscode(reason: reason)
        }

        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: reason
            )
            await MainActor.run {
                isLocked = !success
                authError = nil
            }
            return success
        } catch let authenticationError as LAError {
            await MainActor.run {
                switch authenticationError.code {
                case .userCancel:
                    authError = nil // User cancelled intentionally
                case .biometryLockout:
                    authError = "Biometrics locked out. Use passcode to unlock."
                case .biometryNotAvailable:
                    authError = "Biometrics not available on this device."
                case .biometryNotEnrolled:
                    authError = "No biometrics enrolled. Set up \(getBiometricTypeName()) in Settings."
                default:
                    authError = "Authentication failed. Please try again."
                }
            }
            return false
        } catch {
            await MainActor.run {
                authError = "Authentication failed. Please try again."
            }
            return false
        }
    }

    /// Falls back to device passcode authentication.
    private func authenticateWithPasscode(reason: String) async -> Bool {
        let context = LAContext()
        var error: NSError?

        guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) else {
            await MainActor.run {
                authError = "No authentication method available."
            }
            return false
        }

        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthentication,
                localizedReason: reason
            )
            await MainActor.run {
                isLocked = !success
                authError = nil
            }
            return success
        } catch {
            await MainActor.run {
                authError = "Authentication failed. Please try again."
            }
            return false
        }
    }

    /// Returns a human-readable name for the available biometric type.
    func getBiometricTypeName() -> String {
        switch biometricType {
        case .faceID:
            return "Face ID"
        case .touchID:
            return "Touch ID"
        case .opticID:
            return "Optic ID"
        @unknown default:
            return "Biometrics"
        }
    }

    /// Returns the SF Symbol name for the current biometric type.
    func getBiometricIconName() -> String {
        switch biometricType {
        case .faceID:
            return "faceid"
        case .touchID:
            return "touchid"
        case .opticID:
            return "opticid"
        @unknown default:
            return "lock.shield"
        }
    }

    /// Locks the app if app lock is enabled.
    func lockIfEnabled() {
        if isAppLockEnabled {
            isLocked = true
        }
    }

    /// Unlocks the app without authentication (e.g., when disabling app lock).
    func unlock() {
        isLocked = false
        authError = nil
    }
}
