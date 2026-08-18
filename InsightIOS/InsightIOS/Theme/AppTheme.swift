import SwiftUI

enum AppTheme {
    static let terracotta = Color(red: 0.776, green: 0.365, blue: 0.227)
    static let terracottaDark = Color(red: 0.663, green: 0.278, blue: 0.169)
    static let blush = Color(red: 0.992, green: 0.945, blue: 0.929)
    static let ink = Color(red: 0.12, green: 0.12, blue: 0.13)
    static let mutedInk = Color(red: 0.42, green: 0.38, blue: 0.36)
    static let sage = Color(red: 0.27, green: 0.47, blue: 0.37)
    static let canvas = Color(red: 0.965, green: 0.957, blue: 0.949)
    static let surface = Color(red: 1.0, green: 0.992, blue: 0.984)
    static let line = Color.black.opacity(0.07)
    static let cardBg = Color.white
    static let amberLight = Color(red: 1.0, green: 0.96, blue: 0.88)
}

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.headline).frame(maxWidth: .infinity).frame(height: 54)
            .foregroundStyle(.white).background(AppTheme.terracotta.opacity(configuration.isPressed ? 0.78 : 1), in: RoundedRectangle(cornerRadius: 13, style: .continuous))
            .scaleEffect(configuration.isPressed ? 0.98 : 1).animation(.snappy, value: configuration.isPressed)
    }
}

struct PageBackground: ViewModifier {
    func body(content: Content) -> some View {
        content
            .foregroundStyle(AppTheme.ink)
            .background(AppTheme.canvas.ignoresSafeArea())
    }
}

extension View {
    func pageBackground() -> some View { modifier(PageBackground()) }
    func surface() -> some View {
        padding(16).background(AppTheme.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(AppTheme.line))
    }
    func cardStyle() -> some View {
        padding(14).background(AppTheme.cardBg, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(AppTheme.line))
    }
}
