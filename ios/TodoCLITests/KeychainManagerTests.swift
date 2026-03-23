import XCTest
@testable import TodoCLI

final class KeychainManagerTests: XCTestCase {

    override func setUp() {
        super.setUp()
        // Clean slate before each test
        KeychainManager.deleteAll()
    }

    override func tearDown() {
        KeychainManager.deleteAll()
        super.tearDown()
    }

    // MARK: - Save and Retrieve

    func testSaveAndRetrieveAuthToken() throws {
        try KeychainManager.save("test-token-123", for: .authToken)

        let retrieved = KeychainManager.retrieve(for: .authToken)
        XCTAssertEqual(retrieved, "test-token-123")
    }

    func testSaveAndRetrieveAuthCookie() throws {
        try KeychainManager.save("cookie-value", for: .authCookie)

        let retrieved = KeychainManager.retrieve(for: .authCookie)
        XCTAssertEqual(retrieved, "cookie-value")
    }

    func testSaveEmptyString() throws {
        try KeychainManager.save("", for: .authToken)

        let retrieved = KeychainManager.retrieve(for: .authToken)
        XCTAssertEqual(retrieved, "")
    }

    func testSaveLongString() throws {
        let longString = String(repeating: "abcdefghij", count: 100) // 1000 chars
        try KeychainManager.save(longString, for: .authToken)

        let retrieved = KeychainManager.retrieve(for: .authToken)
        XCTAssertEqual(retrieved, longString)
    }

    func testSaveSpecialCharacters() throws {
        let specialChars = "!@#$%^&*()_+-={}[]|\\:\";<>?,./ 🔑"
        try KeychainManager.save(specialChars, for: .authToken)

        let retrieved = KeychainManager.retrieve(for: .authToken)
        XCTAssertEqual(retrieved, specialChars)
    }

    // MARK: - Overwrite Existing Value

    func testOverwriteExistingValue() throws {
        try KeychainManager.save("original-token", for: .authToken)
        XCTAssertEqual(KeychainManager.retrieve(for: .authToken), "original-token")

        try KeychainManager.save("updated-token", for: .authToken)
        XCTAssertEqual(KeychainManager.retrieve(for: .authToken), "updated-token")
    }

    func testOverwriteMultipleTimes() throws {
        for i in 0..<10 {
            try KeychainManager.save("token-\(i)", for: .authToken)
        }

        let retrieved = KeychainManager.retrieve(for: .authToken)
        XCTAssertEqual(retrieved, "token-9")
    }

    // MARK: - Retrieve Non-Existent Key

    func testRetrieveNonExistentKeyReturnsNil() {
        let retrieved = KeychainManager.retrieve(for: .authToken)
        XCTAssertNil(retrieved)
    }

    func testRetrieveNonExistentCookieReturnsNil() {
        let retrieved = KeychainManager.retrieve(for: .authCookie)
        XCTAssertNil(retrieved)
    }

    // MARK: - Delete

    func testDeleteRemovesValue() throws {
        try KeychainManager.save("to-delete", for: .authToken)
        XCTAssertNotNil(KeychainManager.retrieve(for: .authToken))

        KeychainManager.delete(for: .authToken)
        XCTAssertNil(KeychainManager.retrieve(for: .authToken))
    }

    func testDeleteNonExistentKeyDoesNotCrash() {
        // Should not throw or crash
        KeychainManager.delete(for: .authToken)
        KeychainManager.delete(for: .authCookie)
    }

    func testDeleteAllRemovesBothKeys() throws {
        try KeychainManager.save("token", for: .authToken)
        try KeychainManager.save("cookie", for: .authCookie)

        KeychainManager.deleteAll()

        XCTAssertNil(KeychainManager.retrieve(for: .authToken))
        XCTAssertNil(KeychainManager.retrieve(for: .authCookie))
    }

    // MARK: - Independence of Keys

    func testKeysAreIndependent() throws {
        try KeychainManager.save("token-value", for: .authToken)
        try KeychainManager.save("cookie-value", for: .authCookie)

        XCTAssertEqual(KeychainManager.retrieve(for: .authToken), "token-value")
        XCTAssertEqual(KeychainManager.retrieve(for: .authCookie), "cookie-value")

        KeychainManager.delete(for: .authToken)

        XCTAssertNil(KeychainManager.retrieve(for: .authToken))
        XCTAssertEqual(KeychainManager.retrieve(for: .authCookie), "cookie-value")
    }

    // MARK: - Key Raw Values

    func testKeyRawValues() {
        XCTAssertEqual(KeychainManager.Key.authToken.rawValue, "com.todocli.auth_token")
        XCTAssertEqual(KeychainManager.Key.authCookie.rawValue, "com.todocli.auth_cookie")
    }
}
