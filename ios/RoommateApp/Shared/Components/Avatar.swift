import SwiftUI

/// A person's initial in a coloured circle: a mix of colours, all the same depth so none jumps out,
/// and the same colour for the same name everywhere (chat, People, the profile button) — on web too.
/// Mirrors web lib/avatar.ts: same palette, same hash.
struct Avatar: View {
    let name: String
    var size: CGFloat = 32

    var body: some View {
        Text(name.first.map { String($0).uppercased() } ?? "?")
            .font(.system(size: size * 0.4, weight: .bold))
            .foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(Avatar.gradient(for: name), in: Circle())
            .shadow(color: .black.opacity(0.1), radius: 1, y: 1)
    }

    // Tailwind's indigo, violet, purple, pink, fuchsia, sky, blue, emerald, teal, amber and orange.
    private static let palette: [[UInt32]] = [
        [0x6366f1, 0x4f46e5],  // indigo
        [0x8b5cf6, 0x9333ea],  // violet into purple
        [0xf472b6, 0xd946ef, 0x9333ea],  // pink easing into purple
        [0x0284c7, 0x2563eb, 0x4f46e5],  // a deeper blue easing into indigo
        [0x10b981, 0x0d9488],  // emerald into teal
        [0xf59e0b, 0xea580c],  // amber into orange
    ]

    static func gradient(for name: String) -> LinearGradient {
        // Same as the web: hash = hash * 31 + UTF-16 code unit, kept to 32 bits.
        var hash: Int32 = 0
        for unit in name.utf16 { hash = hash &* 31 &+ Int32(unit) }
        let stops = palette[Int(Int64(hash).magnitude % UInt64(palette.count))]
        return LinearGradient(colors: stops.map(color), startPoint: .topLeading, endPoint: .bottomTrailing)
    }

    private static func color(_ hex: UInt32) -> Color {
        Color(red: Double((hex >> 16) & 0xff) / 255, green: Double((hex >> 8) & 0xff) / 255, blue: Double(hex & 0xff) / 255)
    }
}
