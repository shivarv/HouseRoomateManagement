import Foundation

struct APIError: LocalizedError {
    let status: Int
    let message: String

    var errorDescription: String? { message }

    /// Parses FastAPI's `{"detail": "..."}` or `{"detail": [{"msg": "..."}]}` error bodies.
    static func from(status: Int, data: Data) -> APIError {
        let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        if let detail = json?["detail"] as? String {
            return APIError(status: status, message: detail)
        }
        if let first = (json?["detail"] as? [[String: Any]])?.first, let msg = first["msg"] as? String {
            return APIError(status: status, message: msg)
        }
        return APIError(status: status, message: HTTPURLResponse.localizedString(forStatusCode: status).capitalized)
    }
}
