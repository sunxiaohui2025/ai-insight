import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { theme } from './utils/theme';
import Navbar from './components/Navbar';
import AdminLayout from './components/AdminLayout';

// Pages
import Home from './pages/Home';
import ArticleList from './pages/ArticleList';
import ArticleDetail from './pages/ArticleDetail';
import Login from './pages/Login';
import Register from './pages/Register';

// Admin Pages
import Dashboard from './pages/admin/Dashboard';
import Models from './pages/admin/Models';
import CategoryManagement from './pages/admin/CategoryManagement';
import ContentManagement from './pages/admin/ContentManagement';
import ContentPublish from './pages/admin/ContentPublish';
import SkillsPage from './pages/admin/Skills';
import UserManagement from './pages/admin/UserManagement';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();
  
  if (loading) {
    return <div>Loading...</div>;
  }
  
  return user ? <>{children}</> : <Navigate to="/login" />;
};

const AdminRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isAdmin, loading } = useAuth();
  
  if (loading) {
    return <div>Loading...</div>;
  }
  
  if (!user) {
    return <Navigate to="/login" />;
  }
  
  if (!isAdmin) {
    return <Navigate to="/" />;
  }
  
  return <>{children}</>;
};

function AppContent() {
  return (
    <Router>
      <Routes>
        {/* Public Routes */}
        <Route
          path="/"
          element={
            <>
              <Navbar />
              <Home />
            </>
          }
        />
        <Route
          path="/projects"
          element={
            <>
              <Navbar />
              <ArticleList
                sectionId={1}
                title="项目沉淀"
                description="记录项目开发过程中的技术实践和经验总结"
                eyebrow="PROJECT NOTES"
                svgPosition="right"
              />
            </>
          }
        />
        <Route
          path="/insights"
          element={
            <>
              <Navbar />
              <ArticleList
                sectionId={2}
                title="研究解读"
                description="深度解读第三方技术文章和研究成果"
                eyebrow="RESEARCH & INTERPRETATION"
                svgPosition="left"
              />
            </>
          }
        />
        <Route
          path="/article/:id"
          element={
            <>
              <Navbar />
              <ArticleDetail />
            </>
          }
        />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Admin Routes */}
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminLayout />
            </AdminRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="content" element={<ContentManagement />} />
          <Route path="content/new" element={<ContentPublish />} />
          <Route path="content/:id/edit" element={<ContentPublish />} />
          {/* 旧路径重定向到合并后的内容管理 */}
          <Route path="publish" element={<Navigate to="/admin/content" replace />} />
          <Route path="articles" element={<Navigate to="/admin/content" replace />} />
          <Route path="categories" element={<CategoryManagement />} />
          <Route path="agent" element={<div>Agent 配置页面开发中...</div>} />
          <Route path="skills" element={<SkillsPage />} />
          <Route path="models" element={<Models />} />
          <Route path="users" element={<UserManagement />} />
        </Route>
      </Routes>
    </Router>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
