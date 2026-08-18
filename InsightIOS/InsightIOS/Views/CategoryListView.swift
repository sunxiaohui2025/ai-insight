import SwiftUI
import WebKit
import PDFKit

struct CategoryListView: View {
    let contentSectionId: Int?; let contentCategoryId: Int?; let categoryName: String
    @State private var articles: [ContentArticleResponse] = []
    @State private var showReader: ContentArticleDetail?
    @State private var errorMessage: String?

    var body: some View {
        LazyVStack(spacing: 12) {
            ForEach(articles) { article in
                Button { Task { await open(article.id) } } label: { ContentArticleCard(article: article) }
                    .buttonStyle(.plain)
            }
            if articles.isEmpty { Text("暂无文章").font(.caption).foregroundStyle(.secondary).padding(.vertical, 30) }
            if let errorMessage { Text(errorMessage).font(.caption).foregroundStyle(.red).padding(.vertical, 12) }
        }
        .fullScreenCover(item: $showReader) { article in NavigationStack { ContentReaderView(article: article) } }
        .task(id: "\(contentSectionId ?? 0)-\(contentCategoryId ?? 0)") { await load() }
    }
    private func load() async {
        var path = "/api/v1/content/articles?page=1&page_size=30"
        if let id = contentSectionId { path += "&section_id=\(id)" }; if let id = contentCategoryId { path += "&sub_category_id=\(id)" }
        do { let result: ContentArticlesList = try await CloudAPI.get(path); articles = result.articles } catch { errorMessage = error.localizedDescription }
    }
    private func open(_ id: Int) async { showReader = try? await CloudAPI.get("/api/v1/content/articles/\(id)") }
}

private struct ContentArticleCard: View {
    let article: ContentArticleResponse
    var body: some View { VStack(alignment: .leading, spacing: 0) {
        ZStack { Rectangle().fill(AppTheme.terracotta.opacity(0.12));
            if let url = cloudMediaURL(article.bannerUrl) { BannerImage(url: url) }
        }.frame(height: 170).clipped()
        VStack(alignment: .leading, spacing: 9) {
            Text(article.title).font(.system(size: 18, weight: .semibold)).lineSpacing(4).foregroundStyle(AppTheme.ink).multilineTextAlignment(.leading).lineLimit(2)
            Text(article.subtitle.isEmpty ? article.excerpt : article.subtitle).font(.system(size: 15)).lineSpacing(5).foregroundStyle(.secondary).multilineTextAlignment(.leading).lineLimit(2)
            ArticleMetaTags(category: article.categoryName.isEmpty ? article.sectionName : article.categoryName,
                            author: article.authorName,
                            createdAt: article.createdAt)
        }.padding(16)
    }.frame(maxWidth: .infinity, alignment: .leading).background(.white, in: RoundedRectangle(cornerRadius: 16)).clipShape(RoundedRectangle(cornerRadius: 16)).overlay(RoundedRectangle(cornerRadius: 16).stroke(AppTheme.line)) }
}

/// 文章卡片底部元数据标签（分类 / 作者 / 时间），圆角边框样式，时间标签靠右端对齐
struct ArticleMetaTags: View {
    let category: String
    let author: String
    let createdAt: String
    var body: some View {
        HStack(alignment: .center, spacing: 6) {
            if !category.isEmpty { MetaTag(text: category) }
            if !author.isEmpty { MetaTag(text: author) }
            Spacer(minLength: 8)
            MetaTag(text: formatRelative(createdAt))
        }.padding(.top, 1)
    }
}

/// 单个圆角边框标签
struct MetaTag: View {
    let text: String
    var body: some View {
        Text(text)
            .font(.caption2)
            .foregroundStyle(AppTheme.mutedInk)
            .lineLimit(1)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(AppTheme.blush.opacity(0.35), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 6, style: .continuous).stroke(AppTheme.line))
    }
}

struct BannerImage: UIViewRepresentable {
    let url: URL
    func makeUIView(context: Context) -> WKWebView { let view = WKWebView(); view.isOpaque = false; view.backgroundColor = .clear; view.scrollView.isScrollEnabled = false; return view }
    func updateUIView(_ view: WKWebView, context: Context) {
        var request = URLRequest(url: url); request.cachePolicy = .returnCacheDataElseLoad
        view.load(request)
    }
}

struct ContentReaderView: View {
    let article: ContentArticleDetail; @Environment(\.dismiss) private var dismiss
    @State private var selectedTab = 0  // 0 = 正文, 1 = 一页纸
    @State private var contentHeight: CGFloat = 500
    @State private var horizontalOffset: CGFloat = 0
    var body: some View { ScrollView { VStack(alignment: .leading, spacing: 0) {
        // 顶部 banner（压低高度、贴近封面图，减少下方留白）
        ZStack {
            Rectangle().fill(AppTheme.terracotta.opacity(0.12))
            if let url = cloudMediaURL(article.bannerUrl) { BannerImage(url: url) }
            else {
                LinearGradient(colors: [AppTheme.terracotta.opacity(0.25), AppTheme.sage.opacity(0.16)], startPoint: .topLeading, endPoint: .bottomTrailing)
            }
        }.frame(height: 150).clipped()
        // 标题区（收敛展示：banner → 标题 → 一句话副题 → 单行元信息）
        VStack(alignment: .leading, spacing: 10) {
            Text(article.title).font(.title.bold()).lineSpacing(3)
            if !article.subtitle.isEmpty { Text(article.subtitle).font(.subheadline).foregroundStyle(.secondary).lineSpacing(3) }
            HStack(spacing: 5) {
                Text(article.sectionName)
                if !article.categoryName.isEmpty { Text("·"); Text(article.categoryName) }
                if !article.authorName.isEmpty { Text("·"); Text(article.authorName) }
            }.font(.caption).foregroundStyle(.secondary)
            Divider().padding(.top, 2)
        }
        .padding(.horizontal, 18).padding(.top, 16).padding(.bottom, 8)

        // 视图切换：正文 / 一页纸
        if hasSummary {
            Picker("视图", selection: $selectedTab) {
                Text("正文").tag(0)
                Text("一页纸").tag(1)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 18).padding(.bottom, 8)
        }

        if selectedTab == 0 {
            // 正文：PDF / 整页 HTML / 行内 richtext 分情况渲染
            Group {
                if article.contentFormat == "document" && article.docKind == "pdf", let url = cloudMediaURL(article.attachmentUrl) {
                    PDFDocumentView(url: url).frame(height: contentHeight).onAppear { contentHeight = 900 }
                } else if article.contentFormat == "html" {
                    // 整页 HTML（如链接解析出来的完整网页）：独立全宽渲染，
                    // 不再被外层 padding 收缩，避免内容变窄、两边大留白。
                    FullPageHTMLView(html: readerRawHTML, contentHeight: $contentHeight)
                        .frame(height: contentHeight)
                        .frame(maxWidth: .infinity)
                } else {
                    HTMLContentView(html: readerHTML, fontSize: 17, contentHeight: $contentHeight)
                        .frame(height: contentHeight)
                        .padding(.horizontal, 18)
                }
            }
        } else {
            // 一页纸解读（summary_content / one_page_summary）
            Group {
                if article.contentFormat == "html" {
                    FullPageHTMLView(html: summaryRaw, contentHeight: $contentHeight)
                        .frame(height: contentHeight)
                        .frame(maxWidth: .infinity)
                } else {
                    HTMLContentView(html: summaryHTML, fontSize: 16, contentHeight: $contentHeight)
                        .frame(height: contentHeight)
                        .padding(.horizontal, 18)
                }
            }
        }
    } }
    .pageBackground()
    .navigationTitle("详情")
    .navigationBarTitleDisplayMode(.inline)
    .toolbar { ToolbarItem(placement: .navigationBarLeading) { Button("关闭") { dismiss() } } }
    .offset(x: horizontalOffset)
    .gesture(DragGesture(minimumDistance: 20)
        .onChanged { value in
            if abs(value.translation.width) > abs(value.translation.height) { horizontalOffset = value.translation.width }
        }
        .onEnded { value in
            guard abs(value.translation.width) > abs(value.translation.height) else { withAnimation(.spring()) { horizontalOffset = 0 }; return }
            if abs(value.translation.width) > 90 {
                withAnimation(.easeOut(duration: 0.2)) { horizontalOffset = value.translation.width > 0 ? 500 : -500 }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) { dismiss() }
            } else { withAnimation(.spring()) { horizontalOffset = 0 } }
        })
    }
}

struct PDFDocumentView: UIViewRepresentable {
    let url: URL
    func makeUIView(context: Context) -> PDFView { let view = PDFView(); view.autoScales = true; view.displayMode = .singlePageContinuous; view.displayDirection = .vertical; return view }
    func updateUIView(_ view: PDFView, context: Context) { if view.document == nil { view.document = PDFDocument(url: url) } }
}

/// Renders a COMPLETE HTML document (a full <html> page, e.g. the content parsed
/// from a web link) standalone and edge-to-edge. The article's own HTML + CSS is
/// loaded as-is (not nested inside another body), so it keeps its intended layout,
/// fills the full screen width, and avoids looking squeezed/narrow.
struct FullPageHTMLView: UIViewRepresentable {
    let html: String
    @Binding var contentHeight: CGFloat

    final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: FullPageHTMLView
        init(parent: FullPageHTMLView) { self.parent = parent }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            webView.evaluateJavaScript("document.documentElement.scrollHeight") { value, _ in
                guard let height = value as? CGFloat else { return }
                DispatchQueue.main.async { self.parent.contentHeight = max(120, height + 8) }
            }
        }
    }
    func makeCoordinator() -> Coordinator { Coordinator(parent: self) }
    func makeUIView(context: Context) -> WKWebView {
        let view = WKWebView()
        view.isOpaque = false
        view.backgroundColor = .clear
        view.scrollView.backgroundColor = .clear
        view.scrollView.isScrollEnabled = false
        view.scrollView.bounces = false
        view.scrollView.showsVerticalScrollIndicator = false
        view.navigationDelegate = context.coordinator
        return view
    }
    func updateUIView(_ view: WKWebView, context: Context) {
        // baseURL lets relative /media/... images from the server resolve correctly.
        view.loadHTMLString(html, baseURL: URL(string: CloudConfiguration.baseURL))
    }
}

extension ContentReaderView {
    /// The editor stores ALL published content (manual, link/URL) in manual_content.
    /// Link/URL articles leave original/translated empty, so prefer the first
    /// non-empty field. manual_content is saved HTML (richtext/html); the URL-parsing
    /// fields are plain text and must be converted to HTML to preserve paragraphs.
    private var rawContent: String {
        !article.manualContent.isEmpty ? article.manualContent
            : (!article.translatedContent.isEmpty ? article.translatedContent : article.originalContent)
    }
    /// Content used for inline richtext / plain-text rendering.
    private var readerHTML: String {
        if !article.manualContent.isEmpty && (article.contentFormat == "richtext" || article.contentFormat == "html") {
            return rawContent
        }
        return markdownToHTML(rawContent)
    }
    /// The untouched document used by the full-page standalone renderer.
    private var readerRawHTML: String { rawContent }

    /// Whether the article has a published one-page analysis (一页纸解读).
    private var hasSummary: Bool { !article.summaryContent.isEmpty || !article.onePageSummary.isEmpty }

    /// Content articles store the one-page analysis in summary_content (HTML);
    /// personal/legacy articles may use one_page_summary. Prefer the non-empty one.
    private var summaryRaw: String {
        !article.summaryContent.isEmpty ? article.summaryContent : article.onePageSummary
    }

    /// One-page analysis as inline HTML (for richtext / non-html formats).
    private var summaryHTML: String {
        summaryRaw.contains("<") ? summaryRaw : markdownToHTML(summaryRaw)
    }
}
