const fs = require('fs');
const path = './src/pages/TeacherConsole.jsx';
let content = fs.readFileSync(path, 'utf8');

const newImports = `import ClassSelectorRow from '../components/teacher/ClassSelectorRow';
import TeacherResourceSection from '../components/teacher/TeacherResourceSection';
import StudentMonitoringSection from '../components/teacher/StudentMonitoringSection';
import ClassInsightsSection from '../components/teacher/ClassInsightsSection';`;

const newSections = `          {/* Class Selection Row */}
          <ClassSelectorRow 
            classes={classes} 
            activeClass={activeClass} 
            setActiveClass={setActiveClass} 
            activeClassInfo={activeClassInfo} 
          />

          {/* Class Learning Resources */}
          <TeacherResourceSection
            activeClassInfo={activeClassInfo}
            resourcesLoading={resourcesLoading}
            resourcesError={resourcesError}
            resources={resources}
            groupedResources={groupedResources}
            expandedChapter={expandedChapter}
            setExpandedChapter={setExpandedChapter}
            handleCopyCourseCode={handleCopyCourseCode}
            copiedCourseCode={copiedCourseCode}
            navigate={navigate}
          />

          {/* Student Monitoring Table */}
          <StudentMonitoringSection
            activeClassInfo={activeClassInfo}
            activeClass={activeClass}
            studentsLoading={studentsLoading}
            studentsError={studentsError}
            students={students}
            navigate={navigate}
          />

          {/* Class Statistics Section */}
          <ClassInsightsSection
            insightsLoading={insightsLoading}
            insightsError={insightsError}
            insights={insights}
          />`;

content = content.replace(
  /const useMock = import\.meta\.env\.VITE_USE_MOCK === 'true';\nconst resourceTypeLabels = \{\n  document: '文档',\n  reading: '阅读材料',\n  code: '代码示例',\n  mindmap: '思维导图',\n  video: '视频',\n\};\n/,
  newImports + '\n'
);

const startIdx = content.indexOf('          {/* Class Selection Row */}');
const endStr = '          </section>';
const statSectionIdx = content.indexOf('          {/* Class Statistics Section */}');
const endIdx = content.indexOf(endStr, statSectionIdx) + endStr.length;

if (startIdx !== -1 && statSectionIdx !== -1) {
  content = content.substring(0, startIdx) + newSections + content.substring(endIdx);
  fs.writeFileSync(path, content);
  console.log("Updated TeacherConsole.jsx successfully");
} else {
  console.error("Failed to find section bounds");
}
