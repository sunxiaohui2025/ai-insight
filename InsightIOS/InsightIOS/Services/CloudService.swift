import Foundation
import Security
import SwiftData

enum CloudConfiguration {
    static var baseURL: String {
        get {
            let value = UserDefaults.standard.string(forKey: "insightBaseURL") ?? ""
            UserDefaults(suiteName: "group.com.sun.insight")?.set(value, forKey: "insightBaseURL")
            return value
        }
        set {
            let value = newValue.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            UserDefaults.standard.set(value, forKey: "insightBaseURL")
            // Share Extension reads the App Group suite, not the main app suite.
            UserDefaults(suiteName: "group.com.sun.insight")?.set(value, forKey: "insightBaseURL")
        }
    }
}

enum KeychainStore {
    private static let service = "com.sun.insight.cloud"
    static func saveToken(_ value: String) {
        let data = Data(value.utf8)
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "token"]
        SecItemDelete(query as CFDictionary)
        var insert = query; insert[kSecValueData as String] = data
        SecItemAdd(insert as CFDictionary, nil)
    }
    static func token() -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "token", kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    static func clear() {
        SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "token"] as CFDictionary)
    }
}

// MARK: - Auth

struct CloudUser: Codable { let email: String; let name: String; let role: String }

@MainActor
final class AuthState: ObservableObject {
    @Published var user: CloudUser?
    @Published var isChecking = true
    var isAuthenticated: Bool { user != nil && KeychainStore.token() != nil }

    init() {
        checkAuth()
    }

    func checkAuth() {
        if let data = UserDefaults.standard.data(forKey: "insightUser"),
           let cached = try? JSONDecoder().decode(CloudUser.self, from: data),
           KeychainStore.token() != nil {
            user = cached
        }
        isChecking = false
    }

    func login(email: String, password: String) async throws {
        let response: LoginResponse = try await CloudAPI.request("/api/v1/auth/login", body: AuthPayload(email: email, password: password), authenticated: false)
        KeychainStore.saveToken(response.token)
        user = response.user
        UserDefaults.standard.set(try? JSONEncoder().encode(response.user), forKey: "insightUser")
    }

    func register(name: String, email: String, password: String) async throws -> String {
        let response: MessageResponse = try await CloudAPI.request("/api/v1/auth/register", body: RegisterPayload(name: name, email: email, password: password), authenticated: false)
        return response.message
    }

    func logout() {
        KeychainStore.clear()
        UserDefaults.standard.removeObject(forKey: "insightUser")
        user = nil
    }
}

private struct AuthPayload: Encodable { let email: String; let password: String }
private struct RegisterPayload: Encodable { let name: String; let email: String; let password: String }
private struct LoginResponse: Decodable { let token: String; let user: CloudUser }
private struct MessageResponse: Decodable { let message: String }

// MARK: - API Client

enum CloudAPI {
    static func request<Response: Decodable>(_ path: String, method: String = "POST", authenticated: Bool = true) async throws -> Response {
        try await request(path, method: method, bodyData: nil, authenticated: authenticated)
    }

    static func request<Body: Encodable, Response: Decodable>(_ path: String, method: String = "POST", body: Body, authenticated: Bool = true) async throws -> Response {
        try await request(path, method: method, bodyData: JSONEncoder.cloud.encode(body), authenticated: authenticated)
    }

    static func request<Response: Decodable>(_ path: String, method: String, bodyData: Data?, authenticated: Bool) async throws -> Response {
        let base = CloudConfiguration.baseURL
        guard !base.isEmpty, let url = URL(string: base + path) else { throw CloudError.message("服务器地址未设置") }
        var req = URLRequest(url: url); req.httpMethod = method; req.timeoutInterval = 120
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = bodyData
        if authenticated {
            guard let token = KeychainStore.token() else { throw CloudError.message("请先登录") }
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CloudError.message("服务器无响应") }
        guard 200..<300 ~= http.statusCode else {
            let detail = (try? JSONDecoder().decode(ErrorResponse.self, from: data).detail) ?? "请求失败（\(http.statusCode)）"
            throw CloudError.message(detail)
        }
        return try JSONDecoder.cloud.decode(Response.self, from: data)
    }

    // GET helper
    static func get<Response: Decodable>(_ path: String, authenticated: Bool = true) async throws -> Response {
        try await request(path, method: "GET", bodyData: nil, authenticated: authenticated)
    }

    // DELETE helper
    static func delete(_ path: String, authenticated: Bool = true) async throws {
        let _: EmptyResponse = try await request(path, method: "DELETE", bodyData: nil, authenticated: authenticated)
    }

    // PATCH helper
    static func patch<Body: Encodable>(_ path: String, body: Body, authenticated: Bool = true) async throws {
        let _: EmptyResponse = try await request(path, method: "PATCH", bodyData: JSONEncoder.cloud.encode(body), authenticated: authenticated)
    }
}

func cloudMediaURL(_ path: String) -> URL? {
    guard !path.isEmpty else { return nil }
    if let url = URL(string: path), url.scheme != nil { return url }
    return URL(string: CloudConfiguration.baseURL + (path.hasPrefix("/") ? path : "/" + path))
}

enum CloudError: LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let v) = self { v } else { nil } }
}
private struct ErrorResponse: Decodable { let detail: String }
private struct EmptyResponse: Decodable {}

extension JSONEncoder {
    static var cloud: JSONEncoder {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        e.dateEncodingStrategy = .iso8601
        return e
    }
}
extension JSONDecoder {
    static var cloud: JSONDecoder {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        d.dateDecodingStrategy = .custom { decoder in
            let c = try decoder.singleValueContainer()
            let t = try c.decode(String.self)
            let fmt = ISO8601DateFormatter()
            fmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let std = ISO8601DateFormatter()
            std.formatOptions = [.withInternetDateTime]
            guard let date = fmt.date(from: t) ?? std.date(from: t) else {
                throw DecodingError.dataCorruptedError(in: c, debugDescription: "无法解析时间 \(t)")
            }
            return date
        }
        return d
    }
}

// MARK: - API Response Models

struct CategoryResponse: Codable, Identifiable {
    let id: Int; let name: String; let icon: String
    let sortOrder: Int; let articleCount: Int; let createdAt: String
}

struct ArticleResponse: Codable, Identifiable {
    let id: Int; let url: String; let title: String
    let sourceDomain: String; let excerpt: String; let status: String
    let isRead: Bool; let isStarred: Bool; let wordCount: Int
    let categoryId: Int?; let categoryName: String; let categoryIcon: String
    let createdAt: String; let updatedAt: String
}

struct ArticleDetailResponse: Codable, Identifiable {
    let id: Int; let url: String; let title: String
    let sourceDomain: String
    let originalContent: String; let translatedContent: String; let onePageSummary: String
    let excerpt: String; let status: String
    let isRead: Bool; let isStarred: Bool; let wordCount: Int
    let categoryId: Int?; let categoryName: String; let categoryIcon: String
    let createdAt: String; let updatedAt: String
}

struct ArticlesListResponse: Codable {
    let articles: [ArticleResponse]; let total: Int
    let page: Int; let pageSize: Int
}

struct ContentSection: Codable, Identifiable {
    let id: Int; let name: String; let slug: String
    let description: String
    var articleCount: Int = 0

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id); name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        slug = try c.decodeIfPresent(String.self, forKey: .slug) ?? ""; description = try c.decodeIfPresent(String.self, forKey: .description) ?? ""
        articleCount = try c.decodeIfPresent(Int.self, forKey: .articleCount) ?? 0
    }
}

struct ContentCategory: Codable, Identifiable {
    let id: Int; let sectionId: Int; let parentId: Int?
    let name: String; let slug: String; let icon: String
    let sortOrder: Int; var articleCount: Int = 0; var childCount: Int = 0
}

struct ContentCategoryTree: Codable {
    let section: ContentSection
    let categories: [ContentCategoryNode]
}

struct ContentCategoryNode: Codable, Identifiable {
    let id: Int; let sectionId: Int; let parentId: Int?
    let name: String; let slug: String; let icon: String
    let sortOrder: Int; var children: [ContentCategoryNode] = []

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id); sectionId = try c.decodeIfPresent(Int.self, forKey: .sectionId) ?? 0
        parentId = try c.decodeIfPresent(Int.self, forKey: .parentId); name = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        slug = try c.decodeIfPresent(String.self, forKey: .slug) ?? ""; icon = try c.decodeIfPresent(String.self, forKey: .icon) ?? ""
        sortOrder = try c.decodeIfPresent(Int.self, forKey: .sortOrder) ?? 0; children = try c.decodeIfPresent([ContentCategoryNode].self, forKey: .children) ?? []
    }
}

struct AdminCategoryBody: Encodable {
    let sectionId: Int; let parentId: Int?; let name: String; let slug: String; let icon: String; let sortOrder: Int
}

struct AdminCategoryUpdateBody: Encodable {
    let name: String?; let slug: String?; let parentId: Int?; let icon: String?; let sortOrder: Int?
}

struct ContentArticleResponse: Codable, Identifiable {
    let id: Int; let url: String; let title: String; let subtitle: String
    let sourceDomain: String; let excerpt: String; let status: String
    let wordCount: Int; let sectionId: Int?; let subCategoryId: Int?
    let contentType: String; let bannerUrl: String; let contentFormat: String
    let docKind: String; let attachmentUrl: String; let attachmentName: String
    let categoryName: String; let sectionName: String
    let authorName: String; let createdAt: String; let updatedAt: String

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id); url = try c.decodeIfPresent(String.self, forKey: .url) ?? ""
        title = try c.decodeIfPresent(String.self, forKey: .title) ?? "无标题"
        subtitle = try c.decodeIfPresent(String.self, forKey: .subtitle) ?? ""
        sourceDomain = try c.decodeIfPresent(String.self, forKey: .sourceDomain) ?? ""
        excerpt = try c.decodeIfPresent(String.self, forKey: .excerpt) ?? ""
        status = try c.decodeIfPresent(String.self, forKey: .status) ?? "ready"
        wordCount = try c.decodeIfPresent(Int.self, forKey: .wordCount) ?? 0
        sectionId = try c.decodeIfPresent(Int.self, forKey: .sectionId); subCategoryId = try c.decodeIfPresent(Int.self, forKey: .subCategoryId)
        contentType = try c.decodeIfPresent(String.self, forKey: .contentType) ?? "manual"
        bannerUrl = try c.decodeIfPresent(String.self, forKey: .bannerUrl) ?? ""
        contentFormat = try c.decodeIfPresent(String.self, forKey: .contentFormat) ?? "richtext"
        docKind = try c.decodeIfPresent(String.self, forKey: .docKind) ?? ""
        attachmentUrl = try c.decodeIfPresent(String.self, forKey: .attachmentUrl) ?? ""
        attachmentName = try c.decodeIfPresent(String.self, forKey: .attachmentName) ?? ""
        categoryName = try c.decodeIfPresent(String.self, forKey: .categoryName) ?? ""
        sectionName = try c.decodeIfPresent(String.self, forKey: .sectionName) ?? ""
        authorName = try c.decodeIfPresent(String.self, forKey: .authorName) ?? ""
        createdAt = try c.decodeIfPresent(String.self, forKey: .createdAt) ?? ""
        updatedAt = try c.decodeIfPresent(String.self, forKey: .updatedAt) ?? createdAt
    }
}

struct ContentArticleDetail: Codable, Identifiable {
    let id: Int; let url: String; let title: String; let subtitle: String
    let sourceDomain: String; let originalContent: String; let translatedContent: String
    let manualContent: String; let summaryContent: String; let onePageSummary: String
    let excerpt: String; let status: String; let wordCount: Int
    let contentType: String; let contentFormat: String; let docKind: String
    let bannerUrl: String; let attachmentUrl: String; let attachmentName: String
    let categoryName: String; let sectionName: String
    let authorName: String; let createdAt: String; let updatedAt: String

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id); url = try c.decodeIfPresent(String.self, forKey: .url) ?? ""
        title = try c.decodeIfPresent(String.self, forKey: .title) ?? "无标题"; subtitle = try c.decodeIfPresent(String.self, forKey: .subtitle) ?? ""
        sourceDomain = try c.decodeIfPresent(String.self, forKey: .sourceDomain) ?? ""
        originalContent = try c.decodeIfPresent(String.self, forKey: .originalContent) ?? ""; translatedContent = try c.decodeIfPresent(String.self, forKey: .translatedContent) ?? ""
        manualContent = try c.decodeIfPresent(String.self, forKey: .manualContent) ?? ""; summaryContent = try c.decodeIfPresent(String.self, forKey: .summaryContent) ?? ""; onePageSummary = try c.decodeIfPresent(String.self, forKey: .onePageSummary) ?? ""
        excerpt = try c.decodeIfPresent(String.self, forKey: .excerpt) ?? ""; status = try c.decodeIfPresent(String.self, forKey: .status) ?? "ready"; wordCount = try c.decodeIfPresent(Int.self, forKey: .wordCount) ?? 0
        contentType = try c.decodeIfPresent(String.self, forKey: .contentType) ?? "manual"; contentFormat = try c.decodeIfPresent(String.self, forKey: .contentFormat) ?? "richtext"; docKind = try c.decodeIfPresent(String.self, forKey: .docKind) ?? ""
        bannerUrl = try c.decodeIfPresent(String.self, forKey: .bannerUrl) ?? ""; attachmentUrl = try c.decodeIfPresent(String.self, forKey: .attachmentUrl) ?? ""; attachmentName = try c.decodeIfPresent(String.self, forKey: .attachmentName) ?? ""
        categoryName = try c.decodeIfPresent(String.self, forKey: .categoryName) ?? ""; sectionName = try c.decodeIfPresent(String.self, forKey: .sectionName) ?? ""; authorName = try c.decodeIfPresent(String.self, forKey: .authorName) ?? ""
        createdAt = try c.decodeIfPresent(String.self, forKey: .createdAt) ?? ""; updatedAt = try c.decodeIfPresent(String.self, forKey: .updatedAt) ?? createdAt
    }
}

struct ContentArticlesList: Codable { let articles: [ContentArticleResponse]; let total: Int; let page: Int; let pageSize: Int }

struct SaveArticleResponse: Codable {
    let id: Int; let status: String; let message: String
}

struct SaveArticleBody: Encodable {
    let url: String
    let categoryId: Int?
    enum CodingKeys: String, CodingKey { case url; case categoryId = "category_id" }
}

struct InsightStats: Codable {
    let total: Int; let unread: Int; let starred: Int; let processing: Int
}

struct DecodeResponse: Codable {
    let url: String; let title: String; let sourceDomain: String
    let wordCount: Int
    let originalContent: String; let translatedContent: String
    let onePageSummary: String
    let articleId: Int?
}

struct DecodeRequestBody: Encodable {
    let url: String
    let categoryId: Int?

    enum CodingKeys: String, CodingKey {
        case url
        case categoryId = "category_id"
    }
}

struct CreateCategoryBody: Encodable {
    let name: String; let icon: String
}

struct UpdateArticleBody: Encodable {
    let categoryId: Int?; let isRead: Bool?; let isStarred: Bool?
}
