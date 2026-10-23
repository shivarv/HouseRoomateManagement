import SwiftUI

struct HouseholdsView: View {
    @State private var households: [Household] = []
    @State private var hasLoaded = false
    @State private var error: String?
    @State private var showCreate = false
    @State private var showJoin = false

    var body: some View {
        NavigationStack {
            List {
                ErrorBanner(message: error)
                ForEach(households) { h in
                    NavigationLink(value: h.id) {
                        VStack(alignment: .leading, spacing: 2) {
                            HStack {
                                Text(h.name).font(.headline)
                                if h.myRole == .admin { Badge(text: "Admin", color: .accentColor) }
                            }
                            Text([h.address, h.timezone].compactMap { $0 }.joined(separator: " · "))
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .overlay {
                if hasLoaded && households.isEmpty {
                    ContentUnavailableView {
                        Label("No households", systemImage: "house")
                    } description: {
                        Text("Create a household, or join one with an invite code from your house admin.")
                    } actions: {
                        Button("Create a new home") { showCreate = true }.buttonStyle(.borderedProminent)
                        Button("Join with code") { showJoin = true }
                    }
                }
            }
            .navigationTitle("Households")
            .navigationDestination(for: UUID.self) { HouseholdDetailView(householdId: $0) }
            .toolbar {
                Menu {
                    Button("Create a new home", systemImage: "sparkles") { showCreate = true }
                    Button("Join with invite code", systemImage: "person.badge.plus") { showJoin = true }
                } label: {
                    Image(systemName: "plus")
                }
            }
            // Creating always goes through the guided setup, so every new house starts complete.
            .sheet(isPresented: $showCreate) { SetupWizardView { _ in Task { await load() } } }
            .sheet(isPresented: $showJoin) { JoinHouseholdSheet { Task { await load() } } }
            .refreshable { await load() }
            .task { await load() }
            .onAppear { Task { await load() } }  // e.g. after a home was deleted in Settings
        }
    }

    private func load() async {
        do {
            households = try await APIClient.shared.households()
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        hasLoaded = true
    }
}

struct JoinHouseholdSheet: View {
    var onJoined: () -> Void
    @Environment(\.dismiss) private var dismiss
    @Environment(Session.self) private var session
    @State private var code = ""
    @State private var preview: InvitePreview?
    @State private var error: String?
    @State private var isBusy = false

    var body: some View {
        NavigationStack {
            Form {
                if let preview {
                    Section {
                        ForEach(preview.unclaimedMembers) { m in
                            Button("I'm \(m.displayName)") { Task { await join(memberId: m.id) } }
                        }
                        Button("I'm not listed — add me") { Task { await join(memberId: nil) } }
                    } header: {
                        Text("Joining \(preview.householdName). Which one is you?")
                    } footer: {
                        ErrorBanner(message: error)
                    }
                } else {
                    Section {
                        TextField("Invite code", text: $code)
                            .textInputAutocapitalization(.characters)
                            .autocorrectionDisabled()
                        Button("Find household") { Task { await find() } }
                            .disabled(code.count < 4 || isBusy)
                    } footer: {
                        VStack(alignment: .leading) {
                            Text("Ask your house admin for the 8-character code.")
                            ErrorBanner(message: error)
                        }
                    }
                }
            }
            .disabled(isBusy)
            .navigationTitle("Join household")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
            }
        }
    }

    private func find() async {
        isBusy = true
        defer { isBusy = false }
        do {
            preview = try await APIClient.shared.previewInvite(code: code.trimmingCharacters(in: .whitespaces).uppercased())
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func join(memberId: UUID?) async {
        isBusy = true
        defer { isBusy = false }
        do {
            let house = try await APIClient.shared.acceptInvite(code: code.trimmingCharacters(in: .whitespaces).uppercased(), memberId: memberId)
            session.rememberHousehold(house.id)
            onJoined()
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
