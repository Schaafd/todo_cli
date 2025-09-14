# README Phase Update Template

This template helps maintain consistency when updating the README.md after each phase completion.

## Phase Completion Checklist

### 1. Update Phase Status Badges
- [ ] Change current phase badge from "in progress" to "complete" 
- [ ] Add new phase badge as "in progress"

### 2. Update Features Section
- [ ] Move completed phase features from "planned" to "complete"
- [ ] Add detailed descriptions of new capabilities
- [ ] Include code examples for new features
- [ ] Update feature counts and statistics

### 3. Update Quick Start Guide
- [ ] Add examples for new commands/features
- [ ] Update advanced syntax examples
- [ ] Refresh dashboard view example if changed

### 4. Update Architecture Section
- [ ] Add new modules/files if created
- [ ] Update architecture diagram/description
- [ ] Document new design patterns or principles

### 5. Update Development Roadmap
- [ ] Mark completed phase as ✅
- [ ] Update next phase status to 🔄 
- [ ] Add or refine future phase descriptions
- [ ] Update completion estimates if needed

### 6. Update Testing Information
- [ ] Update test count and coverage statistics
- [ ] Add examples for testing new features
- [ ] Document any new testing patterns

### 7. Update Installation/Usage
- [ ] Add any new prerequisites
- [ ] Update installation steps if changed
- [ ] Refresh usage examples with new features

## Example Phase Badge Updates

```markdown
<!-- Before -->
[![Phase 1 Complete](https://img.shields.io/badge/phase-1%20complete-green.svg)](./PLAN.md)
[![Phase 2 In Progress](https://img.shields.io/badge/phase-2-in%20progress-yellow.svg)](./PLAN.md)

<!-- After Phase 2 completion -->
[![Phase 1 Complete](https://img.shields.io/badge/phase-1%20complete-green.svg)](./PLAN.md)
[![Phase 2 Complete](https://img.shields.io/badge/phase-2%20complete-green.svg)](./PLAN.md)
[![Phase 3 In Progress](https://img.shields.io/badge/phase-3-in%20progress-yellow.svg)](./PLAN.md)
```

## Example Roadmap Updates

```markdown
### ✅ Phase N: [Phase Name] (Complete)
- [x] Feature 1 description
- [x] Feature 2 description
- [x] Feature 3 description

### 🔄 Phase N+1: [Next Phase Name] (In Progress)
- [ ] Planned feature 1
- [ ] Planned feature 2
```

## Commit Message Template

```
docs: update README.md for Phase N completion

📚 Documentation Updates:
- Mark Phase N as complete with feature details
- Update Phase N+1 status to in progress
- Add examples for new [specific features]
- Update architecture section with [new components]
- Refresh installation/usage guides

✨ New Features Documented:
- [Feature 1]: [Brief description]
- [Feature 2]: [Brief description]
- [Feature 3]: [Brief description]

🔄 Next Phase Ready:
- Phase N+1 roadmap updated
- Development environment ready
```

## Review Checklist Before Commit

- [ ] All badges reflect current status
- [ ] Feature examples work with current codebase
- [ ] Installation steps are accurate
- [ ] Architecture section matches current structure  
- [ ] Roadmap phases are properly sequenced
- [ ] Links and references are valid
- [ ] Typos and formatting are clean