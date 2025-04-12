import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

# import siui
from siui.core import SiGlobal

from gui import MySiliconApp

# from siui.core import SiColor

# siui.gui.set_scale_factor(1)


def show_version_message(window : MySiliconApp) -> None:
    window.LayerRightMessageSidebar().send(
        title = "欢迎来到 Aurzex Aumiao UI",
        text = "您当前运行的是 v1.14.514\n"
             "单击此消息框可查看新增功能",
        msg_type = 1,
        icon = SiGlobal.siui.iconpack.get("ic_fluent_hand_wave_filled"),
        fold_after = 10000,
        slot = lambda: window.LayerRightMessageSidebar().send("Aumiao UI"
                                                            "此功能当前未完成",
                                                            icon=SiGlobal.siui.iconpack.get("ic_fluent_info_regular"))
    )

    window.LayerRightMessageSidebar().send(
        title = "重构正在进行中",
        text = "为了优化项目结构， "
             "我们目前正在进行UI重构（使用 Silicon UI Gallery）",
        msg_type = 4,
        icon = SiGlobal.siui.iconpack.get("ic_fluent_warning_filled"),
    )


def main() -> None:
    """Aumiao UI 的启动函数"""
    app = QApplication(sys.argv)

    window = MySiliconApp()
    window.show()

    timer = QTimer(window)
    timer.singleShot(1000, lambda: show_version_message(window)) # 1秒后显示欢迎信息

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

# TODO: 优化启动速度