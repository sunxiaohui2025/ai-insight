"""
Blog public API routes - 博客前端公开 API
这个文件包含前端博客系统需要的公开 API 端点
"""

def register_blog_routes(app):
    """注册博客相关的公开 API 路由"""
    
    # 这些路由已经在 main.py 中实现：
    # GET /api/v1/content/articles - 获取文章列表（公开）
    # GET /api/v1/content/sections - 获取板块列表
    # GET /api/v1/content/sections/{section_id}/categories-tree - 获取分类树
    
    # 需要添加的额外路由：
    
    @app.get("/api/v1/blog/articles")
    def get_blog_articles(
        section_id: int = None,
        category_id: int = None, 
        search: str = None,
        page: int = 1,
        limit: int = 20
    ):
        """公开的文章列表 API（映射到 /api/v1/content/articles）"""
        from fastapi import Request
        # 这个可以直接调用已有的 list_content_articles
        pass
    
    @app.get("/api/v1/blog/articles/{id}")
    def get_blog_article_detail(id: int):
        """公开的文章详情 API"""
        pass
    
    @app.get("/api/v1/blog/sections")
    def get_blog_sections():
        """获取板块列表（映射到 /api/v1/content/sections）"""
        pass
    
    @app.get("/api/v1/blog/categories")
    def get_blog_categories(section_id: int = None):
        """获取分类列表"""
        pass
    
    @app.get("/api/v1/blog/featured")
    def get_featured_articles():
        """获取精选文章"""
        pass
    
    @app.get("/api/v1/blog/latest")
    def get_latest_articles(limit: int = 10):
        """获取最新文章"""
        pass
