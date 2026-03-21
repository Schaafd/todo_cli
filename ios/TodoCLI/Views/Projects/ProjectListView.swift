import SwiftUI

struct ProjectListView: View {
    @EnvironmentObject var apiClient: APIClient
    @EnvironmentObject var themeManager: ThemeManager
    @State private var projects: [Project] = []
    @State private var isLoading = false
    @State private var showCreateSheet = false
    @State private var newProjectName = ""
    @State private var newProjectDescription = ""
    @State private var newProjectColor = "#007AFF"
    @State private var errorMessage: String?

    private let colorPresets = [
        "#007AFF", "#5856D6", "#AF52DE", "#FF2D55",
        "#FF3B30", "#FF9500", "#34C759", "#00C7BE",
    ]

    var body: some View {
        NavigationStack {
            Group {
                if isLoading && projects.isEmpty {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if projects.isEmpty {
                    emptyState
                } else {
                    projectList
                }
            }
            .navigationTitle("Projects")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showCreateSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showCreateSheet) {
                createProjectSheet
            }
            .refreshable {
                await loadProjects()
            }
            .task {
                await loadProjects()
            }
        }
    }

    // MARK: - Project List

    private var projectList: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ForEach(projects) { project in
                    projectCard(project)
                }
            }
            .padding(.horizontal, themeManager.contentPadding)
            .padding(.top, 8)
            .padding(.bottom, 100)
        }
    }

    private func projectCard(_ project: Project) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                // Color dot
                Circle()
                    .fill(project.swiftUIColor)
                    .frame(width: 12, height: 12)

                Text(project.name)
                    .font(.headline)
                    .lineLimit(1)

                Spacer()

                Text("\(project.activeTasks) active")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.secondary)
            }

            if let desc = project.description, !desc.isEmpty {
                Text(desc)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            // Progress bar
            VStack(alignment: .leading, spacing: 4) {
                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 3)
                            .fill(Color(.systemGray5))
                            .frame(height: 6)

                        RoundedRectangle(cornerRadius: 3)
                            .fill(project.swiftUIColor)
                            .frame(width: max(0, geometry.size.width * project.progress), height: 6)
                    }
                }
                .frame(height: 6)

                HStack {
                    Text("\(project.completedCount)/\(project.taskCount) tasks")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                    Spacer()
                    Text("\(Int(project.progress * 100))%")
                        .font(.caption2.weight(.medium).monospacedDigit())
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .padding(themeManager.contentPadding)
        .background(
            RoundedRectangle(cornerRadius: themeManager.cardCornerRadius, style: .continuous)
                .fill(.regularMaterial)
                .shadow(color: .black.opacity(0.06), radius: 2, x: 0, y: 1)
        )
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack {
            Spacer()
            EmptyStateView(
                icon: "folder.badge.plus",
                title: "No projects",
                subtitle: "Create a project to organize your tasks"
            )
            Button {
                showCreateSheet = true
            } label: {
                Text("Create Project")
                    .font(.body.weight(.semibold))
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(
                        Capsule().fill(themeManager.accentColor)
                    )
                    .foregroundStyle(.white)
            }
            .padding(.top, 16)
            Spacer()
        }
    }

    // MARK: - Create Sheet

    private var createProjectSheet: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Project name", text: $newProjectName)
                        .font(.headline)

                    TextField("Description (optional)", text: $newProjectDescription, axis: .vertical)
                        .lineLimit(2...4)
                }

                Section("Color") {
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 4), spacing: 16) {
                        ForEach(colorPresets, id: \.self) { hex in
                            Button {
                                newProjectColor = hex
                            } label: {
                                ZStack {
                                    Circle()
                                        .fill(Color(hex: hex) ?? .blue)
                                        .frame(width: 40, height: 40)

                                    if newProjectColor == hex {
                                        Circle()
                                            .strokeBorder(.white, lineWidth: 3)
                                            .frame(width: 40, height: 40)
                                        Image(systemName: "checkmark")
                                            .font(.caption.weight(.bold))
                                            .foregroundStyle(.white)
                                    }
                                }
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.vertical, 8)
                }
            }
            .navigationTitle("New Project")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") {
                        showCreateSheet = false
                        resetForm()
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Create") {
                        Task { await createProject() }
                    }
                    .font(.body.weight(.semibold))
                    .disabled(newProjectName.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
    }

    // MARK: - Actions

    private func loadProjects() async {
        isLoading = true
        do {
            projects = try await apiClient.fetchProjects()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    private func createProject() async {
        let name = newProjectName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }

        let request = ProjectCreateRequest(
            name: name,
            description: newProjectDescription.isEmpty ? nil : newProjectDescription,
            color: newProjectColor
        )

        do {
            _ = try await apiClient.createProject(request)
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.success)
            showCreateSheet = false
            resetForm()
            await loadProjects()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func resetForm() {
        newProjectName = ""
        newProjectDescription = ""
        newProjectColor = "#007AFF"
    }
}

#Preview {
    ProjectListView()
        .environmentObject(APIClient())
        .environmentObject(ThemeManager())
}
