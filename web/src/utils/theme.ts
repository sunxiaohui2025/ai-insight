import { createTheme } from '@mui/material/styles';

// 参考原有暖色调设计风格
export const theme = createTheme({
  palette: {
    primary: {
      main: '#cf765f', // 暖橙红色
      light: '#e8a36b',
      dark: '#bd6d5c',
    },
    secondary: {
      main: '#141413', // 深墨色
      light: '#5f6368',
      dark: '#000000',
    },
    error: {
      main: '#c5221f',
    },
    warning: {
      main: '#e37400',
    },
    background: {
      default: '#f8fafd',
      paper: '#ffffff',
    },
    text: {
      primary: '#202124',
      secondary: '#5f6368',
    },
  },
  typography: {
    fontFamily: [
      'Arial',
      '"Noto Sans SC"',
      '-apple-system',
      'BlinkMacSystemFont',
      'sans-serif',
    ].join(','),
    h1: {
      fontSize: '2.5rem',
      fontWeight: 500,
      letterSpacing: '-0.05em',
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 500,
      letterSpacing: '-0.04em',
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 500,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 500,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 500,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 500,
    },
    button: {
      textTransform: 'none',
      fontWeight: 500,
    },
  },
  shape: {
    borderRadius: 15,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 24,
          padding: '10px 18px',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: 'none',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 15,
          border: '1px solid #e3e6e9',
          boxShadow: 'none',
          transition: 'transform 0.22s cubic-bezier(0.2, 0.7, 0.2, 1), box-shadow 0.22s, border-color 0.22s',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: '0 12px 32px rgba(0,0,0,0.1)',
            borderColor: '#c4c8ce',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: 'none',
          borderBottom: '1px solid #eef0f2',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 8,
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 20,
        },
      },
    },
  },
});
