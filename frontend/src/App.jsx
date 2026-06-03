import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import Success from './pages/Success';
import Dashboard from './pages/Dashboard';
import StudentProfile from './pages/StudentProfile';
import TeacherConsole from './pages/TeacherConsole';
import TeacherStudentReport from './pages/TeacherStudentReport';
import LearningPath from './pages/LearningPath';
import ResourceDetail from './pages/ResourceDetail';
import Quiz from './pages/Quiz';
import AIChat from './pages/AIChat';
import LearningEffects from './pages/LearningEffects';
import PracticeResult from './pages/PracticeResult';
import AdminConsole from './pages/AdminConsole';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/success" element={<Success />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/profile" element={<StudentProfile />} />
        <Route path="/teacher" element={<TeacherConsole />} />
        <Route path="/teacher/report" element={<TeacherStudentReport />} />
        <Route path="/learning-path" element={<LearningPath />} />
        <Route path="/resource/detail" element={<ResourceDetail />} />
        <Route path="/quiz" element={<Quiz />} />
        <Route path="/quiz/result" element={<PracticeResult />} />
        <Route path="/ai-chat" element={<AIChat />} />
        <Route path="/learning-effects" element={<LearningEffects />} />
        <Route path="/admin" element={<AdminConsole />} />
      </Routes>
    </Router>
  );
}

export default App;
