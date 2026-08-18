import Foundation
import SwiftData

@Model
final class Article {
    @Attribute(.unique) var id: Int
    var url: String
    var title: String
    var sourceDomain: String
    var originalContent: String
    var translatedContent: String
    var excerpt: String
    var status: String  // pending, extracting, translating, ready, failed
    var isRead: Bool
    var isStarred: Bool
    var wordCount: Int
    var categoryId: Int?
    var categoryName: String
    var categoryIcon: String
    var createdAt: Date
    var updatedAt: Date

    init(
        id: Int, url: String, title: String = "", sourceDomain: String = "",
        originalContent: String = "", translatedContent: String = "", excerpt: String = "",
        status: String = "pending", isRead: Bool = false, isStarred: Bool = false,
        wordCount: Int = 0, categoryId: Int? = nil,
        categoryName: String = "未分类", categoryIcon: String = "📄",
        createdAt: Date = .now, updatedAt: Date = .now
    ) {
        self.id = id
        self.url = url
        self.title = title
        self.sourceDomain = sourceDomain
        self.originalContent = originalContent
        self.translatedContent = translatedContent
        self.excerpt = excerpt
        self.status = status
        self.isRead = isRead
        self.isStarred = isStarred
        self.wordCount = wordCount
        self.categoryId = categoryId
        self.categoryName = categoryName
        self.categoryIcon = categoryIcon
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

// MARK: - 解读（复用后端 url-to-article 技能）

struct SkillBanner: Codable, Identifiable {
    let url: String
    let name: String
    let kind: String
    var id: String { url }
}

struct DecodeMeta: Codable {
    var title: String = ""
    var subtitle: String = ""
    var excerpt: String = ""
    var source: String = ""
    var model: String = ""
    var titleMin: Int = 10
    var subtitleMin: Int = 50
}

struct DecodeJobResult: Codable {
    var contentHtml: String = ""
    var summaryHtml: String = ""
    var url: String = ""
    var title: String = ""
    var detectedLanguage: String = ""
    var imageCount: Int = 0
    var banners: [SkillBanner] = []
    var metadataMeta: DecodeMeta?
}

struct DecodeJobLog: Codable { let ts: String; let level: String; let msg: String }

struct DecodeJobResponse: Codable {
    let id: String
    let url: String
    let status: String
    let error: String
    let result: DecodeJobResult?
    let logs: [DecodeJobLog]?
}

struct DecodeUrlBody: Encodable {
    let url: String
    let titleHint: String?
    enum CodingKeys: String, CodingKey {
        case url
        case titleHint = "title_hint"
    }
}

struct DecodePublishBody: Encodable {
    let jobId: String
    let url: String
    let sectionId: Int
    let subCategoryId: Int?
    let bannerUrl: String
    let title: String
    let subtitle: String
    let excerpt: String
    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case url
        case sectionId = "section_id"
        case subCategoryId = "sub_category_id"
        case bannerUrl = "banner_url"
        case title
        case subtitle
        case excerpt
    }
}

struct PublishResponse: Codable {
    let id: Int
    let status: String
    let message: String
}
