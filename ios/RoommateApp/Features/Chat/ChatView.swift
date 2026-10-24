import SwiftUI

/// The house's group chat. Owned by the tab bar, so the unread badge stays current on other tabs.
/// Mirrors web ChatTab.tsx: polls for what's new while open, pages back on request.
@MainActor
@Observable
final class ChatModel {
    var households: [Household] = []
    var householdId: UUID?
    /// The house's people, for the header.
    var house: HouseholdDetail?
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
            async let detail = client.household(householdId)
            let page = try await client.chatPage(householdId: householdId)
            house = try? await detail
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

/// Mirrors web ChatTab.tsx: a header with who's in the house, messages grouped by person (others'
/// with their avatar), mine in the app's gradient, and a "new messages" pill when scrolled up.
/// Long-press a message to copy it, or edit or delete my own (admins can delete any).
struct ChatView: View {
    let model: ChatModel
    @Environment(Session.self) private var session
    @State private var text = ""
    @State private var editing: ChatMessage?
    @State private var editText = ""
    @State private var pendingDelete: ChatMessage?
    /// Whether the newest message is in view; if not, new ones count up in the pill instead.
    @State private var atBottom = true
    @State private var unseen = 0
    @FocusState private var composing: Bool

    static let brand = LinearGradient(colors: [Color(red: 0.31, green: 0.27, blue: 0.9), Color(red: 0.49, green: 0.23, blue: 0.93)],
                                      startPoint: .topLeading, endPoint: .bottomTrailing)  // indigo-600 → violet-600

    var body: some View {
        @Bindable var model = model
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 2) {
                        if model.hasMore {
                            Button("Load earlier messages") { Task { await model.loadOlder() } }
                                .font(.caption.weight(.medium))
                                .padding(.horizontal, 12).padding(.vertical, 5)
                                .background(Color.secondary.opacity(0.12), in: Capsule())
                                .buttonStyle(.plain)
                                .padding(.vertical, 8)
                        }
                        if model.hasLoaded && model.messages.isEmpty { emptyState }
                        ForEach(Array(model.messages.enumerated()), id: \.element.id) { i, m in
                            let prev = i > 0 ? model.messages[i - 1] : nil
                            let next = i + 1 < model.messages.count ? model.messages[i + 1] : nil
                            let newDay = prev.map { day($0.createdAt) != day(m.createdAt) } ?? true
                            if newDay {
                                Text(dayLabel(m.createdAt))
                                    .font(.caption2.weight(.semibold))
                                    .foregroundStyle(.secondary)
                                    .padding(.horizontal, 10).padding(.vertical, 4)
                                    .background(Color.secondary.opacity(0.12), in: Capsule())
                                    .padding(.vertical, 10)
                            }
                            bubble(
                                m,
                                first: newDay || prev?.author?.id != m.author?.id,
                                last: next.map { $0.author?.id != m.author?.id || day($0.createdAt) != day(m.createdAt) } ?? true
                            )
                            .id(m.id)
                        }
                        Color.clear.frame(height: 1)
                            .id("bottom")
                            .onAppear { atBottom = true; unseen = 0 }
                            .onDisappear { atBottom = false }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: model.messages.last?.id) { old, _ in
                    guard let last = model.messages.last else { return }
                    // Follow along when I'm at the bottom or sent it myself; otherwise count it.
                    if old == nil || atBottom || last.isMine {
                        withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                    } else {
                        unseen += 1
                    }
                }
                .onAppear { proxy.scrollTo("bottom", anchor: .bottom) }
                .overlay(alignment: .bottom) {
                    if unseen > 0 {
                        Button {
                            withAnimation { proxy.scrollTo("bottom", anchor: .bottom) }
                            unseen = 0
                        } label: {
                            Text("↓ \(unseen) new \(unseen == 1 ? "message" : "messages")")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 14).padding(.vertical, 7)
                                .background(Color.indigo, in: Capsule())
                                .shadow(color: .indigo.opacity(0.3), radius: 8, y: 4)
                        }
                        .padding(.bottom, 10)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                    }
                }
            }
            .safeAreaInset(edge: .top, spacing: 0) { header }
            .safeAreaInset(edge: .bottom, spacing: 0) { composer }
            .navigationTitle("Chat")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if model.households.count > 1 {
                    ToolbarItem(placement: .principal) {
                        HousePicker(households: model.households, selection: $model.householdId) { await model.load() }
                            .pickerStyle(.menu)
                    }
                }
            }
            .followsCurrentHouse($model.householdId)
            .onChange(of: model.householdId) { _, _ in
                unseen = 0
                Task { await model.load(preferred: session.preferredHousehold) }
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

    // MARK: Header

    /// The house at a glance: who's in this chat.
    private var header: some View {
        let members = (model.house?.members ?? []).filter(\.isActive)
        let name = model.house?.name ?? model.households.first { $0.id == model.householdId }?.name ?? "Your house"
        return HStack(spacing: 12) {
            Text("💬")
                .font(.title3)
                .frame(width: 42, height: 42)
                .background(.white.opacity(0.2), in: RoundedRectangle(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(.white.opacity(0.3)))
            VStack(alignment: .leading, spacing: 2) {
                Text("\(name) chat").font(.headline.weight(.heavy)).lineLimit(1)
                Text("👥 \(members.count) \(members.count == 1 ? "roommate" : "roommates") · messages stay in your house")
                    .font(.caption).foregroundStyle(.white.opacity(0.8)).lineLimit(1)
            }
            Spacer(minLength: 0)
            HStack(spacing: -8) {
                ForEach(members.prefix(4)) { m in
                    Avatar(name: m.displayName, size: 28).overlay(Circle().stroke(.white.opacity(0.7), lineWidth: 2))
                }
                if members.count > 4 {
                    Text("+\(members.count - 4)")
                        .font(.caption2.bold())
                        .frame(width: 28, height: 28)
                        .background(.white.opacity(0.25), in: Circle())
                        .overlay(Circle().stroke(.white.opacity(0.7), lineWidth: 2))
                }
            }
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 14).padding(.vertical, 12)
        .background {
            ZStack {
                LinearGradient(colors: [Color(red: 0.31, green: 0.27, blue: 0.9), Color(red: 0.49, green: 0.23, blue: 0.93), Color(red: 0.75, green: 0.15, blue: 0.83)],
                               startPoint: .leading, endPoint: .trailing)  // indigo → violet → fuchsia
                Circle().fill(.white.opacity(0.2)).frame(width: 110).blur(radius: 24).offset(x: 140, y: -40)
                Circle().fill(Color.cyan.opacity(0.3)).frame(width: 90).blur(radius: 24).offset(x: -10, y: 40)
            }
            .clipped()
        }
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .padding(.horizontal, 12)
        .padding(.top, 6)
        .padding(.bottom, 4)
        .background(.bar)
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Text("💬")
                .font(.title)
                .frame(width: 56, height: 56)
                .background(LinearGradient(colors: [.indigo, Color(red: 0.85, green: 0.27, blue: 0.94)], startPoint: .topLeading, endPoint: .bottomTrailing),
                            in: RoundedRectangle(cornerRadius: 16))
                .shadow(color: .indigo.opacity(0.3), radius: 10, y: 5)
            Text("Say hi to your house").font(.headline)
            Text("Everyone in \(model.house?.name ?? "the house") sees these messages.")
                .font(.subheadline).foregroundStyle(.secondary)
        }
        .multilineTextAlignment(.center)
        .padding(.top, 80)
    }

    // MARK: Composer

    private var composer: some View {
        let empty = text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        return VStack(spacing: 4) {
            if let error = model.error { ErrorBanner(message: error).padding(.horizontal) }
            HStack(alignment: .bottom, spacing: 8) {
                TextField("Message \(model.house?.name ?? "your house")…", text: $text, axis: .vertical)
                    .lineLimit(1...5)
                    .focused($composing)
                    .padding(.horizontal, 14).padding(.vertical, 9)
                    .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 20))
                    .overlay(RoundedRectangle(cornerRadius: 20).stroke(composing ? Color.indigo.opacity(0.5) : Color.secondary.opacity(0.2)))
                Button {
                    let draft = text
                    text = ""
                    Task { if !(await model.send(draft)) { text = draft } }
                } label: {
                    Image(systemName: "paperplane.fill")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(width: 38, height: 38)
                        .background(empty ? AnyShapeStyle(Color.secondary.opacity(0.35)) : AnyShapeStyle(Self.brand), in: Circle())
                }
                .disabled(empty || model.sending || model.householdId == nil)
                .animation(.easeOut(duration: 0.15), value: empty)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
        }
        .background(.bar)
    }

    // MARK: A message

    @ViewBuilder
    private func bubble(_ m: ChatMessage, first: Bool, last: Bool) -> some View {
        let author = m.author?.displayName ?? "Someone who left"
        HStack(alignment: .bottom, spacing: 8) {
            if m.isMine {
                Spacer(minLength: 48)
            } else {
                // Others' avatar once per run, at its last message; the space stays so the run lines up.
                if last { Avatar(name: author, size: 28) } else { Color.clear.frame(width: 28, height: 1) }
            }
            VStack(alignment: m.isMine ? .trailing : .leading, spacing: 2) {
                if first && !m.isMine {
                    Text(author).font(.caption.weight(.semibold)).foregroundStyle(.secondary).padding(.leading, 4)
                }
                Text(m.deleted ? "Message deleted" : m.body)
                    .italic(m.deleted)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .foregroundStyle(m.deleted ? Color.secondary : m.isMine ? Color.white : Color.primary)
                    .background(background(m), in: shape(mine: m.isMine, first: first, last: last))
                    .overlay {
                        if m.deleted { shape(mine: m.isMine, first: first, last: last).strokeBorder(Color.secondary.opacity(0.3), style: StrokeStyle(lineWidth: 1, dash: [4])) }
                    }
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
                if last {
                    Text(DayFormat.time(m.createdAt) + (m.editedAt != nil && !m.deleted ? " · edited" : ""))
                        .font(.caption2).foregroundStyle(.tertiary)
                        .padding(.horizontal, 4)
                }
            }
            if !m.isMine { Spacer(minLength: 48) }
        }
        .padding(.top, first ? 8 : 0)
    }

    private func background(_ m: ChatMessage) -> AnyShapeStyle {
        if m.deleted { return AnyShapeStyle(Color.clear) }
        return m.isMine ? AnyShapeStyle(Self.brand) : AnyShapeStyle(Color(.secondarySystemBackground))
    }

    /// Rounded, with tighter corners where a run of messages joins up on the sender's side.
    private func shape(mine: Bool, first: Bool, last: Bool) -> UnevenRoundedRectangle {
        let big: CGFloat = 18, small: CGFloat = 6
        return UnevenRoundedRectangle(
            topLeadingRadius: !mine && !first ? small : big,
            bottomLeadingRadius: !mine && !last ? small : big,
            bottomTrailingRadius: mine && !last ? small : big,
            topTrailingRadius: mine && !first ? small : big
        )
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
