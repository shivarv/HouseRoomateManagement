import SwiftUI

/// The house look, matching web index.css and lib/tabStyles.ts: indigo → fuchsia gradients over a
/// soft colour wash, with white cards on top. Every screen takes its colours from here.
enum Brand {
    static let indigo = Color(red: 0.39, green: 0.40, blue: 0.95)  // indigo-500
    static let violet = Color(red: 0.49, green: 0.23, blue: 0.93)  // violet-600
    static let fuchsia = Color(red: 0.85, green: 0.27, blue: 0.94)  // fuchsia-500
    static let teal = Color(red: 0.08, green: 0.72, blue: 0.65)  // teal-500

    static let gradient = LinearGradient(colors: [indigo, fuchsia], startPoint: .leading, endPoint: .trailing)
    /// For text, like web's .text-gradient.
    static let textGradient = LinearGradient(colors: [Color(red: 0.31, green: 0.27, blue: 0.9), violet, Color(red: 0.75, green: 0.15, blue: 0.83)],
                                             startPoint: .leading, endPoint: .trailing)
    static let diagonal = LinearGradient(colors: [indigo, fuchsia], startPoint: .topLeading, endPoint: .bottomTrailing)
}

/// The soft wash behind every screen: indigo top left, fuchsia top right, teal at the bottom.
/// Quieter in dark mode so the cards still stand out.
struct BrandBackground: View {
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        let strength = scheme == .dark ? 0.22 : 0.55
        ZStack {
            Color(.systemGroupedBackground)
            GeometryReader { geo in
                let size = max(geo.size.width, geo.size.height)
                RadialGradient(colors: [Brand.indigo.opacity(strength), .clear], center: UnitPoint(x: 0.05, y: 0),
                               startRadius: 0, endRadius: size * 0.55)
                RadialGradient(colors: [Brand.fuchsia.opacity(strength * 0.7), .clear], center: UnitPoint(x: 0.95, y: 0.05),
                               startRadius: 0, endRadius: size * 0.45)
                RadialGradient(colors: [Brand.teal.opacity(strength * 0.55), .clear], center: UnitPoint(x: 0.5, y: 1),
                               startRadius: 0, endRadius: size * 0.5)
            }
        }
        .ignoresSafeArea()
    }
}

extension View {
    /// A List, Form or ScrollView on the colour wash instead of plain grey.
    func brandBackground() -> some View {
        scrollContentBackground(.hidden)
            .background { BrandBackground() }
    }
}

/// The main action on a screen: the gradient pill with a soft glow, dimmed when disabled.
struct BrandButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 15)
            .background(Brand.gradient, in: Capsule())
            .shadow(color: Brand.indigo.opacity(isEnabled ? 0.35 : 0), radius: 10, y: 5)
            .opacity(isEnabled ? 1 : 0.45)
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.snappy(duration: 0.15), value: configuration.isPressed)
    }
}

extension ButtonStyle where Self == BrandButtonStyle {
    static var brand: BrandButtonStyle { BrandButtonStyle() }
}

/// A section title with a small coloured icon tile, like Settings on iOS.
struct IconHeader: View {
    let title: String
    let systemImage: String
    var color: Color = Brand.indigo

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: systemImage)
                .font(.caption.weight(.bold))
                .foregroundStyle(.white)
                .frame(width: 22, height: 22)
                .background(color.gradient, in: RoundedRectangle(cornerRadius: 6))
            Text(title)
        }
        .textCase(nil)
        .font(.subheadline.weight(.semibold))
        .foregroundStyle(.primary)
    }
}

/// The app's mark: the house in a gradient tile, like the web header.
struct AppMark: View {
    var size: CGFloat = 40

    var body: some View {
        Text("🏠")
            .font(.system(size: size * 0.55))
            .frame(width: size, height: size)
            .background(Brand.diagonal, in: RoundedRectangle(cornerRadius: size * 0.3))
            .shadow(color: Brand.indigo.opacity(0.35), radius: size * 0.2, y: size * 0.1)
    }
}

/// The avatar button at the top right of every tab: opens the profile.
struct ProfileButton: View {
    @Environment(Session.self) private var session
    @State private var showing = false

    var body: some View {
        Button { showing = true } label: {
            Avatar(name: session.user?.name ?? "?", size: 30)
        }
        .accessibilityLabel("Profile")
        .sheet(isPresented: $showing) { ProfileView() }
    }
}

/// The gear beside the avatar: the current house's Settings.
struct SettingsButton: View {
    let householdId: UUID
    @State private var showing = false

    var body: some View {
        Button { showing = true } label: { Image(systemName: "gearshape") }
            .accessibilityLabel("Settings")
            .sheet(isPresented: $showing) {
                NavigationStack {
                    HouseSettingsLoader(householdId: householdId)
                        .toolbar {
                            ToolbarItem(placement: .confirmationAction) { Button("Done") { showing = false } }
                        }
                }
            }
    }
}

extension View {
    /// Puts the Settings gear (admins of the current house) and the profile avatar in this tab's
    /// top bar. The House tab has its own gear, which also closes the house's pages after it's deleted.
    func profileToolbar(settings: Bool = true) -> some View {
        modifier(ProfileToolbar(settings: settings))
    }
}

private struct ProfileToolbar: ViewModifier {
    let settings: Bool
    @Environment(Session.self) private var session
    @State private var households: [Household] = []

    /// The current house, when I'm its admin.
    private var adminHouse: UUID? {
        guard settings, let id = session.preferredHousehold(in: households),
              households.first(where: { $0.id == id })?.myRole == .admin else { return nil }
        return id
    }

    func body(content: Content) -> some View {
        content
            .toolbar {
                if let house = adminHouse {
                    ToolbarItem(placement: .topBarTrailing) { SettingsButton(householdId: house) }
                }
                ToolbarItem(placement: .topBarTrailing) { ProfileButton() }
            }
            // The current house can change on any tab; check which one I'm an admin of again.
            .task(id: session.user?.lastHouseholdId) {
                guard settings else { return }
                households = (try? await APIClient.shared.households()) ?? households
            }
    }
}
