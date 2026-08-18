import SwiftUI
import UIKit
import WebKit

/// 「解读」：把网页链接交给后端 url-to-article 技能提取，
/// 得到 HTML 正文、一页纸解读与 1~2 张候选 banner，再由用户自选 banner 与分类后发布。
struct DecodeView: View {
    @State private var urlInput = ""
    @State private var sections: [ContentSection] = []
    @State private var selectedSectionId: Int? = nil
    @State private var categoryTree: [ContentCategoryNode] = []
    @State private var selectedCategoryId: Int? = nil

    @State private var isLoading = false
    @State private var loadingStage = 0
    @State private var errorMessage: String?
    @State private var jobResult: DecodeJobResult?
    @State private var isPublishing = false
    @State private var publishMessage: String?
    @State private var editableTitle = ""
    @State private var editableSubtitle = ""
    @State private var selectedBannerURL: String?

    @State private var jobId: String?
    @State private var resultTab = 0  // 0=正文, 1=一页纸
    @State private var fontSize: CGFloat = 16
    @State private var contentHeight: CGFloat = 360

    // 发布成功弹窗
    @State private var showPublishSuccess = false
    @State private var publishAlertTitle = "发布成功"
    @State private var publishAlertMessage = ""

    @FocusState private var isUrlFocused: Bool
    @FocusState private var isTitleFocused: Bool

    let loadingStages = ["正在提取网页内容...", "正在生成正文与一页纸解读...", "正在生成候选 banner 图..."]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    // Header
                    VStack(alignment: .leading, spacing: 6) {
                        Text("链接解读").font(.system(size: 28, weight: .bold, design: .rounded))
                        Text("粘贴网页链接，AI 提取正文、生成一页纸解读，选择 banner 与分类后发布")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }.padding(.top, 8)

                    // URL Input
                    VStack(alignment: .leading, spacing: 8) {
                        Text("网页链接").font(.subheadline.weight(.medium))
                        HStack {
                            Image(systemName: "link").foregroundStyle(.secondary)
                            TextField("https://...", text: $urlInput)
                                .textContentType(.URL)
                                .keyboardType(.URL)
                                .autocapitalization(.none)
                                .disableAutocorrection(true)
                                .focused($isUrlFocused)
                                .submitLabel(.go)
                                .onSubmit { Task { await startDecode() } }
                            if !urlInput.isEmpty {
                                Button { urlInput = "" } label: {
                                    Image(systemName: "xmark.circle.fill")
                                        .foregroundStyle(.secondary)
                                }
                            }
                        }
                        .padding(12).background(.white, in: RoundedRectangle(cornerRadius: 12))
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(AppTheme.line))
                    }

                    // Action Button
                    Button {
                        Task { await startDecode() }
                    } label: {
                        HStack(spacing: 8) {
                            if isLoading {
                                ProgressView().tint(.white)
                            } else {
                                Image(systemName: "text.viewfinder")
                            }
                            Text(isLoading ? loadingStages[min(loadingStage, loadingStages.count - 1)] : "开始解读")
                        }
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .frame(height: 54)
                        .foregroundStyle(.white)
                        .background(
                            (urlInput.trimmingCharacters(in: .whitespaces).isEmpty || isLoading)
                                ? AppTheme.terracotta.opacity(0.4)
                                : AppTheme.terracotta,
                            in: RoundedRectangle(cornerRadius: 13, style: .continuous)
                        )
                    }
                    .disabled(urlInput.trimmingCharacters(in: .whitespaces).isEmpty || isLoading)

                    // Loading animation
                    if isLoading {
                        VStack(spacing: 20) {
                            HStack(spacing: 6) {
                                ForEach(0..<3) { i in
                                    Circle()
                                        .fill(AppTheme.terracotta.opacity(0.6))
                                        .frame(width: 8, height: 8)
                                        .scaleEffect(pulsingDots ? 1.3 : 0.7)
                                        .animation(
                                            .easeInOut(duration: 0.8)
                                            .repeatForever(autoreverses: true)
                                            .delay(Double(i) * 0.2),
                                            value: pulsingDots
                                        )
                                }
                            }
                            VStack(spacing: 12) {
                                ForEach(Array(loadingStages.enumerated()), id: \.offset) { index, stage in
                                    HStack(spacing: 12) {
                                        ZStack {
                                            if index < loadingStage {
                                                Image(systemName: "checkmark.circle.fill")
                                                    .foregroundStyle(AppTheme.sage)
                                            } else if index == loadingStage {
                                                ProgressView().scaleEffect(0.8)
                                            } else {
                                                Circle()
                                                    .stroke(AppTheme.line, lineWidth: 2)
                                                    .frame(width: 22, height: 22)
                                            }
                                        }
                                        .frame(width: 24, height: 24)
                                        Text(stage)
                                            .font(.subheadline)
                                            .foregroundStyle(index <= loadingStage ? AppTheme.ink : .secondary)
                                            .opacity(index < loadingStage ? 0.6 : 1)
                                        Spacer()
                                    }
                                }
                            }
                            .padding(20)
                            .background(.white, in: RoundedRectangle(cornerRadius: 14))
                            .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppTheme.line))
                        }
                        .padding(.top, 4)
                    }

                    // Error
                    if let error = errorMessage {
                        HStack(spacing: 8) {
                            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
                            Text(error).font(.subheadline)
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(.orange.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
                    }

                    // Publish success
                    if let msg = publishMessage {
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark.circle.fill").foregroundStyle(AppTheme.sage)
                            Text(msg).font(.subheadline)
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(AppTheme.sage.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
                    }

                    // Result: 预览 + 发布
                    if let result = jobResult {
                        publishSection(result: result)
                    }

                    // Tips (only when idle)
                    if jobResult == nil && !isLoading && publishMessage == nil {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("解读流程").font(.subheadline.weight(.medium)).foregroundStyle(.secondary)
                            VStack(alignment: .leading, spacing: 6) {
                                tip(icon: "1.circle.fill", text: "粘贴网页链接（支持中英文网站）")
                                tip(icon: "2.circle.fill", text: "交给 url-to-article 技能提取正文与一页纸解读")
                                tip(icon: "3.circle.fill", text: "英文内容自动翻译为中文")
                                tip(icon: "4.circle.fill", text: "AI 生成候选 banner 图，并提取标题与副标题")
                                tip(icon: "5.circle.fill", text: "选择 banner 与分类后发布为文章")
                            }
                        }
                        .padding(14)
                        .background(.white.opacity(0.6), in: RoundedRectangle(cornerRadius: 12))
                    }
                }
                .padding(.horizontal, 18).padding(.bottom, 40)
            }
            .pageBackground()
            .navigationBarHidden(true)
        }
        .task { await loadSections() }
        .onChange(of: selectedSectionId) { _, newID in
            guard let newID else { categoryTree = []; selectedCategoryId = nil; return }
            Task { await loadCategories(for: newID) }
        }
        .alert(publishAlertTitle, isPresented: $showPublishSuccess) {
            Button("好的", role: .cancel) {}
        } message: {
            Text(publishAlertMessage)
        }
    }

    @State private var pulsingDots = false

    // MARK: - 结果与发布区

    @ViewBuilder
    private func publishSection(result: DecodeJobResult) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Divider()

            Text("解读完成 · 选择 banner 与分类发布")
                .font(.title3.weight(.bold))

            // Banner selection
            if !result.banners.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("选择 banner 图（\(result.banners.count) 张候选）")
                        .font(.subheadline.weight(.medium))
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 12) {
                            ForEach(result.banners) { banner in
                                Button {
                                    selectedBannerURL = banner.url
                                } label: {
                                    AsyncImage(url: cloudMediaURL(banner.url)) { phase in
                                        switch phase {
                                        case .success(let image):
                                            image.resizable().scaledToFill()
                                        case .failure:
                                            Rectangle().fill(AppTheme.line)
                                                .overlay(Image(systemName: "photo").foregroundStyle(.secondary))
                                        default:
                                            Rectangle().fill(AppTheme.line)
                                                .overlay(ProgressView())
                                        }
                                    }
                                    .frame(width: 240, height: 135)
                                    .clipShape(RoundedRectangle(cornerRadius: 12))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 12)
                                            .stroke(selectedBannerURL == banner.url ? AppTheme.terracotta : .clear, lineWidth: 3)
                                    )
                                    .overlay(alignment: .topTrailing) {
                                        if selectedBannerURL == banner.url {
                                            Image(systemName: "checkmark.circle.fill")
                                                .foregroundStyle(.white, AppTheme.terracotta)
                                                .padding(6)
                                        }
                                    }
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            } else {
                HStack {
                    Image(systemName: "photo").foregroundStyle(.secondary)
                    Text("本链接未能从原文提取到配图，将使用默认封面色块").font(.caption).foregroundStyle(.secondary)
                }
            }

            // Title & subtitle
            VStack(alignment: .leading, spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("标题（不少于 10 字）").font(.subheadline.weight(.medium))
                        Spacer()
                        Text("\(editableTitle.count)/\(max(10, result.metadataMeta?.titleMin ?? 10))")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                    TextField("文章标题", text: $editableTitle, axis: .vertical)
                        .lineLimit(1...3)
                        .focused($isTitleFocused)
                        .padding(12).background(.white, in: RoundedRectangle(cornerRadius: 10))
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.line))
                }
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("副标题（不少于 50 字）").font(.subheadline.weight(.medium))
                        Spacer()
                        Text("\(editableSubtitle.count)/\(max(50, result.metadataMeta?.subtitleMin ?? 50))")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                    TextField("副标题", text: $editableSubtitle, axis: .vertical)
                        .lineLimit(3...6)
                        .padding(12).background(.white, in: RoundedRectangle(cornerRadius: 10))
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.line))
                }
            }

            // Section & category
            VStack(alignment: .leading, spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("发布板块").font(.subheadline.weight(.medium))
                    Picker("发布板块", selection: $selectedSectionId) {
                        Text("请选择").tag(nil as Int?)
                        ForEach(sections) { s in Text(s.name).tag(Optional(s.id)) }
                    }
                    .pickerStyle(.menu)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(.white, in: RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.line))
                }
                if !categoryTree.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("分类").font(.subheadline.weight(.medium))
                        Picker("分类", selection: $selectedCategoryId) {
                            Text("不分类").tag(nil as Int?)
                            ForEach(categoryTree) { node in
                                Text(node.name).tag(Optional(node.id))
                                ForEach(node.children) { child in
                                    Text("　　\(child.name)").tag(Optional(child.id))
                                }
                            }
                        }
                        .pickerStyle(.menu)
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .background(.white, in: RoundedRectangle(cornerRadius: 10))
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.line))
                    }
                }
            }

            // Article preview tabs
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 0) {
                    previewTab("正文", 0)
                    previewTab("一页纸", 1)
                }
                .padding(.horizontal, 4).padding(.vertical, 6)
                .background(Color.white.opacity(0.5), in: RoundedRectangle(cornerRadius: 12))

                HStack {
                    Spacer()
                    Menu {
                        Button { fontSize = max(13, fontSize - 2) } label: { Label("缩小", systemImage: "textformat.size.smaller") }
                        Button { fontSize = min(24, fontSize + 2) } label: { Label("放大", systemImage: "textformat.size.larger") }
                        Button { fontSize = 16 } label: { Label("默认", systemImage: "textformat.size") }
                    } label: {
                        Image(systemName: "textformat.size").font(.subheadline).foregroundStyle(.secondary)
                    }
                }

                let html = resultTab == 0
                    ? extractHTMLBody(result.contentHtml)
                    : (result.summaryHtml.isEmpty ? extractHTMLBody(result.contentHtml) : extractHTMLBody(result.summaryHtml))
                HTMLContentView(html: html, fontSize: fontSize, contentHeight: $contentHeight)
                    .frame(height: contentHeight)
                    .padding(4)
            }

            // Publish button
            Button {
                Task { await publish() }
            } label: {
                HStack(spacing: 8) {
                    if isPublishing { ProgressView().tint(.white) } else { Image(systemName: "paperplane.fill") }
                    Text(isPublishing ? "发布中..." : "选择完成，发布文章")
                }
                .font(.headline)
                .frame(maxWidth: .infinity)
                .frame(height: 54)
                .foregroundStyle(.white)
                .background(AppTheme.terracotta, in: RoundedRectangle(cornerRadius: 13, style: .continuous))
            }
            .disabled(isPublishing || selectedSectionId == nil || editableTitle.trimmingCharacters(in: .whitespaces).count < (result.metadataMeta?.titleMin ?? 10))
        }
        .padding(16)
        .background(.white, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(AppTheme.line))
        .onAppear {
            if editableTitle.isEmpty {
                editableTitle = resultTitle(result)
                editableSubtitle = resultSubtitle(result)
            }
            if selectedBannerURL == nil, let first = result.banners.first {
                selectedBannerURL = first.url
            }
        }
    }

    private func previewTab(_ title: String, _ index: Int) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) { resultTab = index }
        } label: {
            Text(title)
                .font(.subheadline.weight(resultTab == index ? .semibold : .regular))
                .foregroundStyle(resultTab == index ? AppTheme.terracotta : .secondary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(resultTab == index ? AppTheme.terracotta.opacity(0.1) : Color.clear,
                            in: RoundedRectangle(cornerRadius: 8))
        }
    }

    private func resultTitle(_ r: DecodeJobResult) -> String {
        (r.metadataMeta?.title ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    }
    private func resultSubtitle(_ r: DecodeJobResult) -> String {
        (r.metadataMeta?.subtitle ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    // MARK: - 网络

    private func loadSections() async {
        do {
            sections = try await CloudAPI.get("/api/v1/content/sections", authenticated: false)
        } catch {}
    }

    private func loadCategories(for sectionId: Int) async {
        do {
            let tree: ContentCategoryTree = try await CloudAPI.get(
                "/api/v1/content/sections/\(sectionId)/categories-tree", authenticated: false
            )
            categoryTree = tree.categories
            selectedCategoryId = nil
        } catch { categoryTree = [] }
    }

    private func startDecode() async {
        let url = urlInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !url.isEmpty, url.hasPrefix("http") else {
            errorMessage = "请输入有效的网页链接（以 http:// 或 https:// 开头）"
            return
        }
        isLoading = true; isUrlFocused = false
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
        loadingStage = 0; errorMessage = nil
        jobResult = nil; publishMessage = nil; jobId = nil
        pulsingDots = true

        do {
            let start: JobStartResponse = try await CloudAPI.request(
                "/api/v1/insight/decode-url",
                method: "POST",
                body: DecodeUrlBody(url: url, titleHint: nil),
                authenticated: true
            )
            jobId = start.jobId
            await pollDecodeJob(jobId: start.jobId)
        } catch {
            withAnimation {
                errorMessage = error.localizedDescription
                isLoading = false; pulsingDots = false
            }
        }
    }

    private func pollDecodeJob(jobId: String) async {
        // give visual feedback through stages
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            if isLoading { withAnimation { loadingStage = 1 } }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.5) {
            if isLoading { withAnimation { loadingStage = 2 } }
        }

        for _ in 0..<240 {
            do {
                let resp: DecodeJobResponse = try await CloudAPI.get("/api/v1/insight/decode-url/\(jobId)", authenticated: true)
                if resp.status == "done", let result = resp.result {
                    withAnimation(.spring(response: 0.4)) {
                        jobResult = result
                        selectedBannerURL = result.banners.first?.url
                        editableTitle = resultTitle(result)
                        editableSubtitle = resultSubtitle(result)
                    }
                    isLoading = false; pulsingDots = false
                    return
                }
                if resp.status == "error" {
                    withAnimation {
                        errorMessage = resp.error.isEmpty ? "解读失败" : resp.error
                        isLoading = false; pulsingDots = false
                    }
                    return
                }
            } catch { /* transient polling failure */ }
            try? await Task.sleep(for: .seconds(2))
        }
        isLoading = false; pulsingDots = false
        errorMessage = "任务仍在后台处理，请稍后重新进入解读页查看"
    }

    private func publish() async {
        guard let result = jobResult, let jobId = jobId else { return }
        isPublishing = true; publishMessage = nil
        do {
            let response: PublishResponse = try await CloudAPI.request(
                "/api/v1/insight/decode-url/publish",
                method: "POST",
                body: DecodePublishBody(
                    jobId: jobId,
                    url: result.url,
                    sectionId: selectedSectionId ?? 0,
                    subCategoryId: selectedCategoryId,
                    bannerUrl: selectedBannerURL ?? "",
                    title: editableTitle.trimmingCharacters(in: .whitespacesAndNewlines),
                    subtitle: editableSubtitle.trimmingCharacters(in: .whitespacesAndNewlines),
                    excerpt: result.metadataMeta?.excerpt ?? ""
                ),
                authenticated: true
            )
            let sectionName = sections.first(where: { $0.id == selectedSectionId })?.name ?? "内容板块"
            let categoryName = categoryTree.first(where: { $0.id == selectedCategoryId })?.name
                ?? categoryTree.flatMap { $0.children }.first(where: { $0.id == selectedCategoryId })?.name
            let whereMsg = categoryName?.isEmpty == false ? "「\(sectionName) / \(categoryName)」" : "「\(sectionName)」"
            publishMessage = "✅ 已在 \(whereMsg) 发布文章 #\(response.id)"
            // 弹窗提醒发布成功，避免需要滚回顶部查看
            publishAlertTitle = "🎉 发布成功"
            publishAlertMessage = "文章已发布到 \(whereMsg)，可返回首页查看。"
            showPublishSuccess = true
            isPublishing = false
        } catch {
            isPublishing = false
            withAnimation { errorMessage = error.localizedDescription }
        }
    }

    private struct JobStartResponse: Codable { let jobId: String; let status: String }

    private func tip(icon: String, text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon).font(.caption).foregroundStyle(AppTheme.terracotta).frame(width: 18)
            Text(text).font(.caption).foregroundStyle(.secondary)
        }
    }
}

// MARK: - HTML 渲染

struct HTMLContentView: UIViewRepresentable {
    let html: String
    let fontSize: CGFloat
    @Binding var contentHeight: CGFloat

    final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: HTMLContentView
        init(parent: HTMLContentView) { self.parent = parent }
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
        view.scrollView.showsVerticalScrollIndicator = false
        view.scrollView.showsHorizontalScrollIndicator = false
        view.scrollView.alwaysBounceVertical = false
        view.navigationDelegate = context.coordinator
        return view
    }

    func updateUIView(_ view: WKWebView, context: Context) {
        // 技能生成的 SVG banner 宽高按桌面端（如 1600×900）内联，必须缩放以适配手机屏幕；
        // 由于 extractHTMLBody 会丢页头 <style>，这里复刻 .banner 的响应式规则。
        let css = """
        body{font-family:-apple-system;font-size:\(fontSize)px;line-height:1.65;color:#302b28;margin:0}
        svg{max-width:100% !important;height:auto !important;display:block}
        img,video,iframe{max-width:100% !important;height:auto !important;border-radius:10px}
        .banner,.banner-container{width:100% !important;max-width:100% !important;aspect-ratio:16/9;overflow:hidden;border-radius:12px;margin-bottom:16px}
        h1,h2,h3{line-height:1.3;margin-top:1em}
        blockquote{border-left:3px solid #b95737;padding-left:12px;color:#756b65}
        code{background:#f3eee9;padding:2px 4px;border-radius:4px}
        p{margin:0 0 12px}
        """
        view.loadHTMLString("<html><head><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><style>\(css)</style></head><body>\(html)</body></html>", baseURL: nil)
    }
}

/// 从完整 HTML 文档中取出 <body> 内容；非完整文档时原样返回。
func extractHTMLBody(_ html: String) -> String {
    let lower = html.lowercased()
    guard let bodyStartRange = lower.range(of: "<body") else { return html }
    guard let gt = html[bodyStartRange.upperBound...].firstIndex(of: ">") else { return html }
    let contentStart = html.index(after: gt)
    if let endLower = lower.range(of: "</body>"),
       endLower.lowerBound > contentStart {
        return String(html[contentStart..<endLower.lowerBound])
    }
    return String(html[contentStart...])
}

func markdownToHTML(_ text: String) -> String {
    var value = text
        .replacingOccurrences(of: "&", with: "&amp;")
        .replacingOccurrences(of: "<", with: "&lt;")
        .replacingOccurrences(of: ">", with: "&gt;")
    value = value.replacingOccurrences(of: #"!\[([^\]]*)\]\(([^)]+)\)"#, with: #"<img alt="$1" src="$2">"#, options: .regularExpression)
    value = value.replacingOccurrences(of: #"\[([^\]]+)\]\(([^)]+)\)"#, with: #"<a href="$2">$1</a>"#, options: .regularExpression)
    value = value.replacingOccurrences(of: #"\*\*([^*]+)\*\*"#, with: #"<strong>$1</strong>"#, options: .regularExpression)
    value = value.replacingOccurrences(of: #"^### (.+)$"#, with: #"<h3>$1</h3>"#, options: [.regularExpression, .anchored])
    value = value.replacingOccurrences(of: #"^## (.+)$"#, with: #"<h2>$1</h2>"#, options: [.regularExpression, .anchored])
    value = value.replacingOccurrences(of: #"^# (.+)$"#, with: #"<h1>$1</h1>"#, options: [.regularExpression, .anchored])
    return value.components(separatedBy: "\n\n").map { "<p>\($0.replacingOccurrences(of: "\n", with: "<br>"))</p>" }.joined()
}
