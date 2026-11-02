from __future__ import annotations

from typing import Any

# 参考额度仅作运营起点，官方未公布固定数值；MUST NOT 当作事实自动套用。
QUOTA_TEMPLATES: dict[str, dict[str, Any]] = {
    "baidu": {
        "code": "baidu",
        "name": "百度智能云",
        "capability": "general_basic",
        "reference_quota": {"daily": None, "monthly": 1000, "total": None},
        "credential_fields": ["app_id", "api_key", "secret_key"],
        "notes": "通用文字识别（标准版）；额度以官网为准",
    },
    "tencent": {
        "code": "tencent",
        "name": "腾讯云",
        "capability": "GeneralBasicOCR",
        "reference_quota": {"daily": None, "monthly": 1000, "total": None},
        "credential_fields": ["secret_id", "secret_key"],
        "notes": "通用印刷体识别；额度以官网为准",
    },
}

DISCLAIMER = "参考额度以厂商官网为准，不自动套用到账号；创建账号时请按实际情况填写。"
