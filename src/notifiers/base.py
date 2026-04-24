"""
通知システムの抽象基底クラス

すべての通知クラスが実装すべきインターフェースを定義します。
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseNotifier(ABC):
    """すべての通知クラスが実装すべき共通インターフェース。"""

    @abstractmethod
    def send_notification(
        self,
        device_info: Dict[str, str],
        is_unknown_device: bool = False,
        detected_at: Optional[float] = None,
    ) -> bool:
        """
        デバイス接続を通知する。

        Args:
            device_info: デバイス情報を含む辞書
            is_unknown_device: 未知端末の初回通知かどうか
            detected_at: 検出時刻（UNIXタイムスタンプ）

        Returns:
            通知送信成功時はTrue、失敗時はFalse
        """
        pass
