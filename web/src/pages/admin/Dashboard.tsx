import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Card,
  CardContent,
} from '@mui/material';
import ArticleIcon from '@mui/icons-material/Article';
import CategoryIcon from '@mui/icons-material/Category';
import VisibilityIcon from '@mui/icons-material/Visibility';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import { adminDashboardApi } from '../../services/api';

const Dashboard: React.FC = () => {
  const [data, setData] = useState({
    total_articles: 0,
    total_categories: 0,
    total_reads: 0,
    new_this_month: 0,
  });

  useEffect(() => {
    adminDashboardApi
      .getStats()
      .then((res) => setData(res.data))
      .catch(() => {});
  }, []);

  const stats = [
    { title: '总文章数', value: String(data.total_articles), icon: <ArticleIcon />, color: '#1a73e8' },
    { title: '总分类数', value: String(data.total_categories), icon: <CategoryIcon />, color: '#34a853' },
    { title: '总阅读量', value: String(data.total_reads), icon: <VisibilityIcon />, color: '#fbbc04' },
    { title: '本月新增', value: String(data.new_this_month), icon: <TrendingUpIcon />, color: '#ea4335' },
  ];

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 600, mb: 4 }}>
        概览
      </Typography>

      <Grid container spacing={3}>
        {stats.map((stat, index) => (
          <Grid size={{ xs: 12, sm: 6, md: 3 }} key={index}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      {stat.title}
                    </Typography>
                    <Typography variant="h4" sx={{ fontWeight: 600 }}>
                      {stat.value}
                    </Typography>
                  </Box>
                  <Box
                    sx={{
                      width: 56,
                      height: 56,
                      borderRadius: 2,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      bgcolor: `${stat.color}20`,
                      color: stat.color,
                    }}
                  >
                    {stat.icon}
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Paper sx={{ p: 3, mt: 4 }}>
        <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
          欢迎使用 AI InSight后台管理系统
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
          在这里你可以：
        </Typography>
        <Box component="ul" sx={{ color: 'text.secondary' }}>
          <li>使用富文本编辑器手写博客文章</li>
          <li>通过 AI Agent 辅助创作，解析链接或文件生成文章</li>
          <li>管理文章分类和内容</li>
          <li>配置 Agent Skills 和 LLM 模型</li>
          <li>管理用户权限</li>
        </Box>
      </Paper>
    </Box>
  );
};

export default Dashboard;
