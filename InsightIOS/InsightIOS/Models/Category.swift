import Foundation
import SwiftData

@Model
final class Category {
    @Attribute(.unique) var id: Int
    var name: String
    var icon: String
    var sortOrder: Int
    var articleCount: Int
    var createdAt: Date

    init(id: Int, name: String, icon: String = "📄", sortOrder: Int = 0, articleCount: Int = 0, createdAt: Date = .now) {
        self.id = id
        self.name = name
        self.icon = icon
        self.sortOrder = sortOrder
        self.articleCount = articleCount
        self.createdAt = createdAt
    }
}
