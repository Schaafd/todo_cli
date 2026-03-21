# Todo CLI - iOS App

A native SwiftUI iOS app for Todo CLI, featuring a flat material design with a heavy focus on quick access, quick add, and personalization.

## Requirements

- **Xcode 15+** (Swift 5.9)
- **iOS 17.0+** deployment target
- A running Todo CLI backend server

## Getting Started

### 1. Open the Project

```bash
open ios/TodoCLI.xcodeproj
```

### 2. Configure the Backend URL

On first launch, go to **Settings** tab and enter your backend server URL:

- **Local development**: `http://localhost:8000`
- **Remote server**: `https://your-server.example.com`

Use the **Test Connection** button to verify connectivity.

### 3. Build and Run

Select your target device or simulator, then press `Cmd+R` to build and run.

## Features

### Quick Add
- **Quick Add Bar** at the top of the Home screen for instant task creation
- **Floating Action Button (FAB)** visible on Home, Tasks, and Projects screens
- Haptic feedback on task creation for a tactile, responsive feel
- Supports the same natural language syntax as the CLI

### Quick Access
- **Home screen** with collapsible sections: Today, Overdue, Active Tasks, and Stats
- **Tab bar** navigation: Home, Tasks, Projects, Focus, Settings
- **Swipe gestures** on tasks: swipe right to complete, swipe left to delete
- **Pull-to-refresh** on all list screens
- **Search and filter** with instant results on the Tasks screen
- **Filter chips** for status (All/Active/Completed/Overdue/Today) and priority

### Focus Timer (Pomodoro)
- Large circular timer with visual progress ring
- Start/Pause/Stop controls
- Session tracking with dot indicators
- Syncs with the backend `/api/pomodoro/*` endpoints
- Works offline with local timer fallback

### Personalization
- **10 accent color presets**: Blue, Indigo, Purple, Pink, Red, Orange, Teal, Green, Mint, Cyan
- **Appearance modes**: Light, Dark, System
- **List density**: Compact (more tasks visible) or Comfortable (more whitespace)
- **Home screen sections**: Toggle which sections appear (Today, Overdue, Pinned, Recent)
- **Live theme preview** in the Theme picker

## Architecture

```
TodoCLI/
├── App/           # App entry point and root navigation
├── Models/        # Data models (Task, Project, User, Pomodoro)
├── Services/      # API client, auth, and task service
├── Views/         # SwiftUI views organized by feature
│   ├── Home/      # Home dashboard and quick add
│   ├── Tasks/     # Task list, row, detail, and creation
│   ├── Projects/  # Project list and management
│   ├── Focus/     # Pomodoro timer
│   ├── Settings/  # Settings and theme picker
│   └── Components/ # Reusable UI components
├── Theme/         # Theme manager and color system
├── Extensions/    # Swift extensions (Date formatting)
└── Assets.xcassets/
```

### API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/tasks` | GET | Fetch all tasks |
| `/api/tasks` | POST | Create a task |
| `/api/tasks/{id}` | GET | Get task details |
| `/api/tasks/{id}` | PUT | Update a task |
| `/api/tasks/{id}` | DELETE | Delete a task |
| `/api/tasks/{id}/toggle` | POST | Toggle completion |
| `/api/projects` | GET | Fetch all projects |
| `/api/projects` | POST | Create a project |
| `/api/pomodoro/status` | GET | Get timer status |
| `/api/pomodoro/start` | POST | Start timer |
| `/api/pomodoro/stop` | POST | Stop timer |
| `/api/pomodoro/pause` | POST | Pause timer |
| `/api/pomodoro/resume` | POST | Resume timer |
| `/api/ai/status` | GET | Get AI assistant status |
| `/api/dashboards` | GET | Fetch dashboards |
| `/health` | GET | Health check |

## Design

The app follows a **flat material design** approach inspired by Material Design 3:

- Clean, minimalist surfaces with `.regularMaterial` backgrounds
- Subtle shadows (`radius: 2, opacity: 0.06-0.08`) for depth without clutter
- Generous `14-16pt` padding throughout
- SF Pro system font with clear typography hierarchy
- Priority color indicators (critical=red, high=orange, medium=yellow, low=green)
- Smooth spring animations on interactions
- Haptic feedback on task completion, creation, and deletion

## Screenshots

*Screenshots will be added after the first build.*

## License

Part of the Todo CLI project. See the root LICENSE file for details.
