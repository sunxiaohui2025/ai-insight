import UIKit
import Social
import UniformTypeIdentifiers

/// 分享页「InSight 深度收藏」
/// 与 App 内「解读」能力一致：选择板块+分类，点保存后调用后端 shared-save，
/// 后端在后台用 url-to-article 技能自动完成：生成主/副标题、自动选 banner、
/// 保存正文与一页纸。分享页不等待结果，提交后即可关闭。
final class ShareViewController: UIViewController {
    private let scrollView = UIScrollView()
    private let stackView = UIStackView()
    private let titleLabel = UILabel()
    private let urlLabel = UILabel()
    private let categoryScrollView = UIScrollView()
    private let categoryListStack = UIStackView()
    private let saveButton = UIButton(type: .system)
    private let statusLabel = UILabel()
    private let activityIndicator = UIActivityIndicatorView(style: .medium)

    private var sharedURL: String = ""
    private var sharedTitle: String = ""
    private var sections: [(id: Int, name: String)] = []
    private var subCategories: [(id: Int, name: String)] = []
    private var selectedSectionId: Int?
    private var selectedSubCategoryId: Int?
    private var isLoggedIn = false
    private var baseURL = ""
    private var token = ""

    private let terracotta = UIColor(red: 0.776, green: 0.365, blue: 0.227, alpha: 1.0)

    override func viewDidLoad() {
        super.viewDidLoad()
        setupUI()
        loadCredentials()
        extractSharedContent()
        loadSections()
    }

    // MARK: - UI Setup

    private func setupUI() {
        view.backgroundColor = UIColor(red: 0.965, green: 0.957, blue: 0.949, alpha: 1.0)

        // Title
        titleLabel.text = "InSight 深度收藏"
        titleLabel.font = .systemFont(ofSize: 20, weight: .bold)
        titleLabel.textColor = terracotta
        titleLabel.textAlignment = .center

        // URL label
        urlLabel.font = .systemFont(ofSize: 12)
        urlLabel.textColor = .gray
        urlLabel.numberOfLines = 2
        urlLabel.textAlignment = .center
        urlLabel.text = "提取中..."

        // Status label
        statusLabel.font = .systemFont(ofSize: 11)
        statusLabel.textColor = .gray
        statusLabel.textAlignment = .center
        statusLabel.numberOfLines = 0
        statusLabel.text = "正在加载板块..."

        // Category radio list
        categoryListStack.axis = .vertical
        categoryListStack.spacing = 6
        categoryListStack.alignment = .fill
        categoryScrollView.showsVerticalScrollIndicator = false
        categoryScrollView.addSubview(categoryListStack)
        categoryListStack.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            categoryListStack.topAnchor.constraint(equalTo: categoryScrollView.topAnchor),
            categoryListStack.leadingAnchor.constraint(equalTo: categoryScrollView.leadingAnchor),
            categoryListStack.trailingAnchor.constraint(equalTo: categoryScrollView.trailingAnchor),
            categoryListStack.bottomAnchor.constraint(equalTo: categoryScrollView.bottomAnchor),
            categoryListStack.widthAnchor.constraint(equalTo: categoryScrollView.widthAnchor)
        ])

        // Save button
        saveButton.setTitle("保存到 InSight", for: .normal)
        saveButton.titleLabel?.font = .systemFont(ofSize: 17, weight: .semibold)
        saveButton.backgroundColor = terracotta
        saveButton.setTitleColor(.white, for: .normal)
        saveButton.layer.cornerRadius = 12
        saveButton.addTarget(self, action: #selector(saveTapped), for: .touchUpInside)
        saveButton.isEnabled = false

        // Close button
        let closeButton = UIButton(type: .system)
        closeButton.setTitle("取消", for: .normal)
        closeButton.setTitleColor(terracotta, for: .normal)
        closeButton.titleLabel?.font = .systemFont(ofSize: 15)
        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)

        // Stack
        stackView.axis = .vertical
        stackView.spacing = 12
        stackView.alignment = .fill
        stackView.addArrangedSubview(titleLabel)
        stackView.addArrangedSubview(urlLabel)
        stackView.addArrangedSubview(categoryScrollView)
        stackView.addArrangedSubview(saveButton)
        stackView.addArrangedSubview(statusLabel)
        stackView.addArrangedSubview(closeButton)

        stackView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stackView)

        NSLayoutConstraint.activate([
            stackView.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            stackView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 28),
            stackView.bottomAnchor.constraint(lessThanOrEqualTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -20),
            stackView.widthAnchor.constraint(equalTo: view.widthAnchor, multiplier: 0.88),
            categoryScrollView.heightAnchor.constraint(equalToConstant: 320),
            saveButton.heightAnchor.constraint(equalToConstant: 50),
        ])
    }

    // MARK: - Credentials / Content

    private func loadCredentials() {
        let defaults = UserDefaults(suiteName: "group.com.sun.insight")
        baseURL = defaults?.string(forKey: "insightBaseURL") ?? ""
        token = KeychainHelper.loadToken(service: "com.sun.insight.cloud") ?? ""
        isLoggedIn = !token.isEmpty
        if !isLoggedIn {
            statusLabel.text = "⚠️ 请在 InSight App 中先登录"
        }
    }

    private func extractSharedContent() {
        guard let extensionItem = extensionContext?.inputItems.first as? NSExtensionItem,
              let attachments = extensionItem.attachments else {
            statusLabel.text = "无法获取分享内容"
            return
        }

        for provider in attachments {
            if provider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                provider.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { [weak self] item, _ in
                    guard let url = item as? URL else { return }
                    DispatchQueue.main.async {
                        self?.sharedURL = url.absoluteString
                        self?.urlLabel.text = url.absoluteString
                        self?.updateSaveButton()
                    }
                }
            }
            if provider.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) && sharedURL.isEmpty {
                provider.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { [weak self] item, _ in
                    guard let text = item as? String, text.hasPrefix("http") else { return }
                    DispatchQueue.main.async {
                        if self?.sharedURL.isEmpty ?? true {
                            self?.sharedURL = text
                            self?.urlLabel.text = text
                            self?.updateSaveButton()
                        }
                    }
                }
            }
            if provider.hasItemConformingToTypeIdentifier(UTType.propertyList.identifier) {
                provider.loadItem(forTypeIdentifier: UTType.propertyList.identifier, options: nil) { [weak self] item, _ in
                    guard let dict = item as? [String: Any],
                          let results = dict[NSExtensionJavaScriptPreprocessingResultsKey] as? [String: Any] else { return }
                    DispatchQueue.main.async {
                        if let url = results["url"] as? String, self?.sharedURL.isEmpty ?? true {
                            self?.sharedURL = url
                        }
                        if let title = results["title"] as? String {
                            self?.sharedTitle = title
                        }
                        self?.urlLabel.text = self?.sharedTitle ?? self?.sharedURL ?? ""
                        self?.updateSaveButton()
                    }
                }
            }
        }
    }

    // 加载可发布的板块（内容板块，与 App「解读」一致）
    private func loadSections() {
        guard isLoggedIn, !baseURL.isEmpty else {
            statusLabel.text = "请在 App 中设置服务器地址并登录"
            return
        }

        var request = URLRequest(url: URL(string: "\(baseURL)/api/v1/content/sections")!)
        if !token.isEmpty { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        request.timeoutInterval = 15

        URLSession.shared.dataTask(with: request) { [weak self] data, _, error in
            DispatchQueue.main.async {
                if let error = error {
                    self?.statusLabel.text = "加载板块失败: \(error.localizedDescription)"
                    return
                }
                guard let data = data,
                      let json = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else {
                    self?.statusLabel.text = "板块数据格式错误"
                    return
                }
                self?.sections = json.compactMap {
                    guard let id = $0["id"] as? Int, let name = $0["name"] as? String else { return nil }
                    return (id: id, name: name)
                }
                self?.selectedSectionId = self?.sections.first?.id
                if let id = self?.selectedSectionId {
                    self?.loadSubCategories(sectionId: id)
                } else {
                    self?.statusLabel.text = "暂无可用板块，请先在 App 中创建"
                }
                self?.renderCategoryButtons()
                self?.updateSaveButton()
            }
        }.resume()
    }

    // 加载所选板块的二级分类
    private func loadSubCategories(sectionId: Int) {
        guard !baseURL.isEmpty else { return }
        var request = URLRequest(url: URL(string: "\(baseURL)/api/v1/content/sections/\(sectionId)/categories-tree")!)
        if !token.isEmpty { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        request.timeoutInterval = 15

        URLSession.shared.dataTask(with: request) { [weak self] data, _, _ in
            DispatchQueue.main.async {
                guard let data = data,
                      let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      let cats = json["categories"] as? [[String: Any]] else {
                    self?.subCategories = []
                    self?.selectedSubCategoryId = nil
                    self?.renderCategoryButtons()
                    self?.updateSaveButton()
                    return
                }
                var list: [(id: Int, name: String)] = []
                for node in cats {
                    guard let id = node["id"] as? Int, let name = node["name"] as? String else { continue }
                    list.append((id: id, name: name))
                    if let children = node["children"] as? [[String: Any]] {
                        for child in children {
                            if let cid = child["id"] as? Int, let cname = child["name"] as? String {
                                list.append((id: cid, name: "    \(cname)"))
                            }
                        }
                    }
                }
                self?.subCategories = list
                self?.renderCategoryButtons()
                self?.updateSaveButton()
            }
        }.resume()
    }

    private func updateSaveButton() {
        saveButton.isEnabled = isLoggedIn && !sharedURL.isEmpty && !sections.isEmpty && selectedSectionId != nil
    }

    // 渲染：板块（一级）+ 选中板块的二级分类
    private func renderCategoryButtons() {
        categoryListStack.arrangedSubviews.forEach { $0.removeFromSuperview() }
        categoryListStack.addArrangedSubview(groupLabel("发布到板块"))

        for section in sections {
            let selected = section.id == selectedSectionId
            categoryListStack.addArrangedSubview(optionButton(
                title: section.name,
                isIndented: false,
                isSelected: selected,
                backgroundTint: terracotta,
                action: { [weak self] in self?.sectionTapped(section.id) }
            ))
        }

        if selectedSectionId != nil, !subCategories.isEmpty {
            categoryListStack.addArrangedSubview(groupLabel("分类（可选）"))
            for sub in subCategories {
                let selected = sub.id == selectedSubCategoryId
                categoryListStack.addArrangedSubview(optionButton(
                    title: sub.name,
                    isIndented: true,
                    isSelected: selected,
                    backgroundTint: terracotta,
                    action: { [weak self] in self?.subcategoryTapped(sub.id) }
                ))
            }
        }
    }

    private func groupLabel(_ text: String) -> UILabel {
        let label = UILabel()
        label.text = text
        label.font = .systemFont(ofSize: 11, weight: .semibold)
        label.textColor = .gray
        return label
    }

    private func optionButton(title: String, isIndented: Bool, isSelected: Bool,
                              backgroundTint: UIColor, action: @escaping () -> Void) -> UIButton {
        let button = UIButton(type: .system)
        button.contentHorizontalAlignment = .left
        button.titleLabel?.font = .systemFont(ofSize: 15, weight: isIndented ? .regular : .medium)
        button.setTitleColor(.darkText, for: .normal)
        button.backgroundColor = .white
        button.layer.cornerRadius = 9
        button.layer.borderWidth = 1
        button.contentEdgeInsets = UIEdgeInsets(top: 8, left: 12, bottom: 8, right: 12)
        let prefix = isIndented ? "      " : ""
        button.setTitle("\(prefix)\(title)", for: .normal)
        button.setImage(UIImage(systemName: isSelected ? "checkmark.circle.fill" : "circle"), for: .normal)
        button.tintColor = isSelected ? backgroundTint : .gray
        button.backgroundColor = isSelected ? backgroundTint.withAlphaComponent(0.10) : .white
        button.layer.borderColor = (isSelected ? backgroundTint : UIColor(white: 0.88, alpha: 1)).cgColor
        button.addAction(UIAction { _ in action() }, for: .touchUpInside)
        return button
    }

    private func sectionTapped(_ id: Int) {
        if selectedSectionId != id {
            selectedSectionId = id
            selectedSubCategoryId = nil
            subCategories = []
            loadSubCategories(sectionId: id)
        }
        renderCategoryButtons()
        updateSaveButton()
    }

    private func subcategoryTapped(_ id: Int) {
        selectedSubCategoryId = (selectedSubCategoryId == id) ? nil : id
        renderCategoryButtons()
    }

    // MARK: - Save (后台自动解读并发布)

    @objc private func saveTapped() {
        guard !sharedURL.isEmpty, let sectionId = selectedSectionId else { return }

        saveButton.isEnabled = false
        saveButton.setTitle("正在提交...", for: .normal)
        statusLabel.text = "正在提交，后台将自动调用技能解读..."

        var body: [String: Any] = [
            "url": sharedURL,
            "section_id": sectionId
        ]
        if let sub = selectedSubCategoryId {
            body["sub_category_id"] = sub
        }
        if !sharedTitle.isEmpty {
            body["title_hint"] = sharedTitle
        }

        var request = URLRequest(url: URL(string: "\(baseURL)/api/v1/insight/articles/shared-save")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        request.timeoutInterval = 30

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self?.statusLabel.text = "❌ 提交失败: \(error.localizedDescription)"
                    self?.saveButton.isEnabled = true
                    self?.saveButton.setTitle("保存到 InSight", for: .normal)
                    return
                }
                guard let http = response as? HTTPURLResponse else {
                    self?.showError("服务器无响应")
                    return
                }
                if http.statusCode == 200 || http.statusCode == 201 {
                    self?.statusLabel.text = "✅ 已提交！正在后台自动生成标题/banner 并发布，稍后到 App 查看即可。"
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                        self?.extensionContext?.completeRequest(returningItems: nil)
                    }
                } else {
                    var message = "提交失败 (\(http.statusCode))"
                    if let data = data,
                       let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                       let detail = json["detail"] as? String {
                        message = detail
                    }
                    self?.showError(message)
                }
            }
        }.resume()
    }

    private func showError(_ message: String) {
        statusLabel.text = "❌ \(message)"
        saveButton.isEnabled = true
        saveButton.setTitle("保存到 InSight", for: .normal)
    }

    @objc private func closeTapped() {
        extensionContext?.completeRequest(returningItems: nil)
    }
}

// MARK: - Keychain Helper

private enum KeychainHelper {
    static func loadToken(service: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: "token",
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
}
