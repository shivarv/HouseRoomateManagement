import SwiftUI

struct ProfileView: View {
    @Environment(Session.self) private var session

    var body: some View {
        NavigationStack {
            List {
                if let user = session.user {
                    Section("Account") {
                        LabeledContent("Name", value: user.name)
                        LabeledContent("Email", value: user.email)
                    }
                }
                Section("Server") {
                    Text(APIClient.shared.baseURL)
                        .font(.footnote.monospaced())
                        .foregroundStyle(.secondary)
                }
                Section {
                    Button("Sign out", role: .destructive) { session.signOut() }
                }
            }
            .navigationTitle("Profile")
        }
    }
}
