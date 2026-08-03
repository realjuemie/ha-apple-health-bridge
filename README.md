# Apple Health Bridge for Home Assistant

通过苹果“快捷指令”把健康、位置和 Wi-Fi 信息直接发送到局域网内的 Home Assistant。没有云端中转，也不需要外部服务器。

## 功能

- UI 配置：每台 iPhone/iPad 创建独立的随机 webhook。
- webhook 强制 `local_only=True`，只接受 `POST`/`PUT`。
- 健康指标首次上传时动态创建传感器实体。
- 固定创建 Wi-Fi 详情、上次同步、位置追踪和“显示连接信息”按钮实体。
- 保存最后一次数据，HA 重启后仍可恢复。
- 严格限制字段、长度、数值范围和 128 KiB 请求体。
- 诊断信息自动隐藏 webhook 密钥。

## 通过 HACS 安装（推荐）

1. 在 HACS 中打开“集成”。
2. 打开右上角菜单，选择“自定义存储库”。
3. 存储库填入：

   ```text
   https://github.com/realjuemie/ha-apple-health-bridge
   ```

4. 类别选择“集成”，添加后安装 `Apple Health Bridge`。
5. 重启 Home Assistant。
6. 打开“设置 → 设备与服务 → 添加集成”，搜索 `Apple Health Bridge` 或“苹果健康桥接”。

## 手动安装

1. 将本仓库中的 `custom_components/apple_health_bridge` 文件夹复制到 HA 配置目录：

   ```text
   /config/custom_components/apple_health_bridge
   ```

2. 重启 Home Assistant。

## 配置

1. 打开“设置 → 设备与服务 → 添加集成”，搜索 `Apple Health Bridge` 或“苹果健康桥接”。
2. 输入设备名称。
3. 从 HA 持久通知中复制本地 webhook 地址。
4. 下载并打开 [已签名的 Apple Health Bridge 快捷指令](shortcut/dist/Apple%20Health%20Bridge.shortcut)。
5. 导入时粘贴完整 webhook 地址；之后不需要手工搭建任何动作。
6. 首次运行时，先在 iOS 的健康授权页确认 13 类健康数据访问，再选择本次要同步的数据；位置和本地网络权限会在使用对应项目时请求。

快捷指令需要 iOS 18 或更高版本，并面向简体中文系统：健康样本筛选使用“步数”“活动能量”“睡眠”等中文类型名称。运行时只会连接你填写的 HA 局域网地址；仓库中的构建工具仅在生成苹果签名安装包时使用 Cherri Playground，不参与日常同步。源码、重新构建方法和手工搭建备用方案见 [快捷指令说明](shortcut/BUILD_GUIDE_zh-CN.md)。

## 数据协议

请求地址：

```text
http://HA_LAN_ADDRESS:8123/api/webhook/<随机 webhook_id>
```

请求方法为 `POST` 或 `PUT`，`Content-Type` 为 `application/json`。完整示例见 [payload-example.json](shortcut/payload-example.json)。

健康指标键必须为小写英文、数字和下划线，且以字母开头。每个指标接受：

```json
{
  "value": 1234,
  "unit": "steps",
  "name": "步数",
  "start": "2026-08-03T00:00:00+08:00",
  "end": "2026-08-03T10:30:00+08:00",
  "source": "Health"
}
```

只有 `value` 必填；其余字段可省略。集成内置常用指标的名称、单位和图标，未知但合法的指标键也会动态生成实体。

## 安全边界

- webhook 不要求 HA 登录令牌，所以 webhook 地址本身就是密钥。
- 集成拒绝非本地来源；不要通过反向代理把它暴露到公网。
- 数据只保存在 HA 自己的 `.storage` 中，快捷指令也不联系其他服务器。
- 快捷指令会在开头集中声明 13 类健康数据访问，但 iOS 系统授权页仍必须由用户亲自确认；快捷指令不能代替用户授权。

## 开发检查

协议测试不依赖 Home Assistant：

```bash
python -m unittest discover -s tests -v
```

完整集成的运行验证需要 Home Assistant 2026.6 或更新版本。

## 许可证

本项目使用 [MIT License](LICENSE)。
