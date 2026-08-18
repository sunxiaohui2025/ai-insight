import SwiftUI
import WebKit

struct ReaderView: View {
    let article: ArticleDetailResponse
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @State private var selectedTab = 0  // 0 = 正文, 1 = 一页纸
    @State private var fontSize: CGFloat = 16
    @State private var contentHeight: CGFloat = 320

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Picker("视图", selection: $selectedTab) {
                    Text("正文").tag(0)
                    Text("一页纸").tag(1)
                }
                .pickerStyle(.segmented)
                .frame(width: 180)

                Spacer()

                Menu {
                    Button { fontSize = max(14, fontSize - 2) } label: { Label("缩小", systemImage: "textformat.size.smaller") }
                    Button { fontSize = min(24, fontSize + 2) } label: { Label("放大", systemImage: "textformat.size.larger") }
                    Button { fontSize = 16 } label: { Label("默认", systemImage: "textformat.size") }
                } label: {
                    Image(systemName: "textformat.size").font(.title3)
                }

                if let url = URL(string: article.url) {
                    Button { openURL(url) } label: { Image(systemName: "safari").font(.title3) }
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 8)
            .background(.regularMaterial)

            // Content
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text(article.title)
                        .font(.system(size: 22, weight: .bold, design: .serif))
                        .padding(.horizontal, 16).padding(.top, 16)

                    // Source info
                    HStack(spacing: 8) {
                        Text(article.categoryIcon)
                        Text(article.categoryName).font(.caption)
                        Text("·").foregroundStyle(.secondary)
                        Text(article.sourceDomain).font(.caption)
                        Text("·").foregroundStyle(.secondary)
                        Text("\(article.wordCount) 词").font(.caption)
                    }
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 16)

                    Divider().padding(.horizontal, 16)

                    if selectedTab == 0 {
                        HTMLContentView(html: markdownToHTML(article.translatedContent), fontSize: fontSize, contentHeight: $contentHeight)
                            .frame(height: contentHeight)
                            .padding(.horizontal, 16)
                    } else {
                        if article.onePageSummary.isEmpty {
                            Text("暂无一页纸解读").font(.system(size: fontSize))
                        } else {
                            HTMLContentView(html: article.onePageSummary, fontSize: fontSize, contentHeight: $contentHeight)
                                .frame(height: contentHeight)
                        }
                    }
                }
                .padding(.bottom, 40)
            }
        }
        .background(AppTheme.canvas)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) { Button("关闭") { dismiss() } }
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: 16) {
                    Button {
                        Task { await toggleStarred() }
                    } label: {
                        Image(systemName: article.isStarred ? "star.fill" : "star").foregroundStyle(article.isStarred ? .yellow : .secondary)
                    }
                }
            }
        }
    }

    private func toggleStarred() async {
        struct ToggleBody: Encodable { let isStarred: Bool }
        do {
            let _: EmptyResponse = try await CloudAPI.request(
                "/api/v1/insight/articles/\(article.id)",
                method: "PATCH",
                bodyData: JSONEncoder.cloud.encode(UpdateArticleBody(categoryId: nil, isRead: nil, isStarred: !article.isStarred)),
                authenticated: true
            )
        } catch {}
    }
}

private struct EmptyResponse: Decodable {}
