import SwiftUI

/// What happened when I pressed "I'll take it". The server decides who was first.
enum SwapOutcome: Hashable {
    case won(Swap)
    case lost(String)  // someone else got there first (409)
    case failed(String)  // network or other error: safe to retry

    /// Accepting twice returns the same result, so a retry after a network error is harmless.
    @MainActor
    static func accept(_ swap: Swap) async -> SwapOutcome {
        do {
            return .won(try await APIClient.shared.acceptSwap(swap.id))
        } catch let error as APIError where error.status == 409 {
            return .lost(error.message)
        } catch {
            return .failed(error.localizedDescription)
        }
    }
}

/// Swap requests I can take, as a List section. Mirrors web/src/features/chores/SwapRequests.tsx.
struct SwapRequestsSection: View {
    let swaps: [Swap]
    var showHousehold = false
    let accept: (Swap) async -> SwapOutcome

    // "Not me" only hides a request on this device; nothing is sent and others still see it.
    @AppStorage("hiddenSwaps") private var hiddenRaw = ""
    @State private var results: [UUID: Result] = [:]
    @State private var pending: Set<UUID> = []

    private struct Result {
        let swap: Swap
        let outcome: SwapOutcome
    }

    private var hidden: Set<String> { Set(hiddenRaw.split(separator: ",").map(String.init)) }

    private var offers: [Swap] {
        swaps.filter { $0.canAccept && !hidden.contains($0.id.uuidString) && results[$0.id] == nil }
    }

    var body: some View {
        if !offers.isEmpty || !results.isEmpty {
            Section("Swap requests") {
                ForEach(Array(results.values), id: \.swap.id) { resultRow($0) }
                ForEach(offers) { offerRow($0) }
            }
        }
    }

    private func offerRow(_ swap: Swap) -> some View {
        let isPending = pending.contains(swap.id)
        return VStack(alignment: .leading, spacing: 8) {
            Text("🔁 \(Text(swap.requester.displayName).bold()) needs someone for \(Text(swap.chore.name).bold()) · \(Self.turn(swap))")
                .font(.subheadline)
            if showHousehold {
                Text(swap.householdName).font(.caption).foregroundStyle(.secondary)
            }
            if let note = swap.note {
                Text("“\(note)”").font(.caption).foregroundStyle(.secondary)
            }
            if let payback = swap.paybackPreview {
                Text("You'd give back your \(swap.chore.name) turn on \(Text(Self.turn(swap, payback)).bold()).")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            HStack {
                Spacer()
                Button("Not me") { hide(swap.id) }
                    .buttonStyle(.bordered)
                    .tint(.gray)
                    .disabled(isPending)
                Button(isPending ? "Taking…" : "I'll take it") { take(swap) }
                    .buttonStyle(.borderedProminent)
                    .disabled(isPending)
            }
        }
        .padding(.vertical, 4)
    }

    @ViewBuilder
    private func resultRow(_ result: Result) -> some View {
        let swap = result.swap
        HStack(alignment: .firstTextBaseline) {
            switch result.outcome {
            case .won(let won):
                Text("🤝 You took \(won.requester.displayName)'s \(won.chore.name) (\(Self.turn(won))). \(won.requester.displayName) does your turn on \(Text(won.paybackDate.map { Self.turn(won, $0) } ?? "your next turn").bold()).")
                    .foregroundStyle(.green)
            case .lost(let message):
                Text("\(swap.requester.displayName)'s \(swap.chore.name) (\(Self.turn(swap))): \(message)")
                    .foregroundStyle(.secondary)
            case .failed(let message):
                VStack(alignment: .leading, spacing: 6) {
                    Text(message).foregroundStyle(.red)
                    Button("Try again") {
                        results[swap.id] = nil
                        take(swap)
                    }
                    .buttonStyle(.bordered)
                }
            }
            Spacer(minLength: 0)
            Button {
                results[swap.id] = nil
            } label: {
                Image(systemName: "xmark").foregroundStyle(.secondary)
            }
            .buttonStyle(.borderless)
            .accessibilityLabel("Dismiss")
        }
        .font(.subheadline)
    }

    private func take(_ swap: Swap) {
        pending.insert(swap.id)
        Task {
            let outcome = await accept(swap)
            pending.remove(swap.id)
            results[swap.id] = Result(swap: swap, outcome: outcome)
        }
    }

    private func hide(_ id: UUID) {
        hiddenRaw = (Array(hidden).suffix(99) + [id.uuidString]).joined(separator: ",")
    }

    static func turn(_ swap: Swap, _ date: String? = nil) -> String {
        let day = date ?? swap.givenDate
        return swap.chore.frequency == .weekly ? "week of \(DayFormat.short(day))" : DayFormat.short(day)
    }
}
