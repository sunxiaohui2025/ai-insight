import SwiftUI

struct MainView: View {
    var body: some View {
        TabView {
            HomeView()
                .tabItem { Label("首页", systemImage: "house.fill") }
            CategoryBrowseView()
                .tabItem { Label("分类", systemImage: "folder.fill") }
            DecodeView()
                .tabItem { Label("解读", systemImage: "text.viewfinder") }
            SettingsView()
                .tabItem { Label("设置", systemImage: "gearshape.fill") }
        }
        .tint(AppTheme.terracotta)
    }
}
