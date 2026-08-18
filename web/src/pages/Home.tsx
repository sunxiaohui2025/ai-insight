import React, { useEffect, useState } from 'react';
import {
  Container,
  Typography,
  Box,
  Grid,
  Button,
  CircularProgress,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import ArticleCard from '../components/ArticleCard';
import { Article } from '../types';
import { blogApi } from '../services/api';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';

const Home: React.FC = () => {
  const navigate = useNavigate();
  const [latestArticles, setLatestArticles] = useState<Article[]>([]);
  const [projectArticles, setProjectArticles] = useState<Article[]>([]);
  const [insightArticles, setInsightArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadArticles();
  }, []);

  const loadArticles = async () => {
    try {
      setLoading(true);
      const [latest, projects, insights] = await Promise.all([
        blogApi.getArticles({ section_id: 2, limit: 6 }), // 最近解读 - 显示研究解读的最新文章
        blogApi.getArticles({ section_id: 1, limit: 3 }), // 项目沉淀
        blogApi.getArticles({ section_id: 2, limit: 3 }), // 研究解读
      ]);

      setLatestArticles(latest.data.articles || []);
      setProjectArticles(projects.data.articles || []);
      setInsightArticles(insights.data.articles || []);
    } catch (error) {
      console.error('Failed to load articles:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 6 }}>
      {/* Hero Section */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1.15fr 0.85fr' },
          gap: { xs: 3, md: 5 },
          alignItems: 'center',
          py: '22px',
          mb: 3,
        }}
      >
        <Box>
          <Typography
            sx={{
              fontSize: '12px',
              color: 'primary.main',
              letterSpacing: '0.12em',
              fontWeight: 600,
              mb: 2,
            }}
          >
            TECHNOLOGY, EXPLAINED
          </Typography>
          <Typography
            variant="h1"
            component="h1"
            sx={{
              fontSize: { xs: '38px', md: '66px' },
              lineHeight: 1.08,
              letterSpacing: '-0.065em',
              fontWeight: 500,
              mb: 2,
            }}
          >
            把复杂技术，<br />讲成可以复用的知识
          </Typography>
          <Typography
            sx={{
              maxWidth: '540px',
              color: 'text.secondary',
              fontSize: '16px',
              lineHeight: 1.8,
              mb: 3,
            }}
          >
            从收藏的网页、项目经验到 AI 生成的一页纸解读，InSight 帮你建立一座真正可阅读、可检索、可持续积累的技术知识库。
          </Typography>
          
        </Box>

        {/* Hero Art - Hand-drawn Reading Animation */}
        <Box
          sx={{
            minHeight: { xs: '170px', md: '250px' },
            borderRadius: '28px',
            background: 'primary.main',
            position: 'relative',
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <svg
            viewBox="0 0 350 250"
            style={{
              width: '100%',
              height: '100%',
              position: 'absolute',
            }}
          >
            {/* Person's head - simple circle */}
            <circle
              cx="180"
              cy="80"
              r="25"
              fill="none"
              stroke="#141413"
              strokeWidth="4"
              strokeLinecap="round"
              className="hero-draw hero-head"
            />

            {/* Body - simple line */}
            <path
              d="M 180 105 L 180 160"
              stroke="#141413"
              strokeWidth="4"
              strokeLinecap="round"
              fill="none"
              className="hero-draw hero-body"
            />

            {/* Arms holding book */}
            <path
              d="M 180 130 L 150 140 L 140 160"
              stroke="#141413"
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
              className="hero-draw hero-arm-left"
            />
            <path
              d="M 180 130 L 210 140 L 220 160"
              stroke="#141413"
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
              className="hero-draw hero-arm-right"
            />

            {/* Book - open pages */}
            <path
              d="M 120 150 L 120 200 Q 180 205 240 200 L 240 150 Q 180 145 120 150 Z"
              fill="none"
              stroke="#141413"
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="hero-draw hero-book"
            />
            <line
              x1="180"
              y1="147"
              x2="180"
              y2="203"
              stroke="#141413"
              strokeWidth="4"
              strokeLinecap="round"
              className="hero-draw hero-book-spine"
            />

            {/* Book content lines */}
            <line x1="135" y1="165" x2="170" y2="165" stroke="#141413" strokeWidth="2.5" strokeLinecap="round" className="hero-draw hero-line-1" />
            <line x1="135" y1="175" x2="168" y2="175" stroke="#141413" strokeWidth="2.5" strokeLinecap="round" className="hero-draw hero-line-2" />
            <line x1="135" y1="185" x2="170" y2="185" stroke="#141413" strokeWidth="2.5" strokeLinecap="round" className="hero-draw hero-line-3" />

            <line x1="190" y1="165" x2="225" y2="165" stroke="#141413" strokeWidth="2.5" strokeLinecap="round" className="hero-draw hero-line-4" />
            <line x1="190" y1="175" x2="223" y2="175" stroke="#141413" strokeWidth="2.5" strokeLinecap="round" className="hero-draw hero-line-5" />
            <line x1="190" y1="185" x2="225" y2="185" stroke="#141413" strokeWidth="2.5" strokeLinecap="round" className="hero-draw hero-line-6" />

            {/* Knowledge particles floating up */}
            <circle cx="150" cy="120" r="3" fill="#e8a36b" className="hero-particle hero-particle-1" />
            <circle cx="210" cy="115" r="3.5" fill="#e8a36b" className="hero-particle hero-particle-2" />
            <circle cx="180" cy="110" r="2.5" fill="#cf765f" className="hero-particle hero-particle-3" />
          </svg>

          <style>
            {`
              @keyframes heroDraw {
                0% { stroke-dashoffset: 1000; opacity: 0; }
                10% { opacity: 1; }
                90% { stroke-dashoffset: 0; opacity: 1; }
                100% { stroke-dashoffset: 0; opacity: 0; }
              }

              @keyframes heroParticleRise {
                0% { transform: translateY(80px); opacity: 0; }
                20% { opacity: 1; }
                80% { opacity: 1; }
                100% { transform: translateY(-30px); opacity: 0; }
              }

              .hero-draw {
                stroke-dasharray: 1000;
                stroke-dashoffset: 1000;
                animation: heroDraw 8s ease-in-out infinite;
              }

              .hero-head { animation-delay: 0s; }
              .hero-body { animation-delay: 0.3s; }
              .hero-arm-left { animation-delay: 0.5s; }
              .hero-arm-right { animation-delay: 0.6s; }
              .hero-book { animation-delay: 0.8s; }
              .hero-book-spine { animation-delay: 1s; }
              .hero-line-1 { animation-delay: 1.3s; }
              .hero-line-2 { animation-delay: 1.4s; }
              .hero-line-3 { animation-delay: 1.5s; }
              .hero-line-4 { animation-delay: 1.6s; }
              .hero-line-5 { animation-delay: 1.7s; }
              .hero-line-6 { animation-delay: 1.8s; }

              .hero-particle {
                transform-box: fill-box;
                transform-origin: center;
                animation: heroParticleRise 8s ease-in-out infinite;
              }
              .hero-particle-1 { animation-delay: 2.2s; }
              .hero-particle-2 { animation-delay: 2.5s; }
              .hero-particle-3 { animation-delay: 2.8s; }
            `}
          </style>
        </Box>
      </Box>

      {/* Latest Research Articles */}
      {latestArticles.length > 0 && (
        <Box sx={{ mb: 8 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography
                sx={{
                  fontSize: '12px',
                  color: 'text.secondary',
                  letterSpacing: '0.12em',
                  fontWeight: 600,
                }}
              >
                RECENT INSIGHTS
              </Typography>
              <Typography
                variant="h4"
                component="h2"
                sx={{
                  fontSize: '28px',
                  fontWeight: 500,
                  mt: 0.5,
                  letterSpacing: '-0.04em',
                }}
              >
                最近解读
              </Typography>
            </Box>
            <Button
              endIcon={<ArrowForwardIcon />}
              onClick={() => navigate('/insights')}
              sx={{
                textTransform: 'none',
                color: 'primary.main',
                fontSize: '13px',
              }}
            >
              查看全部 →
            </Button>
          </Box>
          <Grid container spacing={3}>
            {latestArticles.map((article) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={article.id}>
                <ArticleCard article={article} />
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Project Articles */}
      {projectArticles.length > 0 && (
        <Box sx={{ mb: 8 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography
                sx={{
                  fontSize: '12px',
                  color: 'text.secondary',
                  letterSpacing: '0.12em',
                  fontWeight: 600,
                }}
              >
                PROJECT NOTES
              </Typography>
              <Typography
                variant="h4"
                component="h2"
                sx={{
                  fontSize: '28px',
                  fontWeight: 500,
                  mt: 0.5,
                  letterSpacing: '-0.04em',
                }}
              >
                项目沉淀
              </Typography>
            </Box>
            <Button
              endIcon={<ArrowForwardIcon />}
              onClick={() => navigate('/projects')}
              sx={{
                textTransform: 'none',
                color: 'primary.main',
                fontSize: '13px',
              }}
            >
              查看全部 →
            </Button>
          </Box>
          <Grid container spacing={3}>
            {projectArticles.map((article) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={article.id}>
                <ArticleCard article={article} />
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Insight Articles */}
      {insightArticles.length > 0 && (
        <Box sx={{ mb: 8 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography
                sx={{
                  fontSize: '12px',
                  color: 'text.secondary',
                  letterSpacing: '0.12em',
                  fontWeight: 600,
                }}
              >
                RESEARCH & INTERPRETATION
              </Typography>
              <Typography
                variant="h4"
                component="h2"
                sx={{
                  fontSize: '28px',
                  fontWeight: 500,
                  mt: 0.5,
                  letterSpacing: '-0.04em',
                }}
              >
                研究解读
              </Typography>
            </Box>
            <Button
              endIcon={<ArrowForwardIcon />}
              onClick={() => navigate('/insights')}
              sx={{
                textTransform: 'none',
                color: 'primary.main',
                fontSize: '13px',
              }}
            >
              查看全部 →
            </Button>
          </Box>
          <Grid container spacing={3}>
            {insightArticles.map((article) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={article.id}>
                <ArticleCard article={article} />
              </Grid>
            ))}
          </Grid>
        </Box>
      )}
    </Container>
  );
};

export default Home;
