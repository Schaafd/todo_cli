# iOS App Analysis Report

## Executive Summary

A thorough review of the TodoCLI iOS app (24 Swift files across 6 directories) identified **critical security vulnerabilities**, **code quality gaps**, and **accessibility deficiencies**. The most severe finding was JWT tokens stored in plaintext via `UserDefaults` -- readable by any process with file-system access to the app container or in unencrypted device backups. This and several other issues have been fixed directly in the source code.

**Key findings:**
- **3 critical security issues** (2 fixed, 1 recommendation)
- **5 code quality issues** (3 fixed, 2 recommendations)
- **8 accessibility gaps** (all fixed)
- **3 performance concerns** (recommendations provided)
- **Significant testing gaps** (no iOS unit/UI tests exist)

---

## Security Analysis

### Issues Found

#### 1. CRITICAL: JWT Tokens Stored in UserDefaults (FIXED)
- **File:** `ios/TodoCLI/Services/APIClient.swift`, lines 10-18 (original)
- **Severity:** Critical
- **Description:** The `token` property persisted authentication tokens using `UserDefaults.standard.set(token, forKey: "auth_token")`. UserDefaults stores data as a plaintext plist file on disk. This means:
  - Tokens are visible in unencrypted iTunes/Finder backups
  - Any other app exploiting a sandbox escape can read them
  - Forensic tools can trivially extract them from device images
- **Same issue for auth cookies** at line 208 (original): `UserDefaults.standard.string(forKey: "auth_cookie")`

#### 2. CRITICAL: No HTTPS Enforcement (FIXED)
- **File:** `ios/TodoCLI/Services/APIClient.swift`, line 23 (original)
- **Description:** The default `baseURL` was `http://localhost:8000` (HTTP). While localhost is acceptable for development, the `baseURL` setter accepted *any* URL including plain HTTP to remote servers. Authentication tokens sent over HTTP are transmitted in cleartext and subject to man-in-the-middle attacks.

#### 3. MEDIUM: Login Input Not Validated (FIXED)
- **File:** `ios/TodoCLI/Services/APIClient.swift`, `login()` method
- **Description:** The `login()` function sent credentials directly to the server without any client-side validation. Empty strings, excessively long strings, or malformed input was sent raw.

#### 4. MEDIUM: Login Did Not Store Token from Response (FIXED)
- **File:** `ios/TodoCLI/Services/APIClient.swift`, line 50-53 (original)
- **Description:** The login method decoded a `TokenResponse` but never stored `response.accessToken` to the `token` property. The token was silently discarded, meaning token-based auth could never work after login.

#### 5. LOW: No API Path Sanitization (FIXED)
- **File:** `ios/TodoCLI/Services/APIClient.swift`, `buildURL()` method
- **Description:** API paths were concatenated directly to the base URL without sanitizing for path traversal sequences (`..`).

#### 6. LOW: No Certificate Pinning
- **Status:** Not fixed (recommendation only)
- **Description:** The app uses default `URLSession` without certificate pinning. For a high-value API, consider pinning the server's TLS certificate to prevent MITM attacks even with a compromised CA.

### Fixes Applied

1. **Created `ios/TodoCLI/Services/KeychainManager.swift`** -- A complete Keychain wrapper that:
   - Uses `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` for secure, device-bound storage
   - Provides `save()`, `retrieve()`, `delete()`, and `deleteAll()` operations
   - Includes `migrateFromUserDefaultsIfNeeded()` for seamless one-time migration of existing tokens
   - Uses proper error handling with a custom `KeychainError` enum

2. **Updated `APIClient.swift`**:
   - Token storage now uses `KeychainManager.save()` / `KeychainManager.retrieve()` / `KeychainManager.delete()`
   - Auth cookie retrieval moved from `UserDefaults` to `KeychainManager`
   - Default base URL changed from `http://` to `https://`
   - `baseURL` setter now validates that the URL is HTTPS (or HTTP only for localhost/127.0.0.1)
   - `login()` now validates username (1-150 chars) and password (1-128 chars)
   - `login()` now stores `response.accessToken` in `self.token`
   - `logout()` now also clears the cookie from Keychain
   - `buildURL()` now strips `..` sequences and requires paths to start with `/`
   - `migrateFromUserDefaultsIfNeeded()` called at init to transparently migrate existing users

### Recommendations

- **Add certificate pinning** using `URLSessionDelegate` with `urlSession(_:didReceive:completionHandler:)` for production deployments.
- **Add App Transport Security (ATS) exceptions** only for localhost in `Info.plist`; ensure all production traffic is HTTPS-only.
- **Implement token refresh** -- the current code has no mechanism for refreshing expired JWTs.
- **Add biometric authentication** (Face ID / Touch ID) as an optional gate before accessing the token.

---

## Code Quality Analysis

### Issues Found

#### 1. Missing Error Display in Multiple Views (FIXED)
- **Files:** `HomeView.swift`, `TaskListView.swift`, `ProjectListView.swift`, `TaskCreateView.swift`
- **Description:** All these views had `@State private var errorMessage: String?` properties that were set on failure, but the error was never shown to the user. Errors were silently swallowed.

#### 2. Login Token Not Stored (FIXED)
- **File:** `APIClient.swift`, `login()` method
- **Description:** The `login()` method decoded `TokenResponse` but returned `true` without saving `response.accessToken` to `self.token`. This bug meant JWT-based authentication was non-functional.

#### 3. FocusTimerView Uses Timer on Non-Main Thread
- **File:** `ios/TodoCLI/Views/Focus/FocusTimerView.swift`, line 266
- **Description:** `Timer.scheduledTimer` captures `self` implicitly in the closure. While `@MainActor` annotation on the enclosing view handles thread safety, the timer callback wraps work in `Task { @MainActor in ... }`, which is correct. However, the timer itself is created on the RunLoop that may not be the main RunLoop if called from an async context.

#### 4. TaskService Duplicates Logic from Views
- **File:** `ios/TodoCLI/Services/TaskService.swift`
- **Description:** `TaskService` exists but is not used by any view. Views (`HomeView`, `TaskListView`) each independently implement `loadTasks()`, `toggleTask()`, and `deleteTask()` with duplicated sorting and categorization logic. This leads to inconsistent behavior if one implementation is updated but not the others.

#### 5. ThemeManager Not Marked @MainActor
- **File:** `ios/TodoCLI/Theme/AppTheme.swift`
- **Description:** `ThemeManager` is an `ObservableObject` used by views but lacks `@MainActor` annotation. While `@AppStorage` is thread-safe, `objectWillChange.send()` should only be called from the main thread.

### Fixes Applied

1. **Added error display UI** to `HomeView` (toast overlay), `TaskListView` (alert), `ProjectListView` (alert), and `TaskCreateView` (alert + `errorMessage` state).
2. **Fixed token storage** in `login()` to actually save `response.accessToken`.
3. **Added `errorMessage` state** to `TaskCreateView` which was missing it.

### Recommendations

- **Consolidate task operations** by having views use `TaskService` instead of duplicating fetch/toggle/delete logic in `HomeView`, `TaskListView`, etc.
- **Add `@MainActor`** to `ThemeManager` class.
- **Use `TimelineView`** or `withTaskCancellationHandler` for the pomodoro timer instead of `Timer.scheduledTimer` for better async/await integration.
- **Replace `Timer.scheduledTimer` closure** in `FocusTimerView.startLocalTimer()` with a structured concurrency approach using `Task.sleep`.

---

## Testing Gap Analysis

### Current Coverage

The iOS app has **zero unit tests and zero UI tests**. There is no `TodoCLITests` or `TodoCLIUITests` target. All 900 passing tests are for the Python backend.

### Missing Tests

| Component | Test Type | Priority |
|-----------|-----------|----------|
| `KeychainManager` | Unit | **Critical** -- must verify save/retrieve/delete/migration |
| `APIClient` URL building | Unit | High -- verify HTTPS enforcement, path sanitization |
| `APIClient` HTTP methods | Unit (with mocked URLSession) | High |
| `TodoTask` Codable | Unit | High -- test flexible `id` decoding (Int vs String) |
| `Date+Extensions` | Unit | Medium -- test `relativeDescription`, `isOverdue`, etc. |
| `TaskService` sort/categorize | Unit | Medium |
| `AuthService` login/logout flow | Integration | Medium |
| `HomeView` / `TaskListView` | UI/Snapshot | Low |
| `FocusTimerView` timer behavior | UI | Low |

### Recommended Test Plan

1. **Create `TodoCLITests` target** in Xcode project.
2. **Unit tests for `KeychainManager`**: Verify round-trip save/retrieve, deletion, migration from UserDefaults.
3. **Unit tests for `APIClient`**: Use `URLProtocol` subclass to mock network responses. Test:
   - Successful JSON decoding
   - HTTP error code handling (401 clears token, 404, 422, 500)
   - Offline error detection
   - URL construction with query parameters
   - HTTPS enforcement in `baseURL` setter
4. **Unit tests for models**: Test `TodoTask(from: Decoder)` with integer IDs, missing fields, various date formats.
5. **UI tests**: Create `TodoCLIUITests` target for critical user flows (create task, toggle, delete, timer start/stop).

---

## UX/Accessibility Analysis

### Issues Found

#### 1. No Accessibility Labels on Interactive Elements (FIXED)
- **Files:** `TaskRowView.swift`, `FocusTimerView.swift`, `QuickAddBar.swift`, `ProjectListView.swift`
- **Description:** Most interactive elements (toggle buttons, timer controls, submit buttons) lacked `accessibilityLabel` and `accessibilityHint` modifiers. VoiceOver users would hear unhelpful descriptions like "button" or raw SF Symbol names.

#### 2. Timer Display Not Accessible (FIXED)
- **File:** `FocusTimerView.swift`
- **Description:** The timer showed `"25:00"` visually but VoiceOver would read individual text components. No combined accessibility element existed to convey "25 minutes remaining, running".

#### 3. Task Row Not Grouped for VoiceOver (FIXED)
- **File:** `TaskRowView.swift`
- **Description:** Each task row had many child views (priority bar, checkbox, title, date, tags, badge). VoiceOver would focus on each individually, requiring many swipes per task. Now combined into a single accessible element.

#### 4. Empty States Not Accessible (FIXED)
- **File:** `EmptyStateView.swift`
- **Description:** Icon, title, and subtitle were separate accessibility elements. Combined into one.

#### 5. Stats Not Accessible (FIXED)
- **File:** `HomeView.swift`, `statPill` function
- **Description:** The stats pills showed a value and label as separate text elements. VoiceOver would read them as disconnected "3" ... "Active".

#### 6. Project Cards Not Accessible (FIXED)
- **File:** `ProjectListView.swift`, `projectCard` function
- **Description:** Project cards had no combined accessibility label. Added descriptive label with name, active tasks, and progress.

#### 7. Component Badges Not Accessible (FIXED)
- **Files:** `PriorityBadge.swift`, `TagChip.swift`
- **Description:** Priority badges showed symbols like "!!!" and tags showed "#text" without accessibility labels explaining what they mean.

### Fixes Applied

1. **`TaskRowView.swift`**: Added `.accessibilityElement(children: .combine)`, `.accessibilityLabel` (computed property with task text, priority, status, due date, project, tags), and `.accessibilityHint`.
2. **`FocusTimerView.swift`**: Added `.accessibilityElement(children: .combine)` to the timer display, a `timerAccessibilityLabel` computed property ("X minutes and Y seconds remaining, running"), and labels/hints on all control buttons (Start, Stop, Pause, Resume).
3. **`QuickAddBar.swift`**: Added `.accessibilityLabel("Clear text")` to the clear button and `.accessibilityLabel("Submit task")` with hint to the submit button.
4. **`EmptyStateView.swift`**: Added `.accessibilityElement(children: .combine)` and label.
5. **`HomeView.swift`**: Added `.accessibilityElement(children: .combine)` and `.accessibilityLabel` to stat pills.
6. **`ProjectListView.swift`**: Added `.accessibilityElement(children: .combine)` and descriptive label to project cards.
7. **`PriorityBadge.swift`**: Added `.accessibilityLabel` to both compact and expanded variants.
8. **`TagChip.swift`**: Added `.accessibilityLabel("Tag: \(text)")`.
9. **`ContentView.swift`**: Added `.accessibilityHint` to the FAB button.

### Recommendations

- **Dynamic Type**: The app uses `.font(.system(size: 56))` for the timer display (line 75 of `FocusTimerView.swift`), which does not scale with Dynamic Type. Replace with a scalable font or add `.dynamicTypeSize(.xxxLarge)` capping.
- **Color contrast**: Priority colors like `.priorityMedium` (yellow) may not meet WCAG contrast ratios against light backgrounds. Consider darker variants for text.
- **Reduce Motion**: Timer animations and spring animations should respect `UIAccessibility.isReduceMotionEnabled`.
- **VoiceOver announcements**: When tasks are created/deleted/toggled, post `UIAccessibility.Notification.announcement` so VoiceOver users get feedback.
- **Keyboard navigation**: Ensure all actions are reachable via external keyboard on iPad.

---

## Performance Analysis

### Issues Found

#### 1. Full Task List Re-fetch After Every Mutation
- **Files:** `HomeView.swift` (line 211, 241), `TaskListView.swift` (line 207), `TaskService.swift` (line 55, 70, 98)
- **Description:** Every `toggleTask()`, `deleteTask()`, and `createTask()` call does a full `await loadTasks()` which re-fetches the entire task list from the server. For a list of 100+ tasks, this creates unnecessary network traffic and causes the entire list to re-render.

#### 2. DateFormatter Created Per-Call
- **File:** `ios/TodoCLI/Extensions/Date+Extensions.swift`, lines 44-46, 54-58, 62-65
- **Description:** New `DateFormatter` instances are created inside computed properties (`relativeDescription`, `shortFormatted`, `timeFormatted`). `DateFormatter` is expensive to create. These should be `static let` cached instances.

#### 3. Sorting on Every Filter Change
- **File:** `ios/TodoCLI/Views/Tasks/TaskListView.swift`, `filteredTasks` computed property
- **Description:** `filteredTasks` is a computed property that re-filters and potentially re-evaluates on every view body evaluation. For large task lists with complex filter logic, this could cause frame drops during scrolling.

### Recommendations

1. **Optimistic updates**: After `toggleTask()`, update the local `tasks` array immediately instead of re-fetching. Keep the server call for persistence, and only re-fetch on failure (rollback).
2. **Cache `DateFormatter` instances** as static properties:
   ```swift
   private static let dayOfWeekFormatter: DateFormatter = {
       let f = DateFormatter()
       f.dateFormat = "EEEE"
       return f
   }()
   ```
3. **Move filtering to a `@State`-backed property** that only recomputes when `tasks`, `selectedFilter`, `selectedPriority`, or `searchText` change, rather than on every body evaluation.
4. **Add pagination** to `fetchTasks()` for users with large task lists (100+ items).
5. **Use `List` with `id:`** instead of `ScrollView` + `LazyVStack` for very long lists, as `List` provides cell reuse.

---

## Architecture Review

### Strengths

1. **Clean separation of concerns**: Models, Services, Views, Theme, and Extensions are well-organized into separate directories.
2. **Consistent use of `@MainActor`** on service classes (`APIClient`, `AuthService`, `TaskService`) for thread safety.
3. **Comprehensive error enum** (`APIError`) with descriptive `localizedDescription` for every error case.
4. **Good use of SwiftUI patterns**: `@EnvironmentObject` for dependency injection, `@State` for local state, proper `NavigationStack` usage.
5. **Flexible JSON decoding**: `TodoTask` handles both `Int` and `String` IDs from the backend, with graceful fallbacks for missing fields.
6. **Theme system**: `ThemeManager` with `@AppStorage` provides persistent, customizable theming with live preview.
7. **Custom `FlowLayout`**: Well-implemented Layout protocol conformance for tag chips.

### Weaknesses

1. **No dependency injection for testing**: `APIClient` creates its own `URLSession` internally. There is no protocol abstraction or way to inject a mock session for unit testing.
2. **Duplicated logic across views**: `HomeView`, `TaskListView`, and `TaskService` all implement the same fetch-sort-categorize pattern independently.
3. **No offline/caching layer**: The app has no local persistence (Core Data, SwiftData, or even UserDefaults caching). If the server is unreachable, users see empty screens.
4. **No authentication flow UI**: There is no login screen. `AuthService` exists but is never used in any view. Users cannot actually log in through the app.
5. **`TaskService` is unused**: Despite being a well-designed service layer, no view instantiates or uses `TaskService`.
6. **No navigation coordination**: Views create their own navigation state. A coordinator pattern would improve deep linking and state management.

### Recommendations

1. **Introduce a protocol for networking** (e.g., `APIClientProtocol`) to enable mocking in tests.
2. **Use `TaskService` as the single source of truth** for task data, injected as an `@EnvironmentObject` alongside `APIClient`.
3. **Add SwiftData or Core Data persistence** for offline support and faster app startup.
4. **Build an authentication flow** with a login screen that uses `AuthService`.
5. **Consider a coordinator pattern** or `NavigationPath`-based routing for better navigation management.

---

## Files Modified

| File | Changes |
|------|---------|
| `ios/TodoCLI/Services/KeychainManager.swift` | **NEW** -- Secure Keychain wrapper |
| `ios/TodoCLI/Services/APIClient.swift` | Token storage migrated to Keychain; HTTPS enforcement; login input validation; login token storage fix; path sanitization; cookie cleanup on logout |
| `ios/TodoCLI/Views/Tasks/TaskRowView.swift` | Accessibility: combined element, label, hint, traits |
| `ios/TodoCLI/Views/Focus/FocusTimerView.swift` | Accessibility: timer label, control button labels/hints |
| `ios/TodoCLI/Views/Home/HomeView.swift` | Error display overlay; stat pill accessibility |
| `ios/TodoCLI/Views/Home/QuickAddBar.swift` | Accessibility: clear/submit button labels |
| `ios/TodoCLI/Views/Tasks/TaskListView.swift` | Error alert display |
| `ios/TodoCLI/Views/Tasks/TaskCreateView.swift` | Error state and alert display |
| `ios/TodoCLI/Views/Projects/ProjectListView.swift` | Error alert display; project card accessibility |
| `ios/TodoCLI/Views/Components/EmptyStateView.swift` | Accessibility: combined element with label |
| `ios/TodoCLI/Views/Components/PriorityBadge.swift` | Accessibility labels on both variants |
| `ios/TodoCLI/Views/Components/TagChip.swift` | Accessibility label |
| `ios/TodoCLI/Views/Settings/SettingsView.swift` | Server URL validation before saving |
| `ios/TodoCLI/App/ContentView.swift` | Accessibility hint on FAB |
| `tests/test_analytics.py` | Fixed date-dependent test failure |

---

## Next Steps

**Priority 1 (Critical):**
1. Add certificate pinning for production API endpoints
2. Build login/registration UI using existing `AuthService`
3. Add token refresh mechanism before expiry

**Priority 2 (High):**
4. Create `TodoCLITests` target with unit tests for `KeychainManager`, `APIClient`, and model decoding
5. Refactor views to use `TaskService` instead of duplicating fetch/sort/toggle logic
6. Add offline caching with SwiftData

**Priority 3 (Medium):**
7. Cache `DateFormatter` instances as static properties
8. Implement optimistic UI updates for task mutations
9. Add Dynamic Type support to fixed-size fonts
10. Add Reduce Motion support for animations
11. Post VoiceOver announcements for task CRUD operations

**Priority 4 (Low):**
12. Add pagination for large task lists
13. Implement coordinator-based navigation
14. Add UI tests for critical flows
15. Add App Transport Security configuration to `Info.plist`
