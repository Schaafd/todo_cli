import Foundation
import Security

/// A secure wrapper around the iOS Keychain for storing sensitive credentials.
/// Replaces UserDefaults-based token storage to prevent plaintext credential exposure.
enum KeychainManager {

    // MARK: - Keys
    enum Key: String {
        case authToken = "com.todocli.auth_token"
        case authCookie = "com.todocli.auth_cookie"
    }

    // MARK: - Errors
    enum KeychainError: LocalizedError {
        case duplicateItem
        case itemNotFound
        case unexpectedStatus(OSStatus)
        case encodingFailed

        var errorDescription: String? {
            switch self {
            case .duplicateItem:
                return "An item with this key already exists in the Keychain."
            case .itemNotFound:
                return "No item found for this key in the Keychain."
            case .unexpectedStatus(let status):
                return "Keychain error: \(status)"
            case .encodingFailed:
                return "Failed to encode the value for Keychain storage."
            }
        }
    }

    // MARK: - Public API

    /// Saves a string value to the Keychain, overwriting any existing value for the key.
    static func save(_ value: String, for key: Key) throws {
        guard let data = value.data(using: .utf8) else {
            throw KeychainError.encodingFailed
        }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]

        // Try to update first
        let updateAttributes: [String: Any] = [
            kSecValueData as String: data,
        ]

        let updateStatus = SecItemUpdate(query as CFDictionary, updateAttributes as CFDictionary)

        if updateStatus == errSecItemNotFound {
            // Item doesn't exist yet; add it
            var addQuery = query
            addQuery[kSecValueData as String] = data
            let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
            guard addStatus == errSecSuccess else {
                throw KeychainError.unexpectedStatus(addStatus)
            }
        } else if updateStatus != errSecSuccess {
            throw KeychainError.unexpectedStatus(updateStatus)
        }
    }

    /// Retrieves a string value from the Keychain.
    static func retrieve(for key: Key) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess, let data = result as? Data else {
            return nil
        }

        return String(data: data, encoding: .utf8)
    }

    /// Deletes a value from the Keychain.
    static func delete(for key: Key) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key.rawValue,
        ]

        SecItemDelete(query as CFDictionary)
    }

    /// Deletes all app credentials from the Keychain.
    static func deleteAll() {
        delete(for: .authToken)
        delete(for: .authCookie)
    }

    /// Migrates tokens from UserDefaults to Keychain (one-time migration).
    static func migrateFromUserDefaultsIfNeeded() {
        let defaults = UserDefaults.standard
        let migrationKey = "keychain_migration_complete"

        guard !defaults.bool(forKey: migrationKey) else { return }

        if let token = defaults.string(forKey: "auth_token") {
            try? save(token, for: .authToken)
            defaults.removeObject(forKey: "auth_token")
        }

        if let cookie = defaults.string(forKey: "auth_cookie") {
            try? save(cookie, for: .authCookie)
            defaults.removeObject(forKey: "auth_cookie")
        }

        defaults.set(true, forKey: migrationKey)
    }
}
