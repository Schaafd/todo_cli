import SwiftUI

struct TagChip: View {
    let text: String
    var color: Color = .secondary

    var body: some View {
        Text("#\(text)")
            .font(.caption2.weight(.medium))
            .foregroundStyle(color)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(
                Capsule()
                    .fill(color.opacity(0.1))
            )
    }
}

#Preview {
    HStack(spacing: 8) {
        TagChip(text: "urgent", color: .red)
        TagChip(text: "work", color: .blue)
        TagChip(text: "design")
        TagChip(text: "personal", color: .purple)
    }
    .padding()
}
