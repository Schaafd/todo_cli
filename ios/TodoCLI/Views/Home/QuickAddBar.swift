import SwiftUI

struct QuickAddBar: View {
    @EnvironmentObject var themeManager: ThemeManager
    @Binding var text: String
    @FocusState private var isFocused: Bool
    @State private var isAnimating = false
    var onSubmit: () async -> Void

    var body: some View {
        HStack(spacing: 12) {
            // Text field
            HStack(spacing: 8) {
                Image(systemName: "plus.circle.fill")
                    .font(.title3)
                    .foregroundStyle(
                        text.isEmpty ? .tertiary : themeManager.accentColor
                    )
                    .scaleEffect(isAnimating ? 1.15 : 1.0)

                TextField("Quick add task...", text: $text)
                    .font(.body)
                    .focused($isFocused)
                    .submitLabel(.done)
                    .onSubmit {
                        Task {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                                isAnimating = true
                            }
                            await onSubmit()
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                                isAnimating = false
                            }
                        }
                    }

                if !text.isEmpty {
                    Button {
                        text = ""
                        isFocused = false
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.body)
                            .foregroundStyle(.tertiary)
                    }
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(.regularMaterial)
                    .shadow(
                        color: isFocused
                            ? themeManager.accentColor.opacity(0.15)
                            : .black.opacity(0.06),
                        radius: isFocused ? 6 : 2,
                        x: 0,
                        y: isFocused ? 2 : 1
                    )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(
                        isFocused ? themeManager.accentColor.opacity(0.5) : .clear,
                        lineWidth: 1.5
                    )
            )

            // Submit button
            if !text.isEmpty {
                Button {
                    Task {
                        let generator = UIImpactFeedbackGenerator(style: .light)
                        generator.impactOccurred()
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                            isAnimating = true
                        }
                        await onSubmit()
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                            isAnimating = false
                        }
                    }
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.title2)
                        .foregroundStyle(themeManager.accentColor)
                        .symbolEffect(.bounce, value: isAnimating)
                }
                .transition(.scale.combined(with: .opacity))
            }
        }
        .animation(.easeInOut(duration: 0.2), value: text.isEmpty)
        .animation(.easeInOut(duration: 0.2), value: isFocused)
    }
}

#Preview {
    VStack {
        QuickAddBar(text: .constant("")) { }
        QuickAddBar(text: .constant("Buy groceries")) { }
    }
    .padding()
    .environmentObject(ThemeManager())
}
