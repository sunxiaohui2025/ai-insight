import React from 'react';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material';
import { Link, Outlet, useLocation } from 'react-router-dom';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ArticleIcon from '@mui/icons-material/Article';
import CategoryIcon from '@mui/icons-material/Category';
import PeopleIcon from '@mui/icons-material/People';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import ExtensionIcon from '@mui/icons-material/Extension';
import BackupIcon from '@mui/icons-material/Backup';

const drawerWidth = 260;

const menuItems = [
  { text: '概览', icon: <DashboardIcon />, path: '/admin' },
  { text: '内容管理', icon: <ArticleIcon />, path: '/admin/content' },
  { text: '分类管理', icon: <CategoryIcon />, path: '/admin/categories' },
  { text: '模型管理', icon: <ModelTrainingIcon />, path: '/admin/models' },
  { text: 'Skill 管理', icon: <ExtensionIcon />, path: '/admin/skills' },
  { text: '用户管理', icon: <PeopleIcon />, path: '/admin/users' },
  { text: '数据备份', icon: <BackupIcon />, path: '/admin/data' },
];

const AdminLayout: React.FC = () => {
  const location = useLocation();

  // 概览只在精确匹配时高亮，其他菜单在子路由下也保持高亮
  const isSelected = (path: string) =>
    path === '/admin' ? location.pathname === '/admin' : location.pathname.startsWith(path);

  return (
    <Box sx={{ display: 'flex' }}>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            borderRight: '1px solid #dadce0',
          },
        }}
      >
        <Toolbar>
          <Typography variant="h6" sx={{ fontWeight: 600, color: 'primary.main' }}>
            后台管理
          </Typography>
        </Toolbar>
        <List>
          {menuItems.map((item) => (
            <ListItem key={item.path} disablePadding>
              <ListItemButton
                component={Link}
                to={item.path}
                selected={isSelected(item.path)}
                sx={{
                  '&.Mui-selected': {
                    bgcolor: '#f7e0d8',
                    color: 'secondary.main',
                    '&:hover': {
                      bgcolor: '#f1d2c8',
                    },
                  },
                }}
              >
                <ListItemIcon sx={{ color: isSelected(item.path) ? 'secondary.main' : 'inherit' }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3, bgcolor: 'grey.50', minHeight: '100vh' }}>
        <Outlet />
      </Box>
    </Box>
  );
};

export default AdminLayout;
