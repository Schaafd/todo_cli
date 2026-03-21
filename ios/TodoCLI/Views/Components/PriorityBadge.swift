import SwiftUI

struct PriorityBadge: View {
    let priority: TaskPriority
    var compact: Bool = true

    var body: some View {
        if compact {
            Text(priorityAbbreviation)
                .font(.caption2.weight(.bold))
                .foregroundStyle(Color.forPriority(priority))
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(
                    Capsule()
                        .fill(Color.forPriority(priority).opacity(0.12))
                )
        } else {
            HStack(spacing: 4) {
                Circle()
                    .fill(Color.forPriority(priority))
                    .frame(width: 8, height: 8)
                Text(priority.displayName)
                    .font(.caption.weight(.medium))
                    .foregroundStyle(Color.forPriority(priority))
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(
                Capsule()
                    .fill(Color.forPriority(priority).opacity(0.12))
            )
        }
    }

    private var priorityAbbreviation: String {
        switch priority {
        case .critical: return "!!!"
        case .high: return "!!"
        case .medium: return "!"
        case .low: return "-"
        }
    }
}

#Preview {
    VStack(spacing: 12) {
        ForEach(TaskPriority.allCases, id: \.self) { priority in
            HStack(spacing: 16) {
                PriorityBadge(priority: priority, compact: true)
                PriorityBadge(priority: priority, compact: false)
            }
        }
    }
    .padding()
}
