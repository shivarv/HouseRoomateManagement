import SwiftUI

extension View {
    /// Keeps a tab on the one current house (the last picked, on any device): picking a house on
    /// any tab moves every tab to it, like web's header picker. Put it on the tab's root view, not
    /// on the picker, so tabs that aren't on screen follow too.
    func followsCurrentHouse(_ selection: Binding<UUID?>) -> some View {
        modifier(FollowsCurrentHouse(selection: selection))
    }
}

private struct FollowsCurrentHouse: ViewModifier {
    @Binding var selection: UUID?
    @Environment(Session.self) private var session

    func body(content: Content) -> some View {
        content
            .onChange(of: session.user?.lastHouseholdId) { _, id in follow(id) }
            .onAppear { follow(session.user?.lastHouseholdId) }
            .onChange(of: selection) { _, id in if let id { session.rememberHousehold(id) } }
    }

    private func follow(_ id: UUID?) {
        // Only once the tab has a house: before its first load, the tab picks for itself.
        if let id, selection != nil, selection != id { selection = id }
    }
}

/// The house a tab acts on, which also starts a new home. Mirrors the web header's dropdown:
/// while "Create a new home" or "Join" is open it shows that choice; when the sheet closes it
/// goes back to the previous house (or to the new one, once it's created).
struct HousePicker: View {
    let households: [Household]
    @Binding var selection: UUID?
    /// After a home was created or joined, so the tab can reload its list of houses.
    var onAdded: () async -> Void = {}

    @State private var adding: Adding?
    @Environment(Session.self) private var session

    enum Adding: String, Identifiable {
        case create, join
        var id: Self { self }
    }

    private enum Choice: Hashable {
        case house(UUID)
        case add(Adding)
    }

    var body: some View {
        Picker("House", selection: Binding<Choice>(
            get: { adding.map(Choice.add) ?? .house(selection ?? households.first?.id ?? UUID()) },
            set: { choice in
                switch choice {
                case .house(let id): selection = id
                case .add(let what): adding = what
                }
            }
        )) {
            Section {
                ForEach(households) { Text("🏠 \($0.name)").tag(Choice.house($0.id)) }
            }
            Section("Add a home") {
                Text("✨ Create a new home").tag(Choice.add(.create))
                Text("🔑 Join with an invite code").tag(Choice.add(.join))
            }
        }
        .sheet(item: $adding) { what in
            switch what {
            case .create:
                SetupWizardView { house in
                    selection = house.id
                    Task { await onAdded() }
                }
            case .join:
                JoinHouseholdSheet {
                    // Joining makes it my current house on the server: follow it.
                    Task {
                        await onAdded()
                        if let joined = try? await APIClient.shared.me().lastHouseholdId { selection = joined }
                    }
                }
            }
        }
    }
}
