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
4. 按 [快捷指令搭建说明](shortcut/BUILD_GUIDE_zh-CN.md) 在 iPhone 上创建快捷指令。

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
- iOS 首次读取健康、位置和局域网信息时仍会显示系统授权提示。

## 开发检查

协议测试不依赖 Home Assistant：

```bash
python -m unittest discover -s tests -v
```

完整集成的运行验证需要 Home Assistant 2026.6 或更新版本。
