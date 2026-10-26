import SwiftUI

/// Tabs as pills, matching web lib/tabStyles.ts: the chosen one is the indigo→pink gradient with a
/// soft glow; the others sit on white cards in a light tray. Pressing dips them a little, and on
/// iPad with a pointer they lift on hover.
struct ChipTabs<Item: Hashable & Identifiable & RawRepresentable>: View where Item.RawValue == String {
    let items: [Item]
    @Binding var selection: Item
    /// A small count or tick beside a tab's name, like an unread badge.
    var badge: (Item) -> ChipBadge? = { _ in nil }

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 4) {
                ForEach(items) { item in
                    Button {
                        withAnimation(.snappy(duration: 0.2)) { selection = item }
                    } label: {
                        HStack(spacing: 5) {
                            Text(item.rawValue)
                            if let badge = badge(item) { badge }
                        }
                    }
                    .buttonStyle(ChipStyle(isActive: selection == item))
                }
            }
            .padding(4)
            .background(Color(.secondarySystemFill).opacity(0.6), in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Color.primary.opacity(0.06)))
            .padding(.vertical, 4)
        }
        .scrollClipDisabled()  // keep the active pill's glow from being cut off
    }
}

/// The badge on a chip tab: white text on a coloured pill, with a thin white ring so it reads on
/// the active tab's gradient too.
struct ChipBadge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption2.weight(.bold).monospacedDigit())
            .foregroundStyle(.white)
            .padding(.horizontal, 5)
            .frame(minWidth: 18, minHeight: 18)
            .background(color, in: Capsule())
            .overlay(Capsule().strokeBorder(.white.opacity(0.7), lineWidth: 1))
    }
}

struct ChipStyle: ButtonStyle {
    let isActive: Bool
    static let gradient = LinearGradient(colors: [Color(red: 0.39, green: 0.40, blue: 0.95), Color(red: 0.85, green: 0.27, blue: 0.94)],
                                         startPoint: .leading, endPoint: .trailing)

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(isActive ? .semibold : .medium))
            .padding(.horizontal, 14).padding(.vertical, 7)
            .foregroundStyle(isActive ? Color.white : Color.primary.opacity(0.75))
            .background {
                if isActive {
                    RoundedRectangle(cornerRadius: 12).fill(Self.gradient)
                        .shadow(color: Color.indigo.opacity(0.35), radius: 6, y: 3)
                } else if configuration.isPressed {
                    RoundedRectangle(cornerRadius: 12).fill(Color(.systemBackground))
                        .shadow(color: Color.indigo.opacity(0.12), radius: 4, y: 2)
                }
            }
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
            .animation(.snappy(duration: 0.15), value: configuration.isPressed)
            .contentShape(RoundedRectangle(cornerRadius: 12))
            .hoverEffect(.lift)
    }
}
