import SwiftUI

// MARK: - Shimmer Effect Modifier

/// Shimmer effect modifier for skeleton loading animations.
/// Creates a sliding highlight that moves across the view to indicate loading.
struct ShimmerModifier: ViewModifier {
    @State private var phase: CGFloat = -300

    func body(content: Content) -> some View {
        content
            .overlay(
                LinearGradient(
                    colors: [.clear, .white.opacity(0.4), .clear],
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .frame(width: 200)
                .offset(x: phase)
                .animation(
                    .linear(duration: 1.5).repeatForever(autoreverses: false),
                    value: phase
                )
            )
            .clipped()
            .onAppear {
                phase = 300
            }
    }
}

extension View {
    /// Applies a shimmering animation overlay to indicate loading.
    func shimmer() -> some View {
        modifier(ShimmerModifier())
    }
}

// MARK: - Skeleton Shape Helpers

/// A rounded placeholder rectangle used in skeleton views.
struct SkeletonRect: View {
    var width: CGFloat? = nil
    var height: CGFloat = 16
    var opacity: Double = 0.2

    var body: some View {
        RoundedRectangle(cornerRadius: 4)
            .fill(Color.gray.opacity(opacity))
            .frame(height: height)
            .frame(maxWidth: width ?? .infinity)
    }
}

/// A circular placeholder used in skeleton views.
struct SkeletonCircle: View {
    var size: CGFloat = 24
    var opacity: Double = 0.2

    var body: some View {
        Circle()
            .fill(Color.gray.opacity(opacity))
            .frame(width: size, height: size)
    }
}

// MARK: - Task Row Skeleton

/// Skeleton placeholder that mimics the layout of a TaskRowView.
struct TaskRowSkeleton: View {
    var body: some View {
        HStack(spacing: 12) {
            // Priority bar placeholder
            RoundedRectangle(cornerRadius: 2)
                .fill(Color.gray.opacity(0.15))
                .frame(width: 4)
                .frame(maxHeight: .infinity)
                .padding(.vertical, 4)

            // Checkbox placeholder
            SkeletonCircle(size: 24)

            VStack(alignment: .leading, spacing: 8) {
                // Title placeholder
                SkeletonRect(height: 16)

                HStack(spacing: 8) {
                    // Date placeholder
                    SkeletonRect(width: 80, height: 12, opacity: 0.15)

                    // Project placeholder
                    SkeletonRect(width: 60, height: 12, opacity: 0.15)
                }
            }

            Spacer(minLength: 4)

            // Priority badge placeholder
            SkeletonRect(width: 32, height: 20, opacity: 0.12)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 14)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(.regularMaterial)
        )
        .shimmer()
    }
}

// MARK: - Home Dashboard Skeleton

/// Skeleton placeholder that mimics the layout of the HomeView dashboard,
/// including the stats card and task list sections.
struct HomeDashboardSkeleton: View {
    var body: some View {
        VStack(spacing: 16) {
            // Quick add bar placeholder
            HStack {
                SkeletonRect(height: 44, opacity: 0.12)
            }
            .shimmer()

            // Section header placeholder
            sectionHeaderSkeleton

            // Task rows skeleton
            ForEach(0..<4, id: \.self) { _ in
                TaskRowSkeleton()
            }

            // Stats card skeleton
            statsCardSkeleton
        }
        .padding(.horizontal, 16)
    }

    private var sectionHeaderSkeleton: some View {
        HStack(spacing: 8) {
            SkeletonCircle(size: 16, opacity: 0.15)
            SkeletonRect(width: 80, height: 14, opacity: 0.18)
            SkeletonRect(width: 28, height: 18, opacity: 0.1)
            Spacer()
            SkeletonCircle(size: 12, opacity: 0.1)
        }
        .shimmer()
    }

    private var statsCardSkeleton: some View {
        VStack(spacing: 12) {
            // Header
            HStack(spacing: 8) {
                SkeletonCircle(size: 16, opacity: 0.15)
                SkeletonRect(width: 80, height: 14, opacity: 0.18)
                Spacer()
            }

            // Stat pills
            HStack(spacing: 16) {
                ForEach(0..<4, id: \.self) { _ in
                    VStack(spacing: 4) {
                        SkeletonRect(width: 40, height: 22, opacity: 0.15)
                        SkeletonRect(width: 36, height: 10, opacity: 0.1)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(.regularMaterial)
                .shadow(color: .black.opacity(0.06), radius: 2, x: 0, y: 1)
        )
        .shimmer()
    }
}

// MARK: - Project Skeleton

/// Skeleton placeholder that mimics the layout of a project card in ProjectListView.
struct ProjectSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                // Color dot
                SkeletonCircle(size: 12, opacity: 0.2)

                // Project name
                SkeletonRect(width: 140, height: 16, opacity: 0.2)

                Spacer()

                // Active count
                SkeletonRect(width: 60, height: 12, opacity: 0.15)
            }

            // Description
            SkeletonRect(height: 12, opacity: 0.12)

            // Progress bar
            VStack(alignment: .leading, spacing: 4) {
                RoundedRectangle(cornerRadius: 3)
                    .fill(Color.gray.opacity(0.12))
                    .frame(height: 6)

                HStack {
                    SkeletonRect(width: 80, height: 10, opacity: 0.1)
                    Spacer()
                    SkeletonRect(width: 30, height: 10, opacity: 0.1)
                }
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(.regularMaterial)
                .shadow(color: .black.opacity(0.06), radius: 2, x: 0, y: 1)
        )
        .shimmer()
    }
}

/// A list of project skeleton cards for loading states.
struct ProjectListSkeleton: View {
    var count: Int = 4

    var body: some View {
        VStack(spacing: 12) {
            ForEach(0..<count, id: \.self) { _ in
                ProjectSkeleton()
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
    }
}

// MARK: - Previews

#Preview("Task Row Skeleton") {
    VStack(spacing: 4) {
        TaskRowSkeleton()
        TaskRowSkeleton()
        TaskRowSkeleton()
    }
    .padding()
}

#Preview("Home Dashboard Skeleton") {
    ScrollView {
        HomeDashboardSkeleton()
    }
}

#Preview("Project Skeleton") {
    ScrollView {
        ProjectListSkeleton()
    }
}
