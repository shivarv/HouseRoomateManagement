import SwiftUI

/// Quick picks for "Ask for help". Mirrors web/src/features/help/presets.ts.
enum HelpPresets {
    static let all: [(icon: String, title: String)] = [
        ("🚪", "Open the door"),
        ("🛒", "Buy groceries"),
        ("📦", "Pick up a package"),
        ("🗑️", "Take out the trash"),
        ("🧽", "Clean up the kitchen"),
        ("🍳", "Cook a meal"),
        ("💪", "Lend a hand moving something"),
    ]

    static func icon(for title: String) -> String {
        all.first { $0.title == title }?.icon ?? "🙋"
    }
}

@MainActor
@Observable
final class NotificationsViewModel {
    var requests: [HelpRequest] = []
    var households: [Household] = []
    var error: String?
    var hasLoaded = false
    /// Per-request messages, e.g. "Bea already marked it done" after losing a race.
    var notices: [UUID: String] = [:]

    private let client = APIClient.shared

    var others: [HelpRequest] { requests.filter { !$0.isMine } }
    var mine: [HelpRequest] { requests.filter(\.isMine) }
    /// The tab badge: requests other people are waiting on.
    var waitingCount: Int { requests.filter { !$0.isDone && !$0.isMine }.count }

    func load() async {
        defer { hasLoaded = true }
        do {
            async let r = client.helpRequests()
            async let h = client.households()
            (requests, households) = try await (r, h)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Runs an action on one request, then reloads. A 409 is shown on that request, not as an error.
    func act(on id: UUID, _ action: @escaping () async throws -> Void) async {
        do {
            try await action()
            notices[id] = nil
        } catch {
            notices[id] = error.localizedDescription
        }
        await load()
    }

    func markDone(_ r: HelpRequest) async { await act(on: r.id) { _ = try await self.client.markHelpDone(r.id) } }
    func reopen(_ r: HelpRequest) async { await act(on: r.id) { _ = try await self.client.reopenHelpRequest(r.id) } }
    func withdraw(_ r: HelpRequest) async { await act(on: r.id) { try await self.client.withdrawHelpRequest(r.id) } }

    /// Create (no `editing`) or save my edits. Returns an error message to show in the form.
    func save(editing: HelpRequest?, householdId: UUID?, title: String, details: String) async -> String? {
        do {
            if let editing {
                _ = try await client.updateHelpRequest(editing.id, title: title, details: details)
            } else if let householdId {
                _ = try await client.askForHelp(householdId: householdId, title: title,
                                                details: details.isEmpty ? nil : details)
            }
            await load()
            return nil
        } catch {
            return error.localizedDescription
        }
    }
}

/// 🔔 Notifications (`.everyone`): what other people need, anyone can mark it done.
/// 🙋 Help requests (`.mine`): what I asked for and its status, plus asking for something new.
struct NotificationsView: View {
    enum Scope { case everyone, mine }

    let model: NotificationsViewModel
    var scope: Scope = .everyone

    @Environment(\.scenePhase) private var scenePhase
    @State private var form: FormTarget?

    /// What the form sheet is for: a new request, or editing one of mine.
    struct FormTarget: Identifiable {
        let editing: HelpRequest?
        var id: String { editing?.id.uuidString ?? "new" }
    }

    private var multiHouse: Bool { model.households.count > 1 }

    var body: some View {
        NavigationStack {
            List {
                if model.error != nil {
                    ErrorBanner(message: model.error)
                }
                let shown = scope == .everyone ? model.others : model.mine
                let open = shown.filter { !$0.isDone }
                let done = shown.filter(\.isDone)
                Section(scope == .everyone ? "Needs a hand" : "Waiting for help") {
                    if open.isEmpty && model.hasLoaded {
                        Text(scope == .everyone ? "Nobody needs help right now 🎉"
                                                : "Nothing open. Tap + when you need a hand.")
                            .foregroundStyle(.secondary)
                    }
                    ForEach(open) { row($0) }
                }
                if !done.isEmpty {
                    Section(scope == .everyone ? "Recently done" : "Done") {
                        ForEach(done) { row($0) }
                    }
                }
            }
            .navigationTitle(scope == .everyone ? "Notifications" : "Help requests")
            .toolbar {
                if scope == .mine && !model.households.isEmpty {
                    Button("Ask for help", systemImage: "plus") { form = FormTarget(editing: nil) }
                }
            }
            .sheet(item: $form) { target in
                HelpFormView(model: model, editing: target.editing)
            }
            .refreshable { await model.load() }
            .task { await model.load() }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { Task { await model.load() } }
            }
        }
    }

    private func row(_ r: HelpRequest) -> some View {
        HelpRow(
            request: r,
            showHousehold: multiHouse,
            notice: model.notices[r.id],
            onDone: { Task { await model.markDone(r) } },
            onUndo: { Task { await model.reopen(r) } },
            onEdit: { form = FormTarget(editing: r) },
            onWithdraw: { Task { await model.withdraw(r) } },
            onDismissNotice: { model.notices[r.id] = nil }
        )
    }
}

private struct HelpRow: View {
    let request: HelpRequest
    var showHousehold = false
    var notice: String?
    let onDone: () -> Void
    let onUndo: () -> Void
    let onEdit: () -> Void
    let onWithdraw: () -> Void
    let onDismissNotice: () -> Void

    @State private var confirmWithdraw = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 12) {
                Text(request.isDone ? "✓" : HelpPresets.icon(for: request.title))
                    .font(.title3)
                    .frame(width: 40, height: 40)
                    .background(request.isDone ? Color.green.opacity(0.15) : Color.orange.opacity(0.15), in: Circle())
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        Text(request.title)
                            .font(.headline)
                            .strikethrough(request.isDone)
                            .foregroundStyle(request.isDone ? .secondary : .primary)
                        Badge(text: request.isDone ? "Done" : "Open", color: request.isDone ? .green : .orange)
                    }
                    if let details = request.details {
                        Text(details).font(.subheadline)
                    }
                    Text(subtitle).font(.caption).foregroundStyle(.secondary)
                    if request.isDone, let by = request.doneBy {
                        Text("Done by \(by.displayName)" + (request.doneAt.map { " · \(Self.when($0))" } ?? ""))
                            .font(.caption.weight(.medium))
                            .foregroundStyle(.green)
                    }
                }
            }

            HStack {
                Spacer()
                if !request.isDone && request.isMine {
                    Button("Edit", action: onEdit).buttonStyle(.bordered)
                    Button("Withdraw", role: .destructive) { confirmWithdraw = true }.buttonStyle(.bordered)
                }
                if !request.isDone {
                    Button(request.isMine ? "Mark done" : "I helped ✓", action: onDone)
                        .buttonStyle(.borderedProminent)
                }
                if request.isDone && request.canReopen {
                    Button("Undo", action: onUndo).buttonStyle(.bordered).tint(.gray)
                }
            }

            if let notice {
                HStack {
                    Text(notice).font(.footnote).foregroundStyle(.secondary)
                    Spacer()
                    Button(action: onDismissNotice) { Image(systemName: "xmark") }
                        .buttonStyle(.borderless)
                        .accessibilityLabel("Dismiss")
                }
                .padding(8)
                .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(.vertical, 4)
        .confirmationDialog("Withdraw “\(request.title)”?", isPresented: $confirmWithdraw, titleVisibility: .visible) {
            Button("Withdraw", role: .destructive, action: onWithdraw)
        }
    }

    private var subtitle: String {
        var parts = ["\(request.isMine ? "You" : request.requester.displayName) asked · \(Self.when(request.createdAt))"]
        if showHousehold { parts.append(request.householdName) }
        return parts.joined(separator: " · ")
    }

    static func when(_ timestamp: String) -> String {
        guard let date = DayFormat.timestamp(timestamp) else { return "" }
        return date.formatted(.relative(presentation: .named))
    }
}

/// Ask for help (new), or edit my own open request.
private struct HelpFormView: View {
    let model: NotificationsViewModel
    let editing: HelpRequest?

    @Environment(\.dismiss) private var dismiss
    @Environment(Session.self) private var session
    @State private var choice: String = ""  // a preset title, or "custom"
    @State private var custom = ""
    @State private var details = ""
    @State private var householdId: UUID?
    @State private var error: String?
    @State private var saving = false

    private static let customChoice = "custom"
    private var title: String {
        choice == Self.customChoice ? custom.trimmingCharacters(in: .whitespaces) : choice
    }

    var body: some View {
        NavigationStack {
            Form {
                if editing == nil && model.households.count > 1 {
                    Picker("Which house?", selection: $householdId) {
                        ForEach(model.households) { Text($0.name).tag(Optional($0.id)) }
                    }
                }
                Section("What do you need?") {
                    ForEach(HelpPresets.all, id: \.title) { preset in
                        choiceRow("\(preset.icon) \(preset.title)", value: preset.title)
                    }
                    choiceRow("✏️ Something else…", value: Self.customChoice)
                    if choice == Self.customChoice {
                        TextField("Say what you need help with", text: $custom)
                    }
                }
                Section("Details (optional)") {
                    TextField("e.g. milk, eggs and bread · it's at the front desk", text: $details, axis: .vertical)
                        .lineLimit(2...5)
                }
                if let error {
                    ErrorBanner(message: error)
                }
            }
            .navigationTitle(editing == nil ? "Ask for help" : "Edit request")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(editing == nil ? "Post" : "Save") { save() }
                        .disabled(title.isEmpty || saving)
                }
            }
            .onAppear(perform: fill)
        }
    }

    private func choiceRow(_ label: String, value: String) -> some View {
        Button {
            choice = value
        } label: {
            HStack {
                Text(label).foregroundStyle(.primary)
                Spacer()
                if choice == value { Image(systemName: "checkmark").foregroundStyle(Color.accentColor) }
            }
        }
    }

    private func fill() {
        householdId = editing?.householdId ?? session.preferredHousehold(in: model.households)
        guard let editing else { return }
        if HelpPresets.all.contains(where: { $0.title == editing.title }) {
            choice = editing.title
        } else {
            choice = Self.customChoice
            custom = editing.title
        }
        details = editing.details ?? ""
    }

    private func save() {
        saving = true
        Task {
            let failure = await model.save(editing: editing, householdId: householdId, title: title,
                                           details: details.trimmingCharacters(in: .whitespacesAndNewlines))
            saving = false
            if let failure { error = failure } else { dismiss() }
        }
    }
}
