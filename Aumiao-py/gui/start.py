import sys
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
from ui import MySiliconApp

import siui
from siui.core import SiGlobal
from siui.core import SiColor
#
# siui.gui.set_scale_factor(1)


def show_version_message(window : MySiliconApp):
    window.LayerRightMessageSidebar().send(
        title = "欢迎来到 Aurzex Aumiao",
        text = "您当前运行的是 v1.14.514\n"
             "单击此消息框可查看新增功能",
        msg_type = SiColor.SIDE_MSG_THEME_NORMAL, # type: ignore
        icon = SiGlobal.siui.iconpack.get("ic_fluent_hand_wave_filled"),
        fold_after = 10000,
        slot = lambda: window.LayerRightMessageSidebar().send("哎呀，由于事实，似乎什么都不会发生"
                                                            "此功能当前未完成",
                                                            icon=SiGlobal.siui.iconpack.get("ic_fluent_info_regular"))
    )

    window.LayerRightMessageSidebar().send(
        title = "重构正在进行中",
        text = "为了优化项目结构， "
             "我们目前正在进行UI重构（使用 Silicon UI Gallery）",
        msg_type = SiColor.SIDE_MSG_THEME_WARNING, # type: ignore
        icon = SiGlobal.siui.iconpack.get("ic_fluent_warning_filled"),
    )


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = MySiliconApp()
    window.show()

    timer = QTimer(window)
    timer.singleShot(1000, lambda: show_version_message(window)) # 1秒后显示欢迎信息

    sys.exit(app.exec_())
