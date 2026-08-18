import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  TextField,
  Button,
  Box,
  Alert,
  CircularProgress,
} from '@mui/material';
import { authApi } from '../services/api';

/**
 * 普通用户注册页
 * 注册成功后账号为「待审批」状态，需管理员在后台批准后才能登录阅读文章。
 */
const Register: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('密码至少需要 8 位');
      return;
    }
    if (password !== confirm) {
      setError('两次输入的密码不一致');
      return;
    }

    setLoading(true);
    try {
      // 后端：注册后 status=pending，需要管理员审批
      await authApi.register(email, password, name);
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || '注册失败，请稍后再试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ py: 8 }}>
      <Paper elevation={3} sx={{ p: 4, borderRadius: 2 }}>
        <Typography
          variant="h4"
          component="h1"
          gutterBottom
          sx={{ fontWeight: 600, mb: 1, textAlign: 'center' }}
        >
          注册账号
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mb: 3 }}>
          注册后需等待管理员审批，审批通过后即可登录阅读文章
        </Typography>

        {success ? (
          <Box sx={{ textAlign: 'center' }}>
            <Alert severity="success" sx={{ mb: 3 }}>
              注册成功！请等待管理员审批，通过后即可登录使用。
            </Alert>
            <Button component={Link} to="/login" variant="contained" sx={{ mt: 1 }}>
              前往登录
            </Button>
          </Box>
        ) : (
          <form onSubmit={handleSubmit}>
            {error && (
              <Alert severity="error" sx={{ mb: 3 }}>
                {error}
              </Alert>
            )}

            <TextField
              fullWidth
              label="昵称"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              margin="normal"
              autoComplete="name"
            />
            <TextField
              fullWidth
              label="邮箱"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              margin="normal"
              autoComplete="email"
            />
            <TextField
              fullWidth
              label="密码"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              margin="normal"
              autoComplete="new-password"
              helperText="至少 8 位"
            />
            <TextField
              fullWidth
              label="确认密码"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              margin="normal"
              autoComplete="new-password"
            />

            <Button
              fullWidth
              type="submit"
              variant="contained"
              size="large"
              disabled={loading}
              sx={{ mt: 3, mb: 2 }}
            >
              {loading ? <CircularProgress size={22} color="inherit" /> : '注册'}
            </Button>
          </form>
        )}

        <Box sx={{ textAlign: 'center', mt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            已有账号？{' '}
            <Link to="/login" style={{ color: 'primary.main' }}>
              去登录
            </Link>
          </Typography>
        </Box>
      </Paper>
    </Container>
  );
};

export default Register;
