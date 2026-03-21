import SwiftUI

struct EmptyStateView: View {
    let icon: String
    let title: String
    let subtitle: String

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 40))
                .foregroundStyle(.quaternary)

            Text(title)
                .font(.headline)
                .foregroundStyle(.secondary)

            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
    }
}

#Preview {
    VStack(spacing: 32) {
        EmptyStateView(
            icon: "checklist",
            title: "No tasks",
            subtitle: "Create your first task to get started"
        )

        EmptyStateView(
            icon: "magnifyingglass",
            title: "No results",
            subtitle: "Try a different search term"
        )
    }
}
