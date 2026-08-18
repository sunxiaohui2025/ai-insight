import SwiftData
import SwiftUI
import WebKit

struct HomeView: View {
    @Environment(\.modelContext) private var context
    @EnvironmentObject private var auth: AuthState
    @State private var categories: [CategoryResponse] = []
    @State private var recentArticles: [ContentArticleResponse] = []
    @State private var stats = InsightStats(total: 0, unread: 0, starred: 0, processing: 0)
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var showReader: ContentArticleDetail?
    @State private var searchText = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // 整合成一个 Banner：无背景框，背景即页面背景，右侧为手绘 SVG 动画
                    VStack(alignment: .leading, spacing: 6) {
                        Text(Date.now.formatted(.dateTime.month().day().weekday(.wide)))
                            .font(.subheadline.weight(.semibold)).foregroundStyle(AppTheme.terracottaDark)
                        HStack(alignment: .top, spacing: 14) {
                            VStack(alignment: .leading, spacing: 7) {
                                Text("深度收藏").font(.system(size: 34, weight: .bold, design: .rounded))
                                Text("从收藏到解读，持续积累你的知识库").font(.subheadline).foregroundStyle(.secondary)
                                if let user = auth.user {
                                    Text("\(user.name)，发现更多洞察").font(.subheadline).foregroundStyle(.secondary)
                                }
                            }
                            Spacer(minLength: 8)
                            HomeBannerArt().frame(width: 142, height: 142)
                        }
                    }

                    // 最新文章
                    if !recentArticles.isEmpty {
                        Text("最新文章").font(.headline)
                        ForEach(recentArticles) { article in
                            Button {
                                Task { await openArticle(id: article.id) }
                            } label: {
                                HomeArticleCard(article: article)
                            }
                        }
                    }

                    if let error = errorMessage {
                        Text(error).font(.caption).foregroundStyle(.red)
                    }
                }.padding(.horizontal, 18).padding(.top, 14).padding(.bottom, 24)
            }
            .pageBackground()
            .navigationBarHidden(true)
            .refreshable { await loadData() }
            .fullScreenCover(item: $showReader) { article in
                NavigationStack { ContentReaderView(article: article) }
            }
        }
        .task { await loadData() }
    }

    private func loadData() async {
        isLoading = true; errorMessage = nil
        do {
            async let list: ContentArticlesList = CloudAPI.get("/api/v1/content/articles?page=1&page_size=30")
            let loadedList = try await list
            recentArticles = loadedList.articles
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    private func openArticle(id: Int) async {
        do {
            let detail: ContentArticleDetail = try await CloudAPI.get("/api/v1/content/articles/\(id)")
            showReader = detail
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func searchArticles() async {
        guard !searchText.isEmpty else { await loadData(); return }
        do {
            let encoded = searchText.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? searchText
            let list: ContentArticlesList = try await CloudAPI.get("/api/v1/content/articles?search=\(encoded)&page_size=30")
            recentArticles = list.articles
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func statCard(_ title: String, _ value: Int, _ icon: String, _ color: Color) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: icon).font(.caption.bold()).frame(width: 27, height: 27).foregroundStyle(color).background(color.opacity(0.12), in: Circle())
            Text("\(value)").font(.system(size: 25, weight: .bold, design: .rounded))
            Text(title).font(.caption).foregroundStyle(.secondary)
        }.frame(maxWidth: .infinity, alignment: .leading).padding(13)
            .background(.white, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppTheme.line))
    }
}

private struct HomeArticleCard: View {
    let article: ContentArticleResponse
    var body: some View { VStack(alignment: .leading, spacing: 0) {
        ZStack { Rectangle().fill(AppTheme.terracotta.opacity(0.12)); if let url = cloudMediaURL(article.bannerUrl) { BannerImage(url: url) } }.frame(height: 170).clipped()
        VStack(alignment: .leading, spacing: 9) {
            Text(article.title).font(.system(size: 18, weight: .semibold)).lineSpacing(4).multilineTextAlignment(.leading).lineLimit(2)
            Text(article.subtitle.isEmpty ? article.excerpt : article.subtitle).font(.system(size: 15)).lineSpacing(5).foregroundStyle(.secondary).multilineTextAlignment(.leading).lineLimit(2)
            ArticleMetaTags(category: article.categoryName.isEmpty ? article.sectionName : article.categoryName,
                            author: article.authorName,
                            createdAt: article.createdAt)
        }.padding(16)
    }.background(.white, in: RoundedRectangle(cornerRadius: 16)).clipShape(RoundedRectangle(cornerRadius: 16)).overlay(RoundedRectangle(cornerRadius: 16).stroke(AppTheme.line)) }
}

func formatRelative(_ iso: String) -> String {
    let fmt = ISO8601DateFormatter()
    fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    let std = ISO8601DateFormatter()
    std.formatOptions = [.withInternetDateTime]
    guard let date = fmt.date(from: iso) ?? std.date(from: iso) else { return iso }
    let diff = Date().timeIntervalSince(date)
    if diff < 3600 { return "\(Int(diff / 60))分钟前" }
    if diff < 86400 { return "\(Int(diff / 3600))小时前" }
    if diff < 604800 { return "\(Int(diff / 86400))天前" }
    return date.formatted(.dateTime.month(.abbreviated).day())
}

/// 首页 Banner 插画：Claude 风格的手绘 SVG 动画（意识流、线稿、柔色调）
struct HomeBannerArt: UIViewRepresentable {
    func makeUIView(context: Context) -> WKWebView {
        let view = WKWebView()
        view.isOpaque = false
        view.backgroundColor = .clear
        view.scrollView.isScrollEnabled = false
        view.isUserInteractionEnabled = false
        view.loadHTMLString(HomeBannerArt.svg, baseURL: nil)
        return view
    }
    func updateUIView(_ view: WKWebView, context: Context) {}

    static let svg = #"""
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="margin:0;background:transparent">
    <svg viewBox="0 0 300 300" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <style>
          @keyframes draw { 0%{stroke-dashoffset:560} 100%{stroke-dashoffset:0} }
          @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-9px)} }
          @keyframes nudge { 0%,100%{transform:translate(0,0)} 50%{transform:translate(4px,-6px)} }
          @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
          @keyframes breathe { 0%,100%{opacity:.32} 50%{opacity:.58} }
          .draw{stroke-dasharray:560;animation:draw 3.4s ease forwards}
          .f{animation:float 6s ease-in-out infinite}
          .n{animation:nudge 7s ease-in-out infinite}
          .sp{transform-box:fill-box;transform-origin:center;animation:spin 28s linear infinite}
          .br{animation:breathe 5s ease-in-out infinite}
        </style>
      </defs>

      <!-- 柔和色块（页面背景自然透出，无需背景框） -->
      <circle cx="88" cy="76" r="48" fill="#E9B891" opacity=".26" class="br"/>
      <circle cx="222" cy="212" r="56" fill="#B7C9B0" opacity=".28" class="br"/>

      <!-- 手绘大圆环 + 虚线外环 -->
      <g class="sp">
        <circle cx="150" cy="150" r="112" fill="none" stroke="#C85A2F" stroke-width="2.4" stroke-linecap="round" opacity=".85" class="draw"/>
        <circle cx="150" cy="150" r="132" fill="none" stroke="#7E9C86" stroke-width="1.4" stroke-dasharray="2 9" stroke-linecap="round"/>
      </g>

      <!-- 手绘书卷核心 -->
      <g class="f">
        <path d="M118 122 q26 -24 32 0 q-4 22 -16 26 q-20 -8 -16 -26z" fill="none" stroke="#C85A2F" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" class="draw"/>
        <path d="M124 130 q26 -12 22 12 M124 130 q18 8 30 0" fill="none" stroke="#7E9C86" stroke-width="1.8" stroke-linecap="round"/>
      </g>

      <!-- 思绪的笔触曲线 -->
      <g class="f" opacity=".82">
        <path d="M64 62 q20 12 6 30 M246 78 q-18 10 -8 28 M52 198 q24 -2 18 -22 M248 228 q-16 8 -4 24" fill="none" stroke="#C85A2F" stroke-width="1.8" stroke-linecap="round"/>
      </g>

      <!-- 手绘小星星 -->
      <g class="n">
        <path d="M258 32 l2 7 7 2 -7 2 -2 7 -2 -7 -7 -2 7 -2z" fill="#E8B48F"/>
        <path d="M40 252 l2 7 7 2 -7 2 -2 7 -2 -7 -7 -2 7 -2z" fill="#7E9C86"/>
      </g>
    </svg>
    </body></html>
    """#
}
