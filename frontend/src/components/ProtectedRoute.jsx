import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children, allowedRoles }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-container-lowest">
        <div className="flex flex-col items-center space-y-md">
          <span className="material-symbols-outlined animate-spin text-primary text-3xl">refresh</span>
          <span className="text-body-md text-secondary font-medium">安全验证中...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    if (user.role === 'admin') {
      return <Navigate to="/admin" replace />;
    }
    if (user.role === 'teacher') {
      return <Navigate to="/teacher" replace />;
    }
    return <Navigate to="/dashboard" replace />;
  }

  return children;
}
