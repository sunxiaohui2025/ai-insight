import SwiftUI

struct CategoryBrowseView: View {
    @State private var sections: [ContentSection] = []
    @State private var trees: [Int: ContentCategoryTree] = [:]
    @State private var selectedSection: ContentSection?
    @State private var selectedCategory: ContentCategoryNode?
    @State private var errorMessage: String?
    @State private var treeErrors: [Int: String] = [:]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text("内容分类").font(.title2.bold())

                    // 顶部只保留三个一级入口，二级分类按需展开
                    primaryCategoryTabs

                    if let selectedSection {
                        sectionGroup(selectedSection)
                    }

                    if let error = errorMessage {
                        Text(error).font(.caption).foregroundStyle(.red)
                    }

                    CategoryListView(contentSectionId: selectedSection?.id, contentCategoryId: selectedCategory?.id,
                                     categoryName: selectedSection == nil ? "文章" : (selectedCategory?.name ?? selectedSection?.name ?? "文章"))
                }.padding(18)
            }
            .pageBackground().navigationTitle("分类").navigationBarTitleDisplayMode(.inline)
            .refreshable { await load() }
            .task { await load() }
        }
    }

    private var primaryCategoryTabs: some View {
        HStack(spacing: 8) {
            primaryTab(title: "全部文章", section: nil)
            ForEach(sections) { section in
                primaryTab(title: section.name, section: section)
            }
        }
    }

    private func primaryTab(title: String, section: ContentSection?) -> some View {
        let selected = selectedSection?.id == section?.id
        return Button {
            selectedSection = section; selectedCategory = nil
        } label: {
            Text(title).font(.subheadline.weight(.semibold)).lineLimit(1)
                .frame(maxWidth: .infinity).padding(.vertical, 12)
                .foregroundStyle(selected ? .white : AppTheme.ink)
                .background(selected ? AppTheme.terracotta : .white, in: RoundedRectangle(cornerRadius: 11))
                .overlay(RoundedRectangle(cornerRadius: 11).stroke(selected ? AppTheme.terracotta : AppTheme.line))
        }.buttonStyle(.plain)
    }

    @ViewBuilder private func sectionGroup(_ section: ContentSection) -> some View {
        let isSectionSelected = selectedSection?.id == section.id && selectedCategory == nil
        VStack(alignment: .leading, spacing: 10) {
            Text("\(section.name) · 二级分类").font(.subheadline.weight(.semibold)).foregroundStyle(AppTheme.mutedInk)

            // 只有选中板块后才展开二级分类目录
            if let tree = trees[section.id], !tree.categories.isEmpty {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 104), spacing: 8)], spacing: 8) {
                    ForEach(flatten(tree.categories)) { item in
                        categoryChip(section: section, category: item)
                    }
                }
            } else {
                if let treeError = treeErrors[section.id] {
                    Text("子分类加载失败：\(treeError)").font(.caption).foregroundStyle(.red).padding(.leading, 4)
                } else {
                    Text("暂无子分类").font(.caption).foregroundStyle(.secondary).padding(.leading, 4)
                }
            }
        }
    }

    private func categoryChip(section: ContentSection, category: ContentCategoryNode) -> some View {
        let isSelected = selectedCategory?.id == category.id
        return Button {
            selectedSection = section; selectedCategory = category
        } label: {
            Text(category.name)
                .font(.caption.weight(.medium)).lineLimit(1)
                .frame(maxWidth: .infinity).padding(.vertical, 9).padding(.horizontal, 8)
                .background(isSelected ? AppTheme.terracotta : .white, in: Capsule())
                .foregroundStyle(isSelected ? .white : AppTheme.ink)
                .overlay(Capsule().stroke(isSelected ? AppTheme.terracotta : AppTheme.line))
        }.buttonStyle(.plain)
    }

    private func flatten(_ roots: [ContentCategoryNode]) -> [ContentCategoryNode] {
        roots.flatMap { [$0] + flatten($0.children) }
    }

    private func load() async {
        do {
            sections = try await CloudAPI.get("/api/v1/content/sections")
            await loadAllTrees()
        } catch { errorMessage = error.localizedDescription }
    }
    private func loadAllTrees() async {
        treeErrors = [:]
        for section in sections {
            do {
                let tree: ContentCategoryTree = try await CloudAPI.get("/api/v1/content/sections/\(section.id)/categories-tree")
                trees[section.id] = tree
            } catch {
                treeErrors[section.id] = error.localizedDescription
            }
        }
    }
}
