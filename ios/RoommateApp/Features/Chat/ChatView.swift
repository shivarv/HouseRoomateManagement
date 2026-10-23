import SwiftUI

/// The house's group chat. Owned by the tab bar, so the unread badge stays current on other tabs.
/// Mirrors web ChatTab.tsx: polls for what's new while open, pages back on request.
@MainActor
@Observable
final class ChatModel {
    var households: [Household] = []
    var householdId: UUID?
    var messages: [ChatMessage] = []
    var hasMore = false
    var unread = 0
    var error: String?
    var hasLoaded = false
    var sending = false

    private var since: String?  // the latest change seen (new, edited or deleted)
    private let client = APIClient.shared

    func load(preferred: ([Household]) -> UUID? = { $0.first?.id }) async {
        defer { hasLoaded = true }
        do {
            households = try await client.households()
            if householdId == nil || !households.contains(where: { $0.id == householdId }) {
                householdId = preferred(households)
            }
            guard let householdId else { return }
            let page = try await client.chatPage(householdId: householdId)
            messages = []
            since = nil
            merge(page.messages)
            hasMore = page.hasMore
            await markRead()
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// New, edited or deleted messages since the last look.
    func poll() async {
        guard let householdId, hasLoaded else { return }
        do {
            let page = try await client.chatPage(householdId: householdId, after: since)
            if !page.messages.isEmpty {
                merge(page.messages)
                await markRead()
            }
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func loadOlder() async {
        guard let householdId, let oldest = messages.first else { return }
        do {
            let page = try await client.chatPage(householdId: householdId, before: oldest.createdAt)
            messages = page.messages + messages
            hasMore = page.hasMore
        } catch {
            self.error = error.localizedDescription
        }
    }

    func send(_ text: String) async -> Bool {
        let body = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let householdId, !body.isEmpty else { return false }
        sending = true
        defer { sending = false }
        do {
            merge([try await client.sendChat(householdId: householdId, body: body)])
            error = nil
            return true
        } catch {
            self.error = error.localizedDescription
            return false
        }
    }

    func edit(_ message: ChatMessage, to text: String) async {
        await change { try await self.client.editChat(message.id, body: text) }
    }

    func delete(_ message: ChatMessage) async {
        await change { try await self.client.deleteChat(message.id) }
    }

    /// The badge on the tab: others' messages I haven't seen.
    func refreshUnread() async {
        guard let id = householdId ?? households.first?.id else { return }
        unread = (try? await client.chatUnread(householdId: id).count) ?? unread
    }

    private func change(_ action: @escaping () async throws -> ChatMessage) async {
        do {
            merge([try await action()])
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func markRead() async {
        guard let householdId else { return }
        try? await client.markChatRead(householdId: householdId)
        unread = 0
    }

    /// Add new messages and replace edited or deleted ones, oldest first. Times are compared as
    /// dates: as text, "…:00Z" would sort after "…:00.5Z".
    private func merge(_ incoming: [ChatMessage]) {
        var byId = Dictionary(uniqueKeysWithValues: messages.map { ($0.id, $0) })
        for m in incoming {
            byId[m.id] = m
            if since.map({ time(m.changedAt) > time($0) }) ?? true { since = m.changedAt }
        }
        messages = byId.values.sorted { time($0.createdAt) < time($1.createdAt) }
    }

    private func time(_ stamp: String) -> Date { DayFormat.timestamp(stamp) ?? .distantPast }
}

struct ChatView: View {
    let model: ChatModel
    @Environment(Session.self) private var session
    @State private var text = ""
    @State private var editing: ChatMessage?
    @State private var editText = ""
    @State private var pendingDelete: ChatMessage?
    @FocusState private var composing: Bool

    var body: some View {
        @Bindable var model = model
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 2) {
                        if model.hasMore {
                            Button("Load earlier messages") { Task { await model.loadOlder() } }
                                .font(.footnote)
                                .padding(.vertical, 8)
                        }
                        if model.hasLoaded && model.messages.isEmpty {
                            ContentUnavailableView("Say hi to your house", systemImage: "bubble.left.and.bubble.right",
                                                   description: Text("Everyone in the house sees these messages."))
                                .padding(.top, 60)
                        }
                        ForEach(Array(model.messages.enumerated()), id: \.element.id) { i, m in
                            let prev = i > 0 ? model.messages[i - 1] : nil
                            if prev.map({ day($0.createdAt) != day(m.createdAt) }) ?? true {
                                Text(dayLabel(m.createdAt))
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(.secondary)
                                    .padding(.vertical, 8)
                            }
                            bubble(m, showAuthor: !m.isMine && (prev?.author?.id != m.author?.id || prev.map { day($0.createdAt) != day(m.createdAt) } ?? true))
                                .id(m.id)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.bottom, 8)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: model.messages.last?.id) { _, last in
                    if let last { withAnimation { proxy.scrollTo(last, anchor: .bottom) } }
                }
                .onAppear { if let last = model.messages.last?.id { proxy.scrollTo(last, anchor: .bottom) } }
            }
            .safeAreaInset(edge: .bottom) { composer }
            .navigationTitle("Chat")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if !model.households.isEmpty {
                    ToolbarItem(placement: .principal) {
                        HousePicker(households: model.households, selection: $model.householdId) { await model.load() }
                            .pickerStyle(.menu)
                    }
                }
            }
            .onChange(of: model.householdId) { _, id in
                if let id { session.rememberHousehold(id) }
                Task { await model.load() }
            }
            // While the chat is on screen: check for new messages every few seconds.
            .task {
                if !model.hasLoaded { await model.load(preferred: session.preferredHousehold) }
                while !Task.isCancelled {
                    try? await Task.sleep(for: .seconds(4))
                    await model.poll()
                }
            }
            .alert("Edit message", isPresented: Binding(get: { editing != nil }, set: { if !$0 { editing = nil } })) {
                TextField("Message", text: $editText, axis: .vertical)
                Button("Save") {
                    if let m = editing, !editText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        Task { await model.edit(m, to: editText) }
                    }
                    editing = nil
                }
                Button("Cancel", role: .cancel) { editing = nil }
            }
            .confirmationDialog("Delete this message?", isPresented: Binding(get: { pendingDelete != nil }, set: { if !$0 { pendingDelete = nil } }),
                                titleVisibility: .visible) {
                Button("Delete", role: .destructive) {
                    if let m = pendingDelete { Task { await model.delete(m) } }
                }
            }
        }
    }

    private var composer: some View {
        VStack(spacing: 4) {
            if let error = model.error { ErrorBanner(message: error).padding(.horizontal) }
            HStack(alignment: .bottom, spacing: 8) {
                TextField("Message your house…", text: $text, axis: .vertical)
                    .lineLimit(1...5)
                    .focused($composing)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(Color.secondary.opacity(0.1), in: RoundedRectangle(cornerRadius: 18))
                Button {
                    let draft = text
                    text = ""
                    Task { if !(await model.send(draft)) { text = draft } }
                } label: {
                    Image(systemName: "arrow.up.circle.fill").font(.system(size: 30))
                }
                .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.sending || model.householdId == nil)
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
        .background(.bar)
    }

    @ViewBuilder
    private func bubble(_ m: ChatMessage, showAuthor: Bool) -> some View {
        VStack(alignment: m.isMine ? .trailing : .leading, spacing: 2) {
            if showAuthor {
                Text(m.author?.displayName ?? "Someone who left").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    .padding(.top, 8)
            }
            Text(m.deleted ? "Message deleted" : m.body)
                .italic(m.deleted)
                .padding(.horizontal, 12).padding(.vertical, 8)
                .foregroundStyle(m.deleted ? Color.secondary : m.isMine ? Color.white : Color.primary)
                .background(m.deleted ? Color.secondary.opacity(0.1) : m.isMine ? Color.accentColor : Color.secondary.opacity(0.15),
                            in: RoundedRectangle(cornerRadius: 18))
                .contextMenu {
                    if !m.deleted {
                        Button("Copy", systemImage: "doc.on.doc") { UIPasteboard.general.string = m.body }
                    }
                    if m.canEdit {
                        Button("Edit", systemImage: "pencil") { editText = m.body; editing = m }
                    }
                    if m.canDelete {
                        Button("Delete", systemImage: "trash", role: .destructive) { pendingDelete = m }
                    }
                }
            Text(DayFormat.time(m.createdAt) + (m.editedAt != nil && !m.deleted ? " · edited" : ""))
                .font(.caption2).foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, alignment: m.isMine ? .trailing : .leading)
        .padding(m.isMine ? .leading : .trailing, 48)
    }

    private func day(_ timestamp: String) -> Date? {
        DayFormat.timestamp(timestamp).map { Calendar.current.startOfDay(for: $0) }
    }

    private func dayLabel(_ timestamp: String) -> String {
        guard let date = DayFormat.timestamp(timestamp) else { return "" }
        if Calendar.current.isDateInToday(date) { return "Today" }
        if Calendar.current.isDateInYesterday(date) { return "Yesterday" }
        return date.formatted(.dateTime.weekday(.wide).month(.abbreviated).day())
    }
}
