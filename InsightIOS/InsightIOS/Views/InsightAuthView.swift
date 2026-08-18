import SwiftUI

struct InsightAuthView: View {
    @EnvironmentObject private var auth: AuthState
    @State private var email = ""
    @State private var password = ""
    @State private var name = ""
    @State private var serverURL = ""
    @State private var isRegistering = false
    @State private var message = ""
    @State private var isLoading = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Spacer().frame(height: 40)
                Image(systemName: "books.vertical.fill")
                    .font(.system(size: 48)).foregroundStyle(AppTheme.terracotta)
                Text("InSight").font(.system(size: 36, weight: .bold, design: .rounded))
                Text("深度收藏 · 保存即翻译")
                    .font(.subheadline).foregroundStyle(.secondary)
                VStack(spacing: 14) {
                    TextField("服务器地址", text: $serverURL)
                        .textContentType(.URL).keyboardType(.URL)
                        .autocapitalization(.none)
                        .padding(12).background(.white, in: RoundedRectangle(cornerRadius: 10))
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.line))
                    if isRegistering {
                        TextField("昵称", text: $name)
                            .padding(12).background(.white, in: RoundedRectangle(cornerRadius: 10))
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.line))
                    }
                    TextField("邮箱", text: $email)
                        .textContentType(.emailAddress).keyboardType(.emailAddress)
                        .autocapitalization(.none)
                        .padding(12).background(.white, in: RoundedRectangle(cornerRadius: 10))
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.line))
                    SecureField("密码（至少8位）", text: $password)
                        .padding(12).background(.white, in: RoundedRectangle(cornerRadius: 10))
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.line))
                }
                if !message.isEmpty {
                    Text(message).font(.caption).foregroundStyle(message.contains("成功") ? AppTheme.sage : .red)
                }
                Button {
                    Task { await performAction() }
                } label: {
                    HStack {
                        if isLoading { ProgressView().tint(.white) }
                        Text(isRegistering ? "注册" : "登录")
                    }
                }
                .buttonStyle(PrimaryButtonStyle()).disabled(isLoading || email.isEmpty || password.isEmpty)
                Button(isRegistering ? "已有账号？登录" : "没有账号？注册") {
                    isRegistering.toggle(); message = ""
                }
                .font(.subheadline).foregroundStyle(AppTheme.terracotta)
                Spacer()
            }.padding(.horizontal, 24)
        }
        .pageBackground()
        .onAppear {
            serverURL = CloudConfiguration.baseURL
            if let savedEmail = UserDefaults.standard.string(forKey: "insightEmail") {
                email = savedEmail
            }
        }
    }

    private func performAction() async {
        isLoading = true; message = ""
        CloudConfiguration.baseURL = serverURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        do {
            if isRegistering {
                let msg = try await auth.register(name: name.isEmpty ? email.components(separatedBy: "@").first ?? "用户" : name, email: email.trimmingCharacters(in: .whitespaces), password: password)
                message = msg; isRegistering = false
            } else {
                try await auth.login(email: email.trimmingCharacters(in: .whitespaces), password: password)
                UserDefaults.standard.set(email, forKey: "insightEmail")
                UserDefaults.standard.set(serverURL, forKey: "insightBaseURL")
            }
        } catch { message = error.localizedDescription }
        isLoading = false
    }
}
