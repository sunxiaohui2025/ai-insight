import React, { useEffect, useState } from 'react';
import {
  Container,
  Typography,
  Box,
  Grid,
  Chip,
  CircularProgress,
  Pagination,
} from '@mui/material';
import ArticleCard from '../components/ArticleCard';
import { Article, Category } from '../types';
import { blogApi } from '../services/api';

interface ArticleListProps {
  sectionId: number;
  title: string;
  description: string;
  eyebrow: string;
  svgPosition: 'left' | 'right';
}

const ArticleList: React.FC<ArticleListProps> = ({
  sectionId,
  title,
  description,
  eyebrow,
  svgPosition
}) => {
  const [articles, setArticles] = useState<Article[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 12;

  useEffect(() => {
    loadCategories();
  }, [sectionId]);

  useEffect(() => {
    loadArticles();
  }, [sectionId, selectedCategory, page]);

  const loadCategories = async () => {
    try {
      const response = await blogApi.getCategories(sectionId);
      setCategories(response.data || []);
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  };

  const loadArticles = async () => {
    try {
      setLoading(true);
      const response = await blogApi.getArticles({
        section_id: sectionId,
        category_id: selectedCategory,
        page,
        limit,
      });
      setArticles(response.data.articles || []);
      setTotal(response.data.total || 0);
    } catch (error) {
      console.error('Failed to load articles:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCategoryClick = (categoryId: number | undefined) => {
    setSelectedCategory(categoryId);
    setPage(1);
  };

  const handlePageChange = (_: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const totalPages = Math.ceil(total / limit);

  // SVG动画 - 项目沉淀：混乱线团 → 知识卡片
  const ProjectSVG = () => (
    <svg viewBox="0 0 500 280" style={{ width: '100%', height: '100%', position: 'absolute' }}>
      <path d="M18 185 C72 45 125 255 185 142 S300 58 478 178" stroke="#171615" strokeWidth="6" fill="none" strokeLinecap="round" strokeDasharray="16 13" className="knowledge-flow" />
      <path d="M18 220 C110 290 140 72 215 160 S325 252 478 108" stroke="#171615" strokeWidth="3.5" fill="none" strokeLinecap="round" strokeDasharray="3 14" className="knowledge-flow knowledge-flow-fast" />
      <path d="M340 145 C365 145 378 145 398 145" stroke="#171615" strokeWidth="5" fill="none" strokeLinecap="round" strokeDasharray="10 12" className="knowledge-flow" />
      <g fill="none" stroke="#171615" strokeWidth="4">
        <rect x="402" y="92" width="64" height="48" rx="8" transform="rotate(-5 434 116)" />
        <rect x="402" y="153" width="64" height="48" rx="8" transform="rotate(4 434 177)" />
      </g>
      <circle cx="185" cy="142" r="8" fill="#cf765f" stroke="#171615" strokeWidth="4" className="knowledge-pulse" />
      <circle cx="434" cy="116" r="5" fill="#cf765f" />
      <circle cx="434" cy="177" r="5" fill="#cf765f" />
      <style>{`
        @keyframes knowledgeFlow { to { stroke-dashoffset: -180; } }
        @keyframes knowledgePulse { 50% { transform: scale(1.5); opacity: .55; } }
        .knowledge-flow { animation: knowledgeFlow 8s linear infinite; }
        .knowledge-flow-fast { animation-duration: 5s; }
        .knowledge-pulse { transform-box: fill-box; transform-origin: center; animation: knowledgePulse 3s ease-in-out infinite; }
      `}</style>
    </svg>
  );

  // SVG动画 - 研究解读（左侧）- 抽象天文望远镜和闪烁星星
  const ResearchSVG = () => (
    <svg viewBox="0 0 500 280" style={{ width: '100%', height: '100%', position: 'absolute' }}>
      {/* 望远镜支架 */}
      <line
        x1="300"
        y1="200"
        x2="300"
        y2="140"
        stroke="#141413"
        strokeWidth="4.5"
        strokeLinecap="round"
        className="research-draw research-stand"
      />
      <line
        x1="280"
        y1="200"
        x2="320"
        y2="200"
        stroke="#141413"
        strokeWidth="5"
        strokeLinecap="round"
        className="research-draw research-base"
      />

      {/* 望远镜主体 - 圆柱形 */}
      <ellipse
        cx="240"
        cy="120"
        rx="80"
        ry="20"
        fill="none"
        stroke="#141413"
        strokeWidth="4.5"
        strokeLinecap="round"
        transform="rotate(-35 240 120)"
        className="research-draw research-telescope-body"
      />
      <line
        x1="300"
        y1="140"
        x2="180"
        y2="100"
        stroke="#141413"
        strokeWidth="4.5"
        strokeLinecap="round"
        className="research-draw research-telescope-tube"
      />

      {/* 望远镜镜头 */}
      <ellipse
        cx="180"
        cy="100"
        rx="15"
        ry="8"
        fill="none"
        stroke="#cf765f"
        strokeWidth="3.5"
        strokeLinecap="round"
        transform="rotate(-35 180 100)"
        className="research-draw research-lens"
      />

      {/* 目镜端 */}
      <circle
        cx="300"
        cy="140"
        r="10"
        fill="none"
        stroke="#cf765f"
        strokeWidth="3.5"
        strokeLinecap="round"
        className="research-draw research-eyepiece"
      />

      {/* 线性五角星 - 大 */}
      <path
        d="M 120 80 L 126 98 L 145 98 L 131 108 L 137 126 L 120 116 L 103 126 L 109 108 L 95 98 L 114 98 Z"
        fill="none"
        stroke="#e8a36b"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="research-star research-star-1"
      />

      {/* 线性五角星 - 中 */}
      <path
        d="M 380 100 L 384 112 L 397 112 L 387 120 L 391 132 L 380 124 L 369 132 L 373 120 L 363 112 L 376 112 Z"
        fill="none"
        stroke="#e8a36b"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="research-star research-star-2"
      />

      {/* 线性五角星 - 小 */}
      <path
        d="M 350 50 L 353 58 L 362 58 L 355 63 L 358 71 L 350 66 L 342 71 L 345 63 L 338 58 L 347 58 Z"
        fill="none"
        stroke="#e8a36b"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="research-star research-star-3"
      />

      {/* 线性五角星 - 小 */}
      <path
        d="M 140 50 L 143 58 L 152 58 L 145 63 L 148 71 L 140 66 L 132 71 L 135 63 L 128 58 L 137 58 Z"
        fill="none"
        stroke="#cf765f"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="research-star research-star-4"
      />

      {/* 线性五角星 - 微小装饰 */}
      <path
        d="M 200 60 L 202 66 L 208 66 L 203 70 L 205 76 L 200 72 L 195 76 L 197 70 L 192 66 L 198 66 Z"
        fill="none"
        stroke="#e8a36b"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="research-star research-star-5"
      />

      {/* 观测线 - 从望远镜到星星的连接 */}
      <line
        x1="180"
        y1="100"
        x2="120"
        y2="80"
        stroke="#141413"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeDasharray="4 4"
        opacity="0.5"
        className="research-draw research-sight-line"
      />

      {/* 小闪烁点 */}
      <circle cx="160" cy="70" r="2" fill="#e8a36b" className="research-twinkle research-twinkle-1" />
      <circle cx="320" cy="80" r="2.5" fill="#cf765f" className="research-twinkle research-twinkle-2" />
      <circle cx="400" cy="140" r="2" fill="#e8a36b" className="research-twinkle research-twinkle-3" />

      <style>
        {`
          @keyframes researchDraw {
            0% { stroke-dashoffset: 600; opacity: 0; }
            10% { opacity: 1; }
            90% { stroke-dashoffset: 0; opacity: 1; }
            100% { stroke-dashoffset: 0; opacity: 0; }
          }

          @keyframes researchStarTwinkle {
            0% { opacity: 0; transform: scale(0) rotate(0deg); }
            20% { opacity: 1; transform: scale(1) rotate(0deg); }
            40% { opacity: 0.6; transform: scale(1.1) rotate(72deg); }
            60% { opacity: 1; transform: scale(1) rotate(144deg); }
            80% { opacity: 0.7; transform: scale(1.05) rotate(216deg); }
            100% { opacity: 0; transform: scale(0) rotate(360deg); }
          }

          @keyframes researchPointTwinkle {
            0%, 100% { transform: scale(0); opacity: 0; }
            50% { transform: scale(1.8); opacity: 1; }
          }

          .research-draw {
            stroke-dasharray: 600;
            stroke-dashoffset: 600;
            animation: researchDraw 12s ease-in-out infinite;
          }

          .research-stand { animation-delay: 0s; }
          .research-base { animation-delay: 0.2s; }
          .research-telescope-tube { animation-delay: 0.5s; }
          .research-telescope-body { animation-delay: 0.7s; }
          .research-lens { animation-delay: 1s; }
          .research-eyepiece { animation-delay: 1.2s; }
          .research-sight-line { animation-delay: 1.5s; }

          .research-star {
            transform-box: fill-box;
            transform-origin: center;
            animation: researchStarTwinkle 12s ease-in-out infinite;
          }
          .research-star-1 { animation-delay: 2s; }
          .research-star-2 { animation-delay: 2.5s; }
          .research-star-3 { animation-delay: 3s; }
          .research-star-4 { animation-delay: 3.5s; }
          .research-star-5 { animation-delay: 4s; }

          .research-twinkle {
            transform-box: fill-box;
            transform-origin: center;
            animation: researchPointTwinkle 12s ease-in-out infinite;
          }
          .research-twinkle-1 { animation-delay: 4.5s; }
          .research-twinkle-2 { animation-delay: 5s; }
          .research-twinkle-3 { animation-delay: 5.5s; }
        `}
      </style>
    </svg>
  );

  return (
    <Container maxWidth="lg" sx={{ py: 6 }}>
      {/* Banner Section */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: svgPosition === 'left'
            ? { xs: '1fr', md: '0.85fr 1.15fr' }
            : { xs: '1fr', md: '1.15fr 0.85fr' },
          gap: { xs: 3, md: 6 },
          alignItems: 'center',
          py: '22px',
          mb: 5,
        }}
      >
        {svgPosition === 'left' && (
          <Box
            sx={{
              minHeight: { xs: '180px', md: '240px' },
              borderRadius: '28px',
              background: 'primary.main',
              position: 'relative',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              order: { xs: 2, md: 1 },
            }}
          >
            <ResearchSVG />
          </Box>
        )}

        <Box sx={{
          order: svgPosition === 'left' ? { xs: 1, md: 2 } : 1,
          textAlign: svgPosition === 'left' ? { xs: 'left', md: 'right' } : 'left'
        }}>
          <Typography
            sx={{
              fontSize: '13px',
              color: 'primary.main',
              letterSpacing: '0.14em',
              fontWeight: 600,
              mb: 2,
            }}
          >
            {eyebrow}
          </Typography>
          <Typography
            variant="h1"
            component="h1"
            sx={{
              fontSize: { xs: '48px', md: '72px' },
              lineHeight: 1.1,
              letterSpacing: '-0.05em',
              fontWeight: 500,
              mb: 2.5,
            }}
          >
            {title}
          </Typography>
          <Typography
            sx={{
              color: 'text.secondary',
              fontSize: '17px',
              lineHeight: 1.75,
              maxWidth: '520px',
              marginLeft: svgPosition === 'left' ? { xs: 0, md: 'auto' } : 0,
            }}
          >
            {description}
          </Typography>
        </Box>

        {svgPosition === 'right' && (
          <Box
            sx={{
              minHeight: { xs: '180px', md: '240px' },
              borderRadius: '28px',
              background: 'transparent',
              position: 'relative',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              order: 2,
            }}
          >
            <ProjectSVG />
          </Box>
        )}
      </Box>

      {/* Category Filter */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Chip
            label="全部"
            onClick={() => handleCategoryClick(undefined)}
            color={selectedCategory === undefined ? 'primary' : 'default'}
            sx={{ cursor: 'pointer', '& .MuiChip-label': { fontSize: '15.5px' } }}
          />
          {categories.map((category) => (
            <Chip
              key={category.id}
              label={category.name}
              onClick={() => handleCategoryClick(category.id)}
              color={selectedCategory === category.id ? 'primary' : 'default'}
              sx={{ cursor: 'pointer', '& .MuiChip-label': { fontSize: '15.5px' } }}
            />
          ))}
        </Box>
      </Box>

      {/* Articles Grid */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      ) : articles.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <Typography variant="h6" color="text.secondary">
            暂无文章
          </Typography>
        </Box>
      ) : (
        <>
          <Grid container spacing={3}>
            {articles.map((article) => (
              <Grid size={{ xs: 12, sm: 6, md: 4 }} key={article.id}>
                <ArticleCard article={article} />
              </Grid>
            ))}
          </Grid>

          {/* Pagination */}
          {totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={handlePageChange}
                color="primary"
                size="large"
              />
            </Box>
          )}
        </>
      )}
    </Container>
  );
};

export default ArticleList;
