import Foundation

/// One action voice can run, with real ids. Only the fields its `type` uses are set; the app never
/// builds these itself, it sends back what `interpret` (or a Confirm's undos) returned.
struct VoiceAction: Codable, Hashable {
    let type: String
    var taskId: UUID?
    var choreId: UUID?
    var logId: UUID?
    var memberId: UUID?
    var billId: UUID?
    var paymentId: UUID?
    var amountCents: Int?
    var names: [String]?
    var itemIds: [UUID]?
    var messageId: UUID?
    var text: String?
    var title: String?
    var details: String?
    var requestId: UUID?
}

/// A card to confirm: "Take out trash · done by Raj".
struct VoiceProposal: Codable, Hashable {
    let action: VoiceAction
    let summary: String
    let area: String  // chores, bills, groceries, chat, favours

    var icon: String {
        switch area {
        case "chores": "✅"
        case "bills": "🧾"
        case "groceries": "🛒"
        case "chat": "💬"
        case "favours": "🙋"
        default: "•"
        }
    }
}

/// Cards to confirm; and/or a question with options to tap; and/or notes. Nothing has changed yet.
struct VoiceInterpretation: Decodable {
    var proposals: [VoiceProposal] = []
    var question: String?
    var options: [String] = []
    var notes: [String] = []
    var commandId: UUID?

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        proposals = try c.decodeIfPresent([VoiceProposal].self, forKey: .proposals) ?? []
        question = try c.decodeIfPresent(String.self, forKey: .question)
        options = try c.decodeIfPresent([String].self, forKey: .options) ?? []
        notes = try c.decodeIfPresent([String].self, forKey: .notes) ?? []
        commandId = try c.decodeIfPresent(UUID.self, forKey: .commandId)
    }

    private enum CodingKeys: String, CodingKey {
        case proposals, question, options, notes, commandId
    }
}

struct VoiceResult: Decodable {
    let summary: String
    let ok: Bool
    let error: String?
    let undo: [VoiceAction]?
}

/// Spoken, or typed to the assistant: the activity feed says which.
enum VoiceInput: String, Encodable {
    case voice, typed
}

extension Notification.Name {
    /// Voice changed something (or undid it): screens on show reload, like web's invalidateQueries.
    static let voiceChangedThings = Notification.Name("voiceChangedThings")
}

extension APIClient {
    private struct VoiceConfig: Decodable { let enabled: Bool }
    private struct FollowUp: Encodable { let question: String; let answer: String }
    private struct InterpretBody: Encodable {
        let text: String
        let tab: String?
        let input: VoiceInput
        let followUp: FollowUp?
    }
    private struct ExecuteBody: Encodable {
        let actions: [VoiceAction]
        let commandId: UUID
        let undo: Bool
    }
    private struct ExecuteOut: Decodable { let results: [VoiceResult] }

    /// Whether to show the mic button.
    func voiceEnabled() async throws -> Bool {
        let config: VoiceConfig = try await get("/voice/config")
        return config.enabled
    }

    /// What they said (or typed) → cards to confirm. Changes nothing.
    func interpretVoice(householdId: UUID, text: String, input: VoiceInput, tab: String?,
                        followUp: (question: String, answer: String)? = nil) async throws -> VoiceInterpretation {
        try await send("POST", "/households/\(householdId)/voice/interpret",
                       body: InterpretBody(text: text, tab: tab, input: input,
                                           followUp: followUp.map { FollowUp(question: $0.question, answer: $0.answer) }))
    }

    /// Runs confirmed actions, or (`undo`) the undos a previous run returned. Once per command:
    /// a repeat gets 409.
    func executeVoice(householdId: UUID, commandId: UUID, actions: [VoiceAction], undo: Bool = false) async throws -> [VoiceResult] {
        let out: ExecuteOut = try await send("POST", "/households/\(householdId)/voice/execute",
                                             body: ExecuteBody(actions: actions, commandId: commandId, undo: undo))
        return out.results
    }
}
