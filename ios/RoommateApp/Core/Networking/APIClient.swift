import Foundation

/// The only type that talks to the backend. Resource-specific calls live in Core/Services.
@MainActor
final class APIClient {
    static let shared = APIClient()

    let baseURL: String
    var onUnauthorized: (() -> Void)?

    var token: String? {
        didSet { TokenStore.save(token) }
    }

    private let session = URLSession.shared
    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()
    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    init() {
        baseURL = (Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String)
            ?? "http://localhost:8001/api/v1"
        token = TokenStore.load()
    }

    func get<T: Decodable>(_ path: String) async throws -> T {
        try await send("GET", path, body: Optional<String>.none)
    }

    func send<T: Decodable, B: Encodable>(_ method: String, _ path: String, body: B?) async throws -> T {
        let data = try await raw(method, path, body: body)
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            // e.g. the server is newer than this app: a raw "data couldn't be read" means nothing to anyone.
            throw APIError(status: 0, message: "The server sent something this version of the app doesn't understand. Try updating the app.")
        }
    }

    /// For endpoints that return 204 No Content.
    func sendNoContent<B: Encodable>(_ method: String, _ path: String, body: B? = Optional<String>.none) async throws {
        _ = try await raw(method, path, body: body)
    }

    /// The request runs in its own task, so a screen that goes away mid-load (switching tabs,
    /// pull to refresh) doesn't cancel it into a "can't reach the server" error. A GET that times
    /// out or loses the connection is tried once more: the server sleeps when idle and can take
    /// a while to wake up.
    private func fetch(_ request: URLRequest, retry: Bool) async throws -> (Data, URLResponse) {
        let session = session
        do {
            return try await Task { try await session.data(for: request) }.value
        } catch let error as URLError where retry && Self.retryable.contains(error.code) {
            try? await Task.sleep(for: .seconds(2))
            return try await fetch(request, retry: false)
        } catch {
            throw APIError(status: 0, message: Self.message(for: (error as? URLError)?.code))
        }
    }

    private static let retryable: Set<URLError.Code> = [.timedOut, .networkConnectionLost, .cannotConnectToHost]

    /// What went wrong, in words someone can act on.
    private static func message(for code: URLError.Code?) -> String {
        switch code {
        case .notConnectedToInternet, .dataNotAllowed, .internationalRoamingOff:
            "You're offline. Check your Wi-Fi or mobile data, then pull down to try again."
        case .timedOut:
            "The server is taking a while to answer. It may be waking up, so pull down to try again in a moment."
        case .cannotFindHost, .cannotConnectToHost, .dnsLookupFailed, .networkConnectionLost:
            "Couldn't connect to Roommates right now. Pull down to try again in a moment."
        case .secureConnectionFailed, .serverCertificateUntrusted, .serverCertificateHasBadDate:
            "Couldn't make a secure connection. If you're on public Wi-Fi, try mobile data."
        default:
            "Something went wrong reaching Roommates. Pull down to try again."
        }
    }

    private func raw<B: Encodable>(_ method: String, _ path: String, body: B?) async throws -> Data {
        guard let url = URL(string: baseURL + path) else {
            throw APIError(status: 0, message: "Bad URL: \(path)")
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try encoder.encode(body)
        }

        let (data, response) = try await fetch(request, retry: method == "GET")
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            if status == 401, token != nil { onUnauthorized?() }
            throw APIError.from(status: status, data: data)
        }
        return data
    }
}
