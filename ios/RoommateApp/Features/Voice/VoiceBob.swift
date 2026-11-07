import SwiftUI

/// The mic button on every tab: say what happened ("Raj took out the trash, I bought milk"),
/// check the cards, Confirm. Nothing changes before Confirm; Undo after. Mirrors web VoiceBob.
struct VoiceBob: View {
    let householdId: UUID
    /// The screen it's on: a hint for voice when a phrase could mean two things.
    let tab: String
    /// Sits higher where a screen has its own bar at the bottom (Chat's composer).
    var lifted = false

    @State private var enabled = false
    @State private var open = false
    @State private var toast: Toast?

    struct Toast: Identifiable {
        let id = UUID()
        let text: String
        let undo: [VoiceAction]
        let commandId: UUID
    }

    var body: some View {
        VStack(alignment: .trailing, spacing: 12) {
            if let toast {
                UndoToast(householdId: householdId, toast: toast) { self.toast = nil }
                    .id(toast.id)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
            if enabled {
                Button {
                    open = true
                } label: {
                    Image(systemName: "mic.fill")
                        .font(.title2.weight(.semibold))
                        .foregroundStyle(.white)
                        .frame(width: 56, height: 56)
                        .background(Brand.diagonal, in: Circle())
                        .shadow(color: Brand.fuchsia.opacity(0.35), radius: 10, y: 4)
                }
                .accessibilityLabel("Voice command: say what you did")
            }
        }
        .padding(.trailing, 16)
        .padding(.bottom, lifted ? 128 : 64)
        .animation(.spring(duration: 0.3), value: toast?.id)
        .task {
            // Only shown when the server has voice turned on.
            enabled = (try? await APIClient.shared.voiceEnabled()) ?? false
        }
        .sheet(isPresented: $open) {
            VoiceSheet(householdId: householdId, tab: tab) { text, undo, commandId in
                open = false
                toast = Toast(text: text, undo: undo, commandId: commandId)
            }
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
        }
    }
}

// MARK: - Sheet

private struct VoiceSheet: View {
    let householdId: UUID
    let tab: String
    let onDone: (String, [VoiceAction], UUID) -> Void

    enum Step { case listening, typing, thinking, review }

    @Environment(\.dismiss) private var dismiss
    @State private var listener = SpeechListener()
    @State private var step: Step = .listening
    @State private var text = ""
    @State private var input: VoiceInput = .voice
    @State private var micNote: String?
    @State private var canSpeak = true
    @State private var answer: VoiceInterpretation?
    @State private var picked: [Bool] = []
    @State private var error: String?
    /// After a Confirm where something couldn't be done: what was sent, and each one's result.
    @State private var checked: (sent: [VoiceProposal], results: [VoiceResult])?
    /// Set on the first tap, so a second tap before the answer is back does nothing.
    @State private var confirming = false
    @FocusState private var typingFocused: Bool

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    switch step {
                    case .listening: listening
                    case .typing: typing
                    case .thinking: thinking
                    case .review: review
                    }
                }
                .padding()
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
        .task(id: step) {
            if step == .listening { await listen() }
            if step == .typing { typingFocused = true }
        }
        .onDisappear { listener.cancel() }
    }

    private var title: String {
        switch step {
        case .listening: "🎙 Listening…"
        case .thinking: "Working it out…"
        default: "Say what you did"
        }
    }

    // MARK: Steps

    private var listening: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(listener.text.isEmpty ? "e.g. “Raj took out the trash and I bought milk”" : listener.text)
                .foregroundStyle(listener.text.isEmpty ? .secondary : .primary)
                .frame(maxWidth: .infinity, minHeight: 60, alignment: .topLeading)
                .padding(12)
                .background(Brand.indigo.opacity(0.08), in: RoundedRectangle(cornerRadius: 16))
            Text("Try: “I did the dishes”, “Sam took out the trash”, “add milk and eggs”, “bought the bread”, “can someone pick up my parcel”.")
                .font(.footnote)
                .foregroundStyle(.secondary)
            HStack {
                Button { listener.stop() } label: {
                    Text("Done").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Brand.indigo)
                Button("⌨︎ Type") {
                    listener.cancel()
                    step = .typing
                }
                .buttonStyle(.bordered)
            }
        }
    }

    private var typing: some View {
        VStack(alignment: .leading, spacing: 12) {
            TextField("e.g. I paid the gas bill, it was 42.50", text: $text, axis: .vertical)
                .lineLimit(3...6)
                .focused($typingFocused)
                .padding(12)
                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 16))
                .onChange(of: text) { _, new in if new.count > 500 { text = String(new.prefix(500)) } }
                .submitLabel(.go)
                .onSubmit(submitTyped)
            if let micNote {
                Text(micNote).font(.footnote).foregroundStyle(.orange)
            }
            HStack {
                Button(action: submitTyped) {
                    Text("Go").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Brand.indigo)
                .disabled(trimmed(text).isEmpty)
                if canSpeak {
                    Button("🎤 Speak") { step = .listening }
                        .buttonStyle(.bordered)
                }
            }
        }
    }

    private var thinking: some View {
        HStack(spacing: 10) {
            ProgressView()
            Text("“\(text)”").foregroundStyle(.secondary)
        }
    }

    private var review: some View {
        VStack(alignment: .leading, spacing: 12) {
            if !text.isEmpty {
                Text("“\(text)”").font(.subheadline).foregroundStyle(.secondary)
            }
            ErrorBanner(message: error)
            ForEach(answer?.notes ?? [], id: \.self) { note in
                Text(note)
                    .font(.subheadline)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(Color.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
            }
            if let question = answer?.question {
                Text(question).font(.subheadline.weight(.medium))
                FlowButtons(options: answer?.options ?? []) { option in
                    Task { await interpret(followUp: (question, option)) }
                }
            }
            if let proposals = answer?.proposals, !proposals.isEmpty {
                ForEach(Array(proposals.enumerated()), id: \.offset) { i, proposal in
                    card(proposal, index: i)
                }
            }
            HStack {
                if let proposals = answer?.proposals, !proposals.isEmpty {
                    Button { confirm() } label: {
                        Text(confirmLabel).frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Brand.indigo)
                    .disabled(confirming || toSend.isEmpty)
                }
                Button(canSpeak ? "🎤 Again" : "Try again") {
                    text = ""
                    step = canSpeak ? .listening : .typing
                }
                .buttonStyle(.bordered)
            }
        }
    }

    private func card(_ proposal: VoiceProposal, index i: Int) -> some View {
        let problem = errorFor(proposal)
        let isOn = picked.indices.contains(i) && picked[i]
        return Button {
            guard checked == nil, picked.indices.contains(i) else { return }
            picked[i].toggle()
        } label: {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: isOn ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(isOn ? Brand.indigo : .secondary)
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(proposal.icon) \(proposal.summary)")
                        .foregroundStyle(.primary)
                        .multilineTextAlignment(.leading)
                    if let problem {
                        Text(problem).font(.caption).foregroundStyle(.red)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(12)
            .background(problem == nil ? Color(.secondarySystemBackground) : Color.red.opacity(0.08),
                        in: RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
    }

    // MARK: Logic

    private var chosen: [VoiceProposal] {
        guard let proposals = answer?.proposals else { return [] }
        return proposals.enumerated().filter { picked.indices.contains($0.offset) && picked[$0.offset] }.map(\.element)
    }

    /// After a check found problems: the ones that can still be done. Otherwise what's ticked.
    private var toSend: [VoiceProposal] {
        if let checked {
            return zip(checked.sent, checked.results).filter { $0.1.error == nil }.map(\.0)
        }
        return chosen
    }

    private var confirmLabel: String {
        if confirming { return "Doing it…" }
        if checked != nil { return "Do the other \(toSend.count)" }
        return toSend.count > 1 ? "Confirm all \(toSend.count)" : "Confirm"
    }

    private func errorFor(_ proposal: VoiceProposal) -> String? {
        guard let checked, let i = checked.sent.firstIndex(of: proposal), checked.results.indices.contains(i) else { return nil }
        return checked.results[i].error
    }

    private func trimmed(_ s: String) -> String { s.trimmingCharacters(in: .whitespacesAndNewlines) }

    private func listen() async {
        micNote = nil
        text = ""
        let problem = await listener.start { said in
            if said.isEmpty {
                micNote = "Didn't hear anything. Tap Speak to try again, or type."
                step = .typing
            } else {
                text = said
                input = .voice
                Task { await interpret() }
            }
        }
        switch problem {
        case .notAllowed?:
            canSpeak = false
            micNote = "Microphone or speech recognition is off for Roommates. Turn it on in Settings, or type instead."
            step = .typing
        case .unavailable?:
            canSpeak = false
            micNote = "Speech recognition isn't available right now. Type instead."
            step = .typing
        case nil:
            break
        }
    }

    private func submitTyped() {
        guard !trimmed(text).isEmpty else { return }
        text = trimmed(text)
        input = .typed
        Task { await interpret() }
    }

    private func interpret(followUp: (question: String, answer: String)? = nil) async {
        step = .thinking
        error = nil
        do {
            let res = try await APIClient.shared.interpretVoice(householdId: householdId, text: text, input: input,
                                                               tab: tab, followUp: followUp)
            answer = res
            picked = res.proposals.map { _ in true }
            checked = nil
        } catch {
            self.error = error.localizedDescription
        }
        step = .review
    }

    private func confirm() {
        guard !confirming, let commandId = answer?.commandId else { return }
        let sent = toSend
        guard !sent.isEmpty else { return }
        confirming = true
        error = nil
        Task {
            defer { confirming = false }
            do {
                let results = try await APIClient.shared.executeVoice(householdId: householdId, commandId: commandId,
                                                                      actions: sent.map(\.action))
                if results.contains(where: { $0.error != nil }) {
                    // Nothing ran: show which one can't be done, and offer the rest.
                    checked = (sent, results)
                    return
                }
                NotificationCenter.default.post(name: .voiceChangedThings, object: nil)
                let done = results.filter(\.ok)
                let failed = results.filter { !$0.ok }
                let message = !failed.isEmpty ? "Done \(done.count) of \(sent.count). \(failed[0].error ?? "")"
                    : done.count == 1 ? "Done: \(done[0].summary)" : "Done: \(done.count) things"
                onDone(message, done.flatMap { $0.undo ?? [] }, commandId)
            } catch {
                self.error = error.localizedDescription
            }
        }
    }
}

/// The answers to a question voice asked back, as buttons that wrap.
private struct FlowButtons: View {
    let options: [String]
    let pick: (String) -> Void

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack { buttons }
            VStack(alignment: .leading) { buttons }
        }
    }

    private var buttons: some View {
        ForEach(options, id: \.self) { option in
            Button(option) { pick(option) }
                .buttonStyle(.bordered)
                .tint(Brand.violet)
        }
    }
}

// MARK: - Undo toast

/// "Done · Undo" for a few seconds after voice did something. Undo asks first.
private struct UndoToast: View {
    let householdId: UUID
    let toast: VoiceBob.Toast
    let close: () -> Void

    @State private var asking = false
    @State private var undoing = false
    @State private var failure: String?

    var body: some View {
        HStack(spacing: 12) {
            Text(failure ?? (asking ? "Undo this? Are you sure?" : toast.text))
                .font(.subheadline)
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity, alignment: .leading)
            if !toast.undo.isEmpty && failure == nil {
                if asking {
                    Button("Yes, undo", action: undo).fontWeight(.semibold).foregroundStyle(Brand.fuchsia)
                    Button("Keep it") { asking = false }.foregroundStyle(.white.opacity(0.75))
                } else {
                    Button(undoing ? "Undoing…" : "Undo") { asking = true }
                        .fontWeight(.semibold)
                        .foregroundStyle(Brand.fuchsia)
                        .disabled(undoing)
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color(red: 0.06, green: 0.09, blue: 0.16), in: RoundedRectangle(cornerRadius: 16))
        .shadow(radius: 8, y: 4)
        .frame(maxWidth: 380)
        .padding(.leading, 16)
        .onTapGesture { if failure != nil { close() } }  // read why it couldn't: tap to dismiss
        // Stays up while they're deciding, undoing, or reading why it couldn't.
        .task(id: asking || undoing || failure != nil) {
            guard !asking, !undoing, failure == nil else { return }
            try? await Task.sleep(for: .seconds(8))
            if !Task.isCancelled { close() }
        }
    }

    private func undo() {
        guard !undoing else { return }  // extra taps before the re-render do nothing
        undoing = true
        asking = false
        Task {
            defer {
                undoing = false
                NotificationCenter.default.post(name: .voiceChangedThings, object: nil)
            }
            do {
                let results = try await APIClient.shared.executeVoice(householdId: householdId, commandId: toast.commandId,
                                                                      actions: toast.undo, undo: true)
                if let failed = results.first(where: { $0.error != nil }) {
                    failure = "Couldn't undo: \(failed.error ?? "")"
                } else {
                    close()
                }
            } catch {
                failure = "Couldn't undo: \(error.localizedDescription)"
            }
        }
    }
}
