# Frontend Phase 2: UI Component Splitting Implementation Plan

**Objective**: Extract fat JSX blocks from `TeacherConsole.jsx` and `StudentProfile.jsx` into smaller, pure Presentational Components.

---

### Task 1: Extract `TeacherConsole` Components
**Goal**: Break `src/pages/TeacherConsole.jsx` into 4 sub-components.
**Actions**:
1. **Create `src/components/teacher/ClassSelectorRow.jsx`**:
   - Extract the entire `<section className="mb-margin">` under `{/* Class Selection Row */}`.
   - Props needed: `classes`, `activeClass`, `setActiveClass`, `activeClassInfo`.
2. **Create `src/components/teacher/TeacherResourceSection.jsx`**:
   - Extract the `<section>` under `{/* Class Learning Resources */}`.
   - Props needed: `activeClassInfo`, `resourcesLoading`, `resourcesError`, `resources`, `groupedResources`, `expandedChapter`, `setExpandedChapter`, `handleCopyCourseCode`, `copiedCourseCode`, `navigate`.
3. **Create `src/components/teacher/StudentMonitoringSection.jsx`**:
   - Extract the `<section>` under `{/* Student Monitoring Table */}`.
   - Props needed: `activeClassInfo`, `activeClass`, `studentsLoading`, `studentsError`, `students`, `navigate`.
4. **Create `src/components/teacher/ClassInsightsSection.jsx`**:
   - Extract the `<section>` under `{/* Class Statistics Section */}`.
   - Props needed: `insightsLoading`, `insightsError`, `insights`.
5. **Update `TeacherConsole.jsx`**:
   - Import the 4 new components.
   - Replace the large code blocks with `<ClassSelectorRow ... />`, `<TeacherResourceSection ... />`, `<StudentMonitoringSection ... />`, and `<ClassInsightsSection ... />`.

---

### Task 2: Extract `StudentProfile` Components (Part 1)
**Goal**: Break the top half of `src/pages/StudentProfile.jsx`.
**Actions**:
1. **Create `src/components/profile/ProfileHeaderCard.jsx`**:
   - Extract the div under `{/* 卡片 1：个人信息 */}`.
   - Props needed: `displayInitial`, `displayName`, `discipline_badge`, `disciplineBadgeView`, `currentCourseName`, `profileFields`.
2. **Create `src/components/profile/LearningArchiveCard.jsx`**:
   - Extract the `<section>` that renders "学习档案".
   - Props needed: `handleProfileRefresh`, `refreshing`, `refreshMessage`, `refreshError`, `profile_dimensions`, `formatDimensionValue`, `sourceLabel`.
3. **Create `src/components/profile/LearningDirectionCard.jsx`**:
   - Extract the block under `{/* 学习方向 */}` and `{/* 个性化偏好 */}`.
   - Props needed: `drive_intent`, `handleGoalChange`, `goalSubmitting`, `customInstruction`, `setCustomInstruction`, `handleInstructionSubmit`, `instructionSubmitting`, `instructionError`, `instructionSuccess`.
4. **Update `StudentProfile.jsx`**:
   - Replace the top blocks with the new components.

---

### Task 3: Extract `StudentProfile` Components (Part 2)
**Goal**: Break the Bento Grid (bottom half) of `src/pages/StudentProfile.jsx`.
**Actions**:
1. **Create `src/components/profile/ModalityPreferenceCard.jsx`**:
   - Extract `{/* 卡片 2：模态偏好 */}`.
   - Props needed: `modal_preference`.
2. **Create `src/components/profile/GuidanceLevelCard.jsx`**:
   - Extract `{/* Granularity Card */}`.
   - Props needed: `localGuidanceLevel`, `handleGuidanceChange`, `guidanceSubmitting`, `guidanceUpdatedText`.
3. **Create `src/components/profile/KnowledgeRadarCard.jsx`**:
   - Extract `{/* 卡片 4：知识坐标 + 认知盲区 */}`.
   - Props needed: `knowledge_coordinates`, `cognitive_blindspots`, `daysAgoText`, `labelValue`.
4. **Create `src/components/profile/LearningStateCard.jsx`**:
   - Extract `{/* 卡片 5：驱动力 + 学科勋章 */}`.
   - Props needed: `drive_intent`, `habits`, `driveScore`, `discipline_badge`, `disciplineBadgeView`, `labelValue`.
5. **Update `StudentProfile.jsx`**:
   - Replace the Bento Grid blocks with these new components.
   - Run `npm run lint` and `npm run build` to verify everything works.
