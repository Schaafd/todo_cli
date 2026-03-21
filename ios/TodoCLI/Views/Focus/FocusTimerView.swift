import SwiftUI

struct FocusTimerView: View {
    @EnvironmentObject var apiClient: APIClient
    @EnvironmentObject var themeManager: ThemeManager

    @State private var isRunning = false
    @State private var isPaused = false
    @State private var timeRemaining = 1500 // 25 minutes
    @State private var totalTime = 1500
    @State private var currentSession = 0
    @State private var totalSessions = 4
    @State private var sessionType = "work" // work, break, long_break
    @State private var timer: Timer?
    @State private var errorMessage: String?

    private var progress: Double {
        guard totalTime > 0 else { return 0 }
        return 1.0 - (Double(timeRemaining) / Double(totalTime))
    }

    private var timerColor: Color {
        switch sessionType {
        case "break", "short_break": return .green
        case "long_break": return .teal
        default: return themeManager.accentColor
        }
    }

    private var sessionLabel: String {
        switch sessionType {
        case "break", "short_break": return "Short Break"
        case "long_break": return "Long Break"
        default: return "Focus Session"
        }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 40) {
                Spacer()

                // Session info
                VStack(spacing: 8) {
                    Text(sessionLabel)
                        .font(.title2.weight(.semibold))
                        .foregroundStyle(.primary)

                    Text("Session \(currentSession + 1) of \(totalSessions)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                // Circular timer
                ZStack {
                    // Background ring
                    Circle()
                        .stroke(Color(.systemGray5), lineWidth: 10)
                        .frame(width: 260, height: 260)

                    // Progress ring
                    Circle()
                        .trim(from: 0, to: progress)
                        .stroke(
                            timerColor,
                            style: StrokeStyle(lineWidth: 10, lineCap: .round)
                        )
                        .frame(width: 260, height: 260)
                        .rotationEffect(.degrees(-90))
                        .animation(.easeInOut(duration: 0.5), value: progress)

                    // Time display
                    VStack(spacing: 4) {
                        Text(Date.pomodoroFormatted(seconds: timeRemaining))
                            .font(.system(size: 56, weight: .light, design: .monospaced))
                            .foregroundStyle(.primary)
                            .contentTransition(.numericText())

                        if isRunning && !isPaused {
                            HStack(spacing: 4) {
                                Circle()
                                    .fill(timerColor)
                                    .frame(width: 8, height: 8)
                                Text("Running")
                                    .font(.caption.weight(.medium))
                                    .foregroundStyle(.secondary)
                            }
                        } else if isPaused {
                            Text("Paused")
                                .font(.caption.weight(.medium))
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                // Session dots
                HStack(spacing: 12) {
                    ForEach(0..<totalSessions, id: \.self) { session in
                        Circle()
                            .fill(session < currentSession ? timerColor : Color(.systemGray4))
                            .frame(width: 12, height: 12)
                            .overlay {
                                if session == currentSession && isRunning {
                                    Circle()
                                        .stroke(timerColor, lineWidth: 2)
                                        .frame(width: 18, height: 18)
                                }
                            }
                    }
                }

                // Controls
                HStack(spacing: 32) {
                    if isRunning {
                        // Stop button
                        controlButton(icon: "stop.fill", color: .red) {
                            Task { await stopTimer() }
                        }

                        // Pause/Resume button
                        controlButton(
                            icon: isPaused ? "play.fill" : "pause.fill",
                            color: timerColor,
                            isLarge: true
                        ) {
                            Task {
                                if isPaused {
                                    await resumeTimer()
                                } else {
                                    await pauseTimer()
                                }
                            }
                        }
                    } else {
                        // Start button
                        controlButton(icon: "play.fill", color: timerColor, isLarge: true) {
                            Task { await startTimer() }
                        }
                    }
                }

                Spacer()
            }
            .padding(.horizontal, themeManager.contentPadding)
            .navigationTitle("Focus")
            .navigationBarTitleDisplayMode(.large)
            .task {
                await fetchStatus()
            }
            .onDisappear {
                timer?.invalidate()
            }
        }
    }

    // MARK: - Control Button

    private func controlButton(icon: String, color: Color, isLarge: Bool = false, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(isLarge ? .title : .title3)
                .foregroundStyle(.white)
                .frame(width: isLarge ? 72 : 56, height: isLarge ? 72 : 56)
                .background(
                    Circle()
                        .fill(color)
                        .shadow(color: color.opacity(0.3), radius: 8, x: 0, y: 4)
                )
        }
    }

    // MARK: - Timer Actions

    private func startTimer() async {
        do {
            let status = try await apiClient.startPomodoro()
            applyStatus(status)
            startLocalTimer()
            let generator = UIImpactFeedbackGenerator(style: .medium)
            generator.impactOccurred()
        } catch {
            // Start locally if server fails
            isRunning = true
            isPaused = false
            timeRemaining = 1500
            totalTime = 1500
            sessionType = "work"
            startLocalTimer()
        }
    }

    private func stopTimer() async {
        timer?.invalidate()
        timer = nil

        do {
            let status = try await apiClient.stopPomodoro()
            applyStatus(status)
        } catch {
            isRunning = false
            isPaused = false
            timeRemaining = 1500
            totalTime = 1500
        }

        let generator = UIImpactFeedbackGenerator(style: .heavy)
        generator.impactOccurred()
    }

    private func pauseTimer() async {
        timer?.invalidate()
        timer = nil

        do {
            let status = try await apiClient.pausePomodoro()
            applyStatus(status)
        } catch {
            isPaused = true
        }
    }

    private func resumeTimer() async {
        do {
            let status = try await apiClient.resumePomodoro()
            applyStatus(status)
            startLocalTimer()
        } catch {
            isPaused = false
            startLocalTimer()
        }
    }

    private func fetchStatus() async {
        do {
            let status = try await apiClient.fetchPomodoroStatus()
            applyStatus(status)
            if status.isRunning && !status.isPaused {
                startLocalTimer()
            }
        } catch {
            // Use defaults
        }
    }

    private func applyStatus(_ status: PomodoroStatus) {
        isRunning = status.isRunning
        isPaused = status.isPaused
        timeRemaining = status.timeRemaining
        currentSession = status.currentSession
        totalSessions = status.totalSessions
        sessionType = status.sessionType

        // Determine total time based on session type
        switch sessionType {
        case "break", "short_break":
            totalTime = 300 // 5 minutes
        case "long_break":
            totalTime = 900 // 15 minutes
        default:
            totalTime = 1500 // 25 minutes
        }
    }

    private func startLocalTimer() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
            Task { @MainActor in
                if timeRemaining > 0 {
                    timeRemaining -= 1
                } else {
                    timer?.invalidate()
                    timer = nil
                    let generator = UINotificationFeedbackGenerator()
                    generator.notificationOccurred(.success)
                    await fetchStatus()
                }
            }
        }
    }
}

#Preview {
    FocusTimerView()
        .environmentObject(APIClient())
        .environmentObject(ThemeManager())
}
