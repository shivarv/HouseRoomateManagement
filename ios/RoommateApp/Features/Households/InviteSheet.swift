import SwiftUI
import UIKit

/// Invite roommates: their email gets a private invite (they log in or sign up from it and join), or
/// share the house link. Admins can make a new link, which stops the old one. Pending invites are
/// listed with the people (People). Mirrors web InvitePanel.tsx.
struct InviteSheet: View {
    let house: HouseholdDetail
    @Environment(\.dismiss) private var dismiss
    @State private var emails = ""
    @State private var results: EmailInviteResults?
    @State private var error: String?
    @State private var busy = false
    @State private var copied = false
    @State private var inviteCode: String
    @State private var confirmReset = false
    @State private var resetNote: String?

    init(house: HouseholdDetail) {
        self.house = house
        _inviteCode = State(initialValue: house.inviteCode)
    }

    private var message: String { InviteLink.message(house: house.name, code: inviteCode) }
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
                    TextField("bea@example.com, cy@example.com", text: $emails)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button(busy ? "Inviting…" : (parsed.count > 1 ? "Invite \(parsed.count)" : "Invite")) {
                        Task { await invite() }
                    }
                    .bold()
                    .disabled(parsed.isEmpty || !invalid.isEmpty || busy)
                    if let results {
                        ForEach(results.results, id: \.email) { r in resultLine(r) }
                        let unsent = results.results.filter { $0.status == "saved" || $0.status == "failed" }.map(\.email)
                        if !unsent.isEmpty, let url = emailURL(to: unsent, message) {
                            Link("Send it from Mail instead", destination: url).font(.footnote)
                        }
                    }
                } header: {
                    Text("Their email")
                } footer: {
                    if !invalid.isEmpty {
                        Text("Check \(invalid.joined(separator: ", ")): that isn't an email address.").foregroundStyle(.red)
                    } else {
                        Text("They get an invite, log in or sign up from it, and join \(house.name) — at the end of every chore rotation.")
                    }
                }

                Section {
                    ShareLink(item: message) { Label("Share invite…", systemImage: "square.and.arrow.up") }
                    if let url = whatsappURL(message) {
                        Link(destination: url) { Label("WhatsApp", systemImage: "message.fill") }
                    }
                    Button {
                        UIPasteboard.general.string = InviteLink.url(code: inviteCode)
                        copied = true
                    } label: {
                        Label(copied ? "Copied" : "Copy link", systemImage: copied ? "checkmark" : "link")
                    }
                    if house.myRole == .admin {
                        Button("Make a new link (stops the old one)", systemImage: "arrow.clockwise") { confirmReset = true }
                    }
                } header: {
                    Text("Or share the link")
                } footer: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Anyone with the link can join. The code \(inviteCode) works too.")
                        if let resetNote { Text(resetNote).foregroundStyle(.green) }
                    }
                }

                if let error { Section { ErrorBanner(message: error) } }
            }
            .navigationTitle("Invite roommates")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .confirmationDialog("Make a new link?", isPresented: $confirmReset, titleVisibility: .visible) {
                Button("Make a new link", role: .destructive) { Task { await resetLink() } }
            } message: {
                Text("The current link and code stop working right away. Share the new one with anyone who still needs it.")
            }
        }
    }

    /// One address's outcome, in words the sender can act on. Mirrors web InviteResultLine.
    @ViewBuilder
    private func resultLine(_ r: EmailInviteResult) -> some View {
        switch r.status {
        case "sent":
            Text("✓ Invite emailed to \(r.email)").font(.footnote).foregroundStyle(.green)
        case "member":
            Text("\(r.email) is already in the house.").font(.footnote).foregroundStyle(.secondary)
        default:
            VStack(alignment: .leading, spacing: 2) {
                Text("Couldn't email \(r.email).").font(.footnote.bold())
                Text(failureReason(r)).font(.footnote)
            }
            .foregroundStyle(.orange)
        }
    }

    private func failureReason(_ r: EmailInviteResult) -> String {
        if r.status == "saved" { return "Sending email isn't set up on this server yet." }
        switch r.reason {
        case "bad_address": return "That address doesn't look right — check for typos and invite again."
        case "unavailable": return "Our email service isn't responding right now. Try Invite again in a few minutes."
        default: return "Our email service didn't accept it. Try again later; if it keeps happening, the app's email setup needs a look."
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

    private func invite() async {
        busy = true
        defer { busy = false }
        do {
            results = try await APIClient.shared.emailInvites(householdId: house.id, emails: parsed)
            emails = ""
            error = nil
        } catch let e as APIError where e.status == 0 || e.status >= 500 {
            error = "We couldn't reach the server, so nothing was sent. Check your connection and try again in a minute."
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func resetLink() async {
        do {
            inviteCode = try await APIClient.shared.resetInviteCode(householdId: house.id).inviteCode
            copied = false
            resetNote = "✓ New link made — old links no longer work."
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
