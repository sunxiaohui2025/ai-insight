import SwiftUI

struct CategoryManageView: View {
    @State private var categories: [CategoryResponse] = []
    @State private var newName = ""
    @State private var newIcon = "doc.text"
    @State private var isLoading = true
    @State private var errorMessage: String?

    let iconOptions = ["doc.text", "wrench.and.screwdriver", "atom", "briefcase", "brain", "lightbulb", "chart.bar", "target", "book", "globe", "bolt", "paintpalette", "sparkles", "diamond"]

    var body: some View {
        NavigationStack {
            List {
                Section("分类列表") {
                    ForEach(categories) { cat in
                        HStack {
                            Image(systemName: cat.icon).font(.title3)
                            Text(cat.name).font(.subheadline)
                            Spacer()
                            Text("\(cat.articleCount) 篇").font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    .onDelete(perform: deleteCategory)
                    .onMove(perform: moveCategory)
                }

                Section("添加新分类") {
                    HStack {
                        Picker("图标", selection: $newIcon) {
                            ForEach(iconOptions, id: \.self) { icon in
                                Label(icon, systemImage: icon).tag(icon)
                            }
                        }
                        .pickerStyle(.wheel).frame(height: 80)

                        VStack {
                            TextField("分类名称", text: $newName)
                                .padding(10).background(.white, in: RoundedRectangle(cornerRadius: 8))
                                .overlay(RoundedRectangle(cornerRadius: 8).stroke(AppTheme.line))
                            Button {
                                Task { await addCategory() }
                            } label: {
                                Text("添加").frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(AppTheme.terracotta)
                            .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty)
                        }
                    }
                }

                if let error = errorMessage {
                    Text(error).font(.caption).foregroundStyle(.red)
                }
            }
            .navigationTitle("分类管理")
            .toolbar { EditButton() }
            .task { await loadCategories() }
        }
    }

    private func loadCategories() async {
        isLoading = true; errorMessage = nil
        do {
            categories = try await CloudAPI.get("/api/v1/insight/categories")
        } catch { errorMessage = error.localizedDescription }
        isLoading = false
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
        } catch { errorMessage = error.localizedDescription }
    }

    private func deleteCategory(at offsets: IndexSet) {
        Task {
            for index in offsets {
                let cat = categories[index]
                do {
                    try await CloudAPI.delete("/api/v1/insight/categories/\(cat.id)")
                } catch { errorMessage = error.localizedDescription }
            }
            await loadCategories()
        }
    }

    private func moveCategory(from source: IndexSet, to destination: Int) {
        Task {
            categories.move(fromOffsets: source, toOffset: destination)
            let order = categories.map(\.id)
            do {
                struct ReorderBody: Encodable { let order: [Int] }
                let _: EmptyResponse = try await CloudAPI.request(
                    "/api/v1/insight/categories/reorder",
                    method: "PUT",
                    bodyData: JSONEncoder.cloud.encode(ReorderBody(order: order)),
                    authenticated: true
                )
            } catch { errorMessage = error.localizedDescription }
        }
    }
}

private struct EmptyResponse: Decodable {}
