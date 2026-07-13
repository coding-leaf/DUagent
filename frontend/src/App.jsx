import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import Login from './pages/Login';
import Register from './pages/Register';
import Success from './pages/Success';
import Dashboard from './pages/Dashboard';
import StudentProfile from './pages/StudentProfile';
import TeacherConsole from './pages/TeacherConsole';
import TeacherStudentReport from './pages/TeacherStudentReport';
import LearningPath from './pages/LearningPath';

import Quiz from './pages/Quiz';
import AIChat from './pages/AIChat';
import LearningEffects from './pages/LearningEffects';
import PracticeResult from './pages/PracticeResult';
import AdminConsole from './pages/AdminConsole';
import ResourceDetail from './pages/ResourceDetail';
import PersonalizedResources from './pages/PersonalizedResources';
import PersonalizedResourceGenerate from './pages/PersonalizedResourceGenerate';
import CodeProblemPractice from './pages/CodeProblemPractice';
import { AuthProvider } from './context/AuthContext';
import { CourseProvider } from './context/CourseContext';
import { ChatProvider } from './context/ChatContext';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <Router>
      <Toaster position="top-center" richColors />
      <AuthProvider>
        <CourseProvider>
          <ChatProvider>
            <Routes>
              {/* Alias /login to the Login page for clearer redirects */}
              <Route path="/" element={<Login />} />
              <Route path="/login" element={<Navigate to="/" replace />} />
              <Route path="/register" element={<Register />} />
              <Route path="/success" element={<Success />} />
              
              {/* Student routes */}
              <Route path="/dashboard" element={<ProtectedRoute allowedRoles={['student']}><Dashboard /></ProtectedRoute>} />
              <Route path="/resource/:id" element={<ProtectedRoute allowedRoles={['student', 'teacher']}><ResourceDetail /></ProtectedRoute>} />
              <Route path="/profile" element={<ProtectedRoute allowedRoles={['student']}><StudentProfile /></ProtectedRoute>} />
              <Route path="/learning-path" element={<ProtectedRoute allowedRoles={['student']}><LearningPath /></ProtectedRoute>} />

              <Route path="/quiz" element={<ProtectedRoute allowedRoles={['student']}><Quiz /></ProtectedRoute>} />
              <Route path="/quiz/result" element={<ProtectedRoute allowedRoles={['student']}><PracticeResult /></ProtectedRoute>} />
              <Route path="/ai-chat" element={<ProtectedRoute allowedRoles={['student']}><AIChat /></ProtectedRoute>} />
              <Route path="/learning-effects" element={<ProtectedRoute allowedRoles={['student']}><LearningEffects /></ProtectedRoute>} />
              <Route path="/personalized-resources" element={<ProtectedRoute allowedRoles={['student']}><PersonalizedResources /></ProtectedRoute>} />
              <Route path="/personalized-resources/generate" element={<ProtectedRoute allowedRoles={['student']}><PersonalizedResourceGenerate /></ProtectedRoute>} />
              <Route path="/code-problems/:problemId" element={<ProtectedRoute allowedRoles={['student']}><CodeProblemPractice /></ProtectedRoute>} />
              
              {/* Teacher / Admin routes */}
              <Route path="/teacher" element={<ProtectedRoute allowedRoles={['teacher', 'admin']}><TeacherConsole /></ProtectedRoute>} />
              <Route path="/teacher/report" element={<ProtectedRoute allowedRoles={['teacher', 'admin']}><TeacherStudentReport /></ProtectedRoute>} />
              
              {/* Admin routes */}
              <Route path="/admin" element={<ProtectedRoute allowedRoles={['admin']}><AdminConsole /></ProtectedRoute>} />
            </Routes>
          </ChatProvider>
        </CourseProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
