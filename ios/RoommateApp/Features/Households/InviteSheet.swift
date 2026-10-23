import SwiftUI
import UIKit

/// Invite people to a house: the link (share sheet, WhatsApp, email, copy), email invites the
/// server keeps as pending, and a personal link for each roommate added by name. Mirrors web
/// InvitePanel.tsx.
struct InviteSheet: View {
    let house: HouseholdDetail
    @Environment(\.dismiss) private var dismiss
    @State private var emails = ""
    @State private var pending: [EmailInvite] = []
    @State private var results: EmailInviteResults?
    @State private var error: String?
    @State private var busy = false
    @State private var copied = false

    private var message: String { InviteLink.message(house: house.name, code: house.inviteCode) }
    private var waiting: [Member] { house.members.filter { !$0.hasAccount } }
    private var parsed: [String] {
        var seen = Set<String>()
        return emails.split(whereSeparator: { $0 == "," || $0 == ";" || $0.isWhitespace })
            .map { $0.lowercased() }
            .filter { seen.insert($0).inserted }
    }
    private var invalid: [String] { parsed.filter { !$0.contains("@") || !$0.contains(".") } }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ShareLink(item: message) { Label("Share invite…", systemImage: "square.and.arrow.up") }
                    if let url = whatsappURL(message) {
                        Link(destination: url) { Label("WhatsApp", systemImage: "message.fill") }
                    }
                    if let url = emailURL(to: [], message) {
                        Link(destination: url) { Label("Email", systemImage: "envelope") }
                    }
                    Button {
                        UIPasteboard.general.string = InviteLink.url(code: house.inviteCode)
                        copied = true
                    } label: {
                        Label(copied ? "Copied" : "Copy link", systemImage: copied ? "checkmark" : "link")
                    }
                } header: {
                    Text("Invite people to \(house.name)")
                } footer: {
                    Text("They open the link, sign up (or log in) and join. The code \(house.inviteCode) works too.")
                }

                Section {
                    TextField("bea@example.com, cy@example.com", text: $emails)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button(busy ? "Inviting…" : (parsed.count > 1 ? "Invite \(parsed.count)" : "Invite")) {
                        Task { await invite() }
                    }
                    .disabled(parsed.isEmpty || !invalid.isEmpty || busy)
                    if let results {
                        ForEach(results.results, id: \.email) { r in
                            Text("\(r.status == "sent" ? "✓ Emailed" : r.status == "saved" ? "✓ Invited" : "Already in the house:") \(r.email)")
                                .font(.footnote)
                                .foregroundStyle(r.status == "member" ? .secondary : Color.green)
                        }
                        let unsent = results.results.filter { $0.status == "saved" }.map(\.email)
                        if !unsent.isEmpty, let url = emailURL(to: unsent, message) {
                            Link(destination: url) {
                                Text("Emailing from the app isn't set up yet — they'll see the invite when they sign up with that email. Tap to send it from Mail.")
                                    .font(.footnote)
                            }
                        }
                    }
                } header: {
                    Text("Invite by email")
                } footer: {
                    if !invalid.isEmpty { Text("Check \(invalid.joined(separator: ", ")): that isn't an email address.").foregroundStyle(.red) }
                }

                if !pending.isEmpty {
                    Section("Waiting to join") {
                        ForEach(pending) { p in
                            VStack(alignment: .leading) {
                                Text(p.email)
                                Text((p.lastSentAt == nil ? "invited" : "emailed") + (p.invitedBy.map { " by \($0.displayName)" } ?? ""))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            .swipeActions {
                                if p.canCancel {
                                    Button("Cancel", role: .destructive) { Task { await cancel(p) } }
                                }
                            }
                        }
                    }
                }

                if !waiting.isEmpty {
                    Section {
                        ForEach(waiting) { m in
                            ShareLink(item: InviteLink.message(house: house.name, code: house.inviteCode, member: m)) {
                                Label("Invite \(m.displayName)", systemImage: "person.crop.circle.badge.plus")
                            }
                        }
                    } header: {
                        Text("Haven't joined yet")
                    } footer: {
                        Text("A personal link matches them to their name when they join.")
                    }
                }

                if let error { Section { ErrorBanner(message: error) } }
            }
            .navigationTitle("Invite people")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .task { await loadPending() }
        }
    }

    private func whatsappURL(_ text: String) -> URL? {
        text.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed).flatMap { URL(string: "https://wa.me/?text=\($0)") }
    }

    private func emailURL(to: [String], _ text: String) -> URL? {
        var parts = URLComponents()
        parts.scheme = "mailto"
        parts.path = to.joined(separator: ",")
        parts.queryItems = [URLQueryItem(name: "subject", value: "Join \(house.name) on Roommates"), URLQueryItem(name: "body", value: text)]
        return parts.url
    }

    private func loadPending() async {
        pending = (try? await APIClient.shared.pendingInvites(householdId: house.id)) ?? []
    }

    private func invite() async {
        busy = true
        defer { busy = false }
        do {
            results = try await APIClient.shared.emailInvites(householdId: house.id, emails: parsed)
            emails = ""
            error = nil
            await loadPending()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func cancel(_ invite: EmailInvite) async {
        do {
            try await APIClient.shared.cancelInvite(invite.id)
            await loadPending()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
