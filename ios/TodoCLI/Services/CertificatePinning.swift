import Foundation
import Security
import CommonCrypto

/// Certificate pinning delegate for URLSession.
/// Validates server certificates against pinned public key hashes.
class CertificatePinningDelegate: NSObject, URLSessionDelegate {
    /// SHA-256 hashes of pinned public keys (base64 encoded)
    private let pinnedHashes: Set<String>

    /// Whether pinning is enabled (disabled for localhost/development)
    private let enabled: Bool

    init(pinnedHashes: Set<String> = [], enabled: Bool = true) {
        self.pinnedHashes = pinnedHashes
        self.enabled = enabled
    }

    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        // If pinning disabled (dev mode), accept all
        guard enabled, !pinnedHashes.isEmpty else {
            completionHandler(.performDefaultHandling, nil)
            return
        }

        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        // Skip pinning for localhost connections
        let host = challenge.protectionSpace.host
        if host == "localhost" || host == "127.0.0.1" || host == "::1" {
            completionHandler(.performDefaultHandling, nil)
            return
        }

        // Evaluate the server trust
        let policy = SecPolicyCreateSSL(true, host as CFString)
        SecTrustSetPolicies(serverTrust, policy)

        var error: CFError?
        let isTrusted = SecTrustEvaluateWithError(serverTrust, &error)

        guard isTrusted else {
            completionHandler(.cancelAuthenticationChallenge, nil)
            return
        }

        // Check each certificate in the chain against pinned hashes
        let certificateCount = SecTrustGetCertificateCount(serverTrust)
        var foundMatch = false

        for index in 0..<certificateCount {
            guard let certificate = SecTrustGetCertificateAtIndex(serverTrust, index) else {
                continue
            }

            if let hash = publicKeyHash(for: certificate), pinnedHashes.contains(hash) {
                foundMatch = true
                break
            }
        }

        if foundMatch {
            let credential = URLCredential(trust: serverTrust)
            completionHandler(.useCredential, credential)
        } else {
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }

    /// Extract SHA-256 hash of the public key from a certificate.
    /// Returns a base64-encoded string of the SHA-256 hash.
    private func publicKeyHash(for certificate: SecCertificate) -> String? {
        guard let publicKey = SecCertificateCopyKey(certificate) else {
            return nil
        }

        guard let publicKeyData = SecKeyCopyExternalRepresentation(publicKey, nil) as Data? else {
            return nil
        }

        // Compute SHA-256 hash
        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        publicKeyData.withUnsafeBytes { buffer in
            _ = CC_SHA256(buffer.baseAddress, CC_LONG(buffer.count), &hash)
        }

        return Data(hash).base64EncodedString()
    }
}

/// Configuration for certificate pinning behavior.
struct CertificatePinningConfiguration {
    /// Whether certificate pinning is enabled
    var isPinningEnabled: Bool

    /// Set of base64-encoded SHA-256 public key hashes to pin against
    var pinnedPublicKeyHashes: Set<String>

    /// Default configuration with pinning disabled
    static let disabled = CertificatePinningConfiguration(
        isPinningEnabled: false,
        pinnedPublicKeyHashes: []
    )

    /// Creates an enabled configuration with the given hashes
    static func enabled(hashes: Set<String>) -> CertificatePinningConfiguration {
        CertificatePinningConfiguration(
            isPinningEnabled: true,
            pinnedPublicKeyHashes: hashes
        )
    }
}
