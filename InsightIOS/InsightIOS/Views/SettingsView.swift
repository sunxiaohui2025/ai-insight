import SwiftUI

private struct CategoryManageView: View {
    @State private var sections: [ContentSection] = []
    @State private var selectedSectionId = 1
    @State private var categories: [ContentCategory] = []
    @State private var editing: ContentCategory?
    @State private var parentId: Int?
    @State private var showingEditor = false
    @State private var errorMessage: String?

    var body: some View {
        List {
            Section("内容板块") {
                Picker("板块", selection: $selectedSectionId) {
                    ForEach(sections) { Text($0.name).tag($0.id) }
                }.onChange(of: selectedSectionId) { _, _ in Task { await loadCategories() } }
            }
            Section {
                ForEach(categories.filter { $0.parentId == nil }) { category in
                    VStack(alignment: .leading, spacing: 7) {
                        categoryRow(category, indent: 0)
                        ForEach(categories.filter { $0.parentId == category.id }) { child in
                            categoryRow(child, indent: 1)
                        }
                    }
                }
                Button { parentId = nil; editing = nil; showingEditor = true } label: {
                    Label("添加一级分类", systemImage: "plus.circle")
                }.foregroundStyle(AppTheme.terracotta)
            } header: { Text("分类目录") }
            if let errorMessage { Text(errorMessage).font(.caption).foregroundStyle(.red) }
        }
        .navigationTitle("分类管理")
        .toolbar { ToolbarItem(placement: .topBarTrailing) { Button { parentId = nil; editing = nil; showingEditor = true } label: { Image(systemName: "plus") } } }
        .task { await loadSections() }
        .sheet(isPresented: $showingEditor) {
            CategoryEditor(existing: editing, parentId: parentId, sectionId: selectedSectionId) { await loadCategories() }
        }
    }

    private func categoryRow(_ category: ContentCategory, indent: Int) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "square.grid.2x2").foregroundStyle(AppTheme.terracotta)
            Text(category.name).font(indent == 0 ? .subheadline.weight(.semibold) : .subheadline).padding(.leading, CGFloat(indent * 22))
            Spacer(); Text("\(category.articleCount) 篇").font(.caption).foregroundStyle(.secondary)
            Menu {
                Button("编辑") { editing = category; parentId = category.parentId; showingEditor = true }
                if indent == 0 { Button("添加二级分类") { editing = nil; parentId = category.id; showingEditor = true } }
                Button("删除", role: .destructive) { Task { await delete(category.id) } }
            } label: { Image(systemName: "ellipsis.circle").foregroundStyle(.secondary) }
        }.padding(.vertical, 4)
    }

    private func loadSections() async {
        do { sections = try await CloudAPI.get("/api/v1/content/sections"); selectedSectionId = sections.first?.id ?? 1; await loadCategories() }
        catch { errorMessage = error.localizedDescription }
    }
    private func loadCategories() async {
        do { categories = try await CloudAPI.get("/api/v1/admin/sections/\(selectedSectionId)/categories") }
        catch { errorMessage = error.localizedDescription }
    }
    private func delete(_ id: Int) async {
        do { try await CloudAPI.delete("/api/v1/admin/categories/\(id)"); await loadCategories() }
        catch { errorMessage = error.localizedDescription }
    }
}

private struct CategoryEditor: View {
    let existing: ContentCategory?; let parentId: Int?; let sectionId: Int; let onSaved: () async -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""; @State private var slug = ""; @State private var icon = "⌁"
    var body: some View {
        NavigationStack { Form {
            TextField("分类名称", text: $name); TextField("Slug", text: $slug); TextField("图标", text: $icon)
            Button(existing == nil ? "创建" : "保存") { Task { await save() } }.disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
        }.navigationTitle(existing == nil ? (parentId == nil ? "添加一级分类" : "添加二级分类") : "编辑分类").toolbar { ToolbarItem(placement: .topBarLeading) { Button("取消") { dismiss() } } }.onAppear { name = existing?.name ?? ""; slug = existing?.slug ?? ""; icon = existing?.icon ?? "⌁" } }
    }
    private func save() async {
        let body = AdminCategoryBody(sectionId: sectionId, parentId: parentId, name: name, slug: slug.isEmpty ? name.lowercased().replacingOccurrences(of: " ", with: "-") : slug, icon: icon, sortOrder: 0)
        do {
            if let existing {
                let update = AdminCategoryUpdateBody(name: name, slug: body.slug, parentId: parentId, icon: icon, sortOrder: nil)
                let _: SettingsEmptyResponse = try await CloudAPI.request("/api/v1/admin/categories/\(existing.id)", method: "PUT", body: update)
            } else {
                let _: SettingsEmptyResponse = try await CloudAPI.request("/api/v1/admin/categories", method: "POST", body: body)
            }
            await onSaved(); dismiss()
        } catch {}
    }
}

struct SettingsView: View {
    @EnvironmentObject private var auth: AuthState
    @State private var baseURL = ""
    @State private var stats = InsightStats(total: 0, unread: 0, starred: 0, processing: 0)
    @State private var categories: [CategoryResponse] = []
    @State private var newName = ""
    @State private var newIcon = "doc.text"
    @State private var catErrorMessage: String?
    @State private var showCategorySheet = false
    @State private var pendingDelete: CategoryResponse?
    @State private var showMoveSheet = false

    let iconOptions = ["doc.text", "wrench.and.screwdriver", "atom", "briefcase", "brain", "lightbulb", "chart.bar", "target", "book", "globe", "bolt", "paintpalette", "sparkles", "diamond"]

    var body: some View {
        NavigationStack {
            Form {
                Section("账号") {
                    if let user = auth.user {
                        HStack {
                            VStack(alignment: .leading) {
                                Text(user.name).font(.headline)
                                Text(user.email).font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Button("退出") { auth.logout() }
                                .buttonStyle(.bordered).tint(.red)
                        }
                    }
                }

                Section("服务器") {
                    TextField("服务器地址", text: $baseURL)
                        .onSubmit { CloudConfiguration.baseURL = baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/")) }
                }

                Section("内容分类") {
                    NavigationLink {
                        CategoryManageView()
                    } label: {
                        Label("分类管理", systemImage: "folder.badge.gearshape")
                    }
                    Text("管理项目沉淀、研究解读及其一二级分类").font(.caption).foregroundStyle(.secondary)
                }

                Section("统计") {
                    HStack {
                        Text("总收藏"); Spacer(); Text("\(stats.total)").foregroundStyle(.secondary)
                    }
                    HStack {
                        Text("未读"); Spacer(); Text("\(stats.unread)").foregroundStyle(.secondary)
                    }
                    HStack {
                        Text("星标"); Spacer(); Text("\(stats.starred)").foregroundStyle(.secondary)
                    }
                    HStack {
                        Text("处理中"); Spacer(); Text("\(stats.processing)").foregroundStyle(.secondary)
                    }
                }

                Section("关于") {
                    HStack {
                        Text("版本"); Spacer(); Text("1.0.0").foregroundStyle(.secondary)
                    }
                    Text("InSight - 深度收藏，一键保存网页内容并全文翻译，随时随地阅读你的知识库。")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("设置")
            .onAppear {
                baseURL = CloudConfiguration.baseURL
                Task {
                    await loadStats()
                    await loadCategories()
                }
            }
            .sheet(isPresented: $showCategorySheet) {
                NavigationStack {
                    VStack(spacing: 20) {
                        Text("添加分类").font(.headline).padding(.top, 30)

                        VStack(spacing: 8) {
                            Text("选择图标").font(.caption).foregroundStyle(.secondary)
                            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 7), spacing: 8) {
                                ForEach(iconOptions, id: \.self) { icon in
                                    Button {
                                        newIcon = icon
                                    } label: {
                                        Image(systemName: icon).font(.title2)
                                            .frame(width: 40, height: 40)
                                            .background(newIcon == icon ? AppTheme.terracotta.opacity(0.15) : Color.clear,
                                                        in: RoundedRectangle(cornerRadius: 8))
                                            .overlay(RoundedRectangle(cornerRadius: 8)
                                                        .stroke(newIcon == icon ? AppTheme.terracotta : AppTheme.line, lineWidth: 1))
                                    }
                                }
                            }
                        }

                        TextField("分类名称", text: $newName)
                            .padding(12).background(.white, in: RoundedRectangle(cornerRadius: 10))
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.line))

                        Button {
                            Task {
                                await addCategory()
                                showCategorySheet = false
                            }
                        } label: {
                            Text("添加").font(.headline).frame(maxWidth: .infinity).frame(height: 50)
                                .foregroundStyle(.white)
                                .background(AppTheme.terracotta, in: RoundedRectangle(cornerRadius: 12))
                        }
                        .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty)

                        Spacer()
                    }
                    .padding(.horizontal, 24)
                    .toolbar {
                        ToolbarItem(placement: .navigationBarLeading) {
                            Button("取消") { showCategorySheet = false }
                        }
                    }
                }
                .presentationDetents([.medium])
            }
            .sheet(isPresented: $showMoveSheet) {
                NavigationStack {
                    List {
                        Section("将文章移动到") {
                            ForEach(categories.filter { $0.id != pendingDelete?.id }) { target in
                                Button {
                                    Task { await moveArticlesAndDelete(to: target) }
                                } label: {
                                    Label(target.name, systemImage: systemIcon(target.icon))
                                }
                            }
                        }
                    }
                    .navigationTitle("移动文章")
                    .toolbar { ToolbarItem(placement: .navigationBarLeading) { Button("取消") { showMoveSheet = false } } }
                }
                .presentationDetents([.medium])
            }
        }
    }

    private func loadStats() async {
        do {
            stats = try await CloudAPI.get("/api/v1/insight/stats")
        } catch {}
    }

    private func loadCategories() async {
        do {
            categories = try await CloudAPI.get("/api/v1/insight/categories")
        } catch {
            catErrorMessage = error.localizedDescription
        }
    }

    private func addCategory() async {
        let name = newName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        do {
            let _: CategoryResponse = try await CloudAPI.request(
                "/api/v1/insight/categories",
                method: "POST",
                body: CreateCategoryBody(name: name, icon: newIcon)
            )
            newName = ""; newIcon = "doc.text"
            await loadCategories()
        } catch {
            catErrorMessage = error.localizedDescription
        }
    }

    private func deleteCategory(at offsets: IndexSet) {
        Task {
            for index in offsets {
                let cat = categories[index]
                if cat.articleCount > 0 {
                    pendingDelete = cat
                    showMoveSheet = true
                    continue
                }
                do {
                    try await CloudAPI.delete("/api/v1/insight/categories/\(cat.id)")
                } catch {
                    catErrorMessage = error.localizedDescription
                }
            }
            await loadCategories()
        }
    }

    private func moveArticlesAndDelete(to target: CategoryResponse) async {
        guard let source = pendingDelete else { return }
        do {
            let list: ArticlesListResponse = try await CloudAPI.get("/api/v1/insight/articles?category_id=\(source.id)&page_size=200")
            for article in list.articles {
                let _: SettingsEmptyResponse = try await CloudAPI.request(
                    "/api/v1/insight/articles/\(article.id)", method: "PATCH",
                    bodyData: JSONEncoder.cloud.encode(UpdateArticleBody(categoryId: target.id, isRead: nil, isStarred: nil)), authenticated: true
                )
            }
            try await CloudAPI.delete("/api/v1/insight/categories/\(source.id)")
            pendingDelete = nil; showMoveSheet = false
            await loadCategories()
        } catch { catErrorMessage = error.localizedDescription }
    }

    private func systemIcon(_ icon: String) -> String {
        ["📥": "tray", "🛠": "wrench.and.screwdriver", "🔬": "atom", "💼": "briefcase", "🧠": "brain", "📄": "doc.text"][icon] ?? icon
    }
}

private struct SettingsEmptyResponse: Decodable {}
