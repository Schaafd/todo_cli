import SwiftUI

struct ThemePickerView: View {
    @EnvironmentObject var themeManager: ThemeManager

    var body: some View {
        Form {
            // Accent Color
            Section {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 5), spacing: 20) {
                    ForEach(ThemeManager.presetColors, id: \.name) { preset in
                        Button {
                            withAnimation(.easeInOut(duration: 0.25)) {
                                themeManager.accentColor = preset.color
                            }
                            let generator = UISelectionFeedbackGenerator()
                            generator.selectionChanged()
                        } label: {
                            VStack(spacing: 6) {
                                ZStack {
                                    Circle()
                                        .fill(preset.color)
                                        .frame(width: 44, height: 44)
                                        .shadow(color: preset.color.opacity(0.3), radius: 4, x: 0, y: 2)

                                    if colorsMatch(themeManager.accentColor, preset.color) {
                                        Circle()
                                            .strokeBorder(.white, lineWidth: 3)
                                            .frame(width: 44, height: 44)
                                        Image(systemName: "checkmark")
                                            .font(.caption.weight(.bold))
                                            .foregroundStyle(.white)
                                    }
                                }

                                Text(preset.name)
                                    .font(.caption2)
                                    .foregroundStyle(
                                        colorsMatch(themeManager.accentColor, preset.color)
                                            ? .primary
                                            : .secondary
                                    )
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.vertical, 12)
            } header: {
                Text("Accent Color")
            } footer: {
                Text("Choose the primary color used throughout the app.")
            }

            // Appearance Mode
            Section {
                ForEach(ThemeManager.Appearance.allCases, id: \.self) { mode in
                    Button {
                        withAnimation(.easeInOut(duration: 0.25)) {
                            themeManager.appearance = mode
                        }
                    } label: {
                        HStack(spacing: 12) {
                            Image(systemName: mode.icon)
                                .font(.title3)
                                .foregroundStyle(themeManager.appearance == mode ? themeManager.accentColor : .secondary)
                                .frame(width: 28)

                            Text(mode.displayName)
                                .foregroundStyle(.primary)

                            Spacer()

                            if themeManager.appearance == mode {
                                Image(systemName: "checkmark")
                                    .font(.body.weight(.semibold))
                                    .foregroundStyle(themeManager.accentColor)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                    .buttonStyle(.plain)
                }
            } header: {
                Text("Appearance")
            } footer: {
                Text("System follows your device's appearance setting.")
            }

            // List Density
            Section {
                ForEach(ThemeManager.ListDensity.allCases, id: \.self) { density in
                    Button {
                        withAnimation(.easeInOut(duration: 0.25)) {
                            themeManager.listDensity = density
                        }
                    } label: {
                        HStack(spacing: 12) {
                            Image(systemName: density == .compact ? "rectangle.compress.vertical" : "rectangle.expand.vertical")
                                .font(.title3)
                                .foregroundStyle(themeManager.listDensity == density ? themeManager.accentColor : .secondary)
                                .frame(width: 28)

                            VStack(alignment: .leading) {
                                Text(density.displayName)
                                    .foregroundStyle(.primary)
                                Text(density == .compact ? "Show more tasks at once" : "More space between items")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }

                            Spacer()

                            if themeManager.listDensity == density {
                                Image(systemName: "checkmark")
                                    .font(.body.weight(.semibold))
                                    .foregroundStyle(themeManager.accentColor)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                    .buttonStyle(.plain)
                }
            } header: {
                Text("List Density")
            }

            // Preview
            Section("Preview") {
                previewCard
            }
        }
        .navigationTitle("Theme")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Preview Card

    private var previewCard: some View {
        VStack(spacing: 8) {
            HStack(spacing: 12) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.priorityHigh)
                    .frame(width: 4, height: 40)

                ZStack {
                    Circle()
                        .strokeBorder(Color(.systemGray3), lineWidth: 2)
                        .frame(width: 22, height: 22)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text("Sample Task")
                        .font(.body.weight(.medium))
                    HStack(spacing: 6) {
                        Text("Today")
                            .font(.caption)
                            .foregroundStyle(.statusDueToday)
                        TagChip(text: "sample")
                    }
                }

                Spacer()

                PriorityBadge(priority: .high)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, themeManager.listDensity.verticalPadding)
            .background(
                RoundedRectangle(cornerRadius: themeManager.cardCornerRadius, style: .continuous)
                    .fill(.regularMaterial)
            )

            HStack(spacing: 12) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.priorityLow)
                    .frame(width: 4, height: 40)

                ZStack {
                    Circle()
                        .fill(Color.statusCompleted)
                        .frame(width: 18, height: 18)
                    Circle()
                        .strokeBorder(Color.statusCompleted, lineWidth: 2)
                        .frame(width: 22, height: 22)
                    Image(systemName: "checkmark")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(.white)
                }

                Text("Completed Task")
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .strikethrough(true, color: .secondary)

                Spacer()
            }
            .padding(.horizontal, 12)
            .padding(.vertical, themeManager.listDensity.verticalPadding)
            .background(
                RoundedRectangle(cornerRadius: themeManager.cardCornerRadius, style: .continuous)
                    .fill(.regularMaterial)
            )
            .opacity(0.7)
        }
        .padding(.vertical, 4)
    }

    private func colorsMatch(_ a: Color, _ b: Color) -> Bool {
        let aHex = a.toHex() ?? ""
        let bHex = b.toHex() ?? ""
        return aHex == bHex
    }
}

#Preview {
    NavigationStack {
        ThemePickerView()
    }
    .environmentObject(ThemeManager())
}
