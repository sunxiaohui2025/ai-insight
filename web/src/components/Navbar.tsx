import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Avatar,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Navbar: React.FC = () => {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const menuOpen = Boolean(menuAnchor);

  const closeMenu = () => setMenuAnchor(null);

  const handleLogout = () => {
    closeMenu();
    logout();
    navigate('/');
  };

  const goAdmin = () => {
    closeMenu();
    navigate('/admin');
  };

  return (
    <AppBar
      position="sticky"
      color="default"
      sx={{
        bgcolor: 'white',
        height: '72px',
        justifyContent: 'center',
      }}
    >
      <Toolbar sx={{ justifyContent: 'space-between', px: { xs: 2, md: '5vw' } }}>
        {/* Brand */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Box
            component={Link}
            to="/"
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              textDecoration: 'none',
              color: 'text.primary',
              fontSize: '19px',
              fontWeight: 600,
              letterSpacing: '-0.03em',
            }}
          >
            <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
              <circle cx="15" cy="15" r="13" fill="#cf765f" />
              <path d="M8 18.5c2.3-5.8 5.4-8.5 8.4-7.1 2.4 1.1 2.8 4.7 5.6 4.2" fill="none" stroke="#fff8f1" strokeWidth="2.2" strokeLinecap="round" />
              <circle cx="9" cy="19" r="1.6" fill="#fff8f1" />
              <circle cx="21" cy="15.5" r="1.6" fill="#fff8f1" />
            </svg>
            <Box component="span" sx={{ fontWeight: 700 }}>AI <Box component="span" sx={{ fontWeight: 500 }}>InSight</Box></Box>
          </Box>

          {/* Navigation */}
          <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: '25px', color: 'text.secondary' }}>
            <Button
              component={Link}
              to="/"
              sx={{
                color: 'inherit',
                textTransform: 'none',
                padding: '25px 0',
                borderRadius: 0,
                minWidth: 'auto',
                '&:hover': {
                  color: 'primary.main',
                  background: 'transparent',
                },
              }}
            >
              首页
            </Button>

            <Button
              component={Link}
              to="/projects"
              sx={{
                color: 'inherit',
                textTransform: 'none',
                padding: '25px 0',
                borderRadius: 0,
                minWidth: 'auto',
                '&:hover': {
                  color: 'primary.main',
                  background: 'transparent',
                },
              }}
            >
              项目沉淀
            </Button>

            <Button
              component={Link}
              to="/insights"
              sx={{
                color: 'inherit',
                textTransform: 'none',
                padding: '25px 0',
                borderRadius: 0,
                minWidth: 'auto',
                '&:hover': {
                  color: 'primary.main',
                  background: 'transparent',
                },
              }}
            >
              研究解读
            </Button>
          </Box>
        </Box>

        {/* Actions */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {user ? (
            <>
              {/* 用户名为默认显示，后台管理与退出收进下拉菜单 */}
              <Button
                onClick={(e) => setMenuAnchor(e.currentTarget)}
                endIcon={
                  <ExpandMoreIcon
                    sx={{
                      transition: 'transform 0.2s',
                      transform: menuOpen ? 'rotate(180deg)' : 'none',
                    }}
                  />
                }
                aria-haspopup="true"
                aria-expanded={menuOpen}
                aria-controls={menuOpen ? 'user-menu' : undefined}
                aria-label={`用户菜单：${user.name}`}
                sx={{
                  textTransform: 'none',
                  fontSize: '13px',
                  color: 'text.primary',
                  gap: '2px',
                  pl: '6px',
                  pr: '10px',
                  py: '5px',
                  borderRadius: '999px',
                  border: '1px solid',
                  borderColor: 'divider',
                  '&:hover': { borderColor: 'primary.main', background: 'transparent' },
                }}
              >
                <Avatar
                  sx={{
                    width: 24,
                    height: 24,
                    mr: '7px',
                    fontSize: '12px',
                    fontWeight: 600,
                    bgcolor: 'primary.main',
                  }}
                >
                  {user.name?.trim().charAt(0).toUpperCase() || '?'}
                </Avatar>
                {user.name}
              </Button>

              <Menu
                id="user-menu"
                anchorEl={menuAnchor}
                open={menuOpen}
                onClose={closeMenu}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{
                  paper: {
                    sx: { mt: 1, minWidth: 190, borderRadius: '10px' },
                  },
                }}
              >
                <Box sx={{ px: 2, py: 1 }}>
                  <Typography sx={{ fontSize: '13px', fontWeight: 600 }}>{user.name}</Typography>
                  <Typography sx={{ fontSize: '11.5px', color: 'text.secondary' }}>
                    {user.email}
                  </Typography>
                </Box>
                <Divider />

                {isAdmin && (
                  <MenuItem onClick={goAdmin} sx={{ fontSize: '13px', py: 1 }}>
                    <ListItemIcon>
                      <SettingsIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText slotProps={{ primary: { sx: { fontSize: '13px' } } }}>
                      后台管理
                    </ListItemText>
                  </MenuItem>
                )}

                <MenuItem onClick={handleLogout} sx={{ fontSize: '13px', py: 1 }}>
                  <ListItemIcon>
                    <LogoutIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText slotProps={{ primary: { sx: { fontSize: '13px' } } }}>退出</ListItemText>
                </MenuItem>
              </Menu>
            </>
          ) : (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Button
                component={Link}
                to="/register"
                size="small"
                sx={{
                  textTransform: 'none',
                  color: 'text.secondary',
                  '&:hover': { color: 'primary.main', background: 'transparent' },
                }}
              >
                注册
              </Button>
              <Button
                component={Link}
                to="/login"
                variant="contained"
                size="small"
                sx={{ textTransform: 'none' }}
              >
                登录
              </Button>
            </Box>
          )}
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
