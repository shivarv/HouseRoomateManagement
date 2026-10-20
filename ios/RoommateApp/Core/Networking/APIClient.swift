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
        return try decoder.decode(T.self, from: data)
    }

    /// For endpoints that return 204 No Content.
    func sendNoContent<B: Encodable>(_ method: String, _ path: String, body: B? = Optional<String>.none) async throws {
        _ = try await raw(method, path, body: body)
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

        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError(status: 0, message: "Can't reach the server at \(baseURL). Is the backend running?")
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(status) else {
            if status == 401, token != nil { onUnauthorized?() }
            throw APIError.from(status: status, data: data)
        }
        return data
    }
}
