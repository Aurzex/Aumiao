from . import icons
from .components.page_about import About
from .components.page_container import ExampleContainer
from .components.page_dialog import ExampleDialogs
from .components.page_functional import ExampleFunctional
from .components.page_homepage import ExampleHomepage
from .components.page_icons import ExampleIcons
from .components.page_option_cards import ExampleOptionCards
from .components.page_page_control import ExamplePageControl
from .components.page_refactor import RefactoredWidgets
from .components.page_widgets import ExampleWidgets
from .components.dialogs.Aumiao_user_login_dialog import LoginDialog

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDesktopWidget

import siui
from siui.core import SiColor, SiGlobal
from siui.templates.application.application import SiliconApplication
from siui.components.widgets import (
    SiDenseHContainer,
    SiDenseVContainer,
    SiLabel,
    SiLineEdit,
    SiLongPressButton,
    SiPushButton,
    SiSimpleButton,
    SiSwitch,
)
from siui.components.button import SiPushButtonRefactor

# 载入图标
siui.core.globals.SiGlobal.siui.loadIcons(
    icons.IconDictionary(color=SiGlobal.siui.colors.fromToken(SiColor.SVG_NORMAL)).icons
)


class MySiliconApp(SiliconApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        screen_geo = QDesktopWidget().screenGeometry()
        self.setMinimumSize(1024, 380)
        self.resize(1366, 745)
        self.move(0, 0)
        self.layerMain().setTitle("Aumiao UI")
        self.setWindowTitle("Aumiao UI")
        self.setWindowIcon(QIcon("./img/empty_icon.png"))
        
        # 创建一个水平容器
        self.container_for_tools = SiDenseHContainer(self)
        self.container_for_tools.move(self.width() - 120, 16) #  调用当前对象的 container_for_tools 属性的方法 move         move 方法用于移动 container_for_tools 的位置         第一个参数 0 表示将 container_for_tools 水平方向移动到 x 坐标为 0 的位置         第二个参数 self.height() - 50 表示将 container_for_tools 垂直方向移动到 y 坐标为当前对象高度减去 50 的位置
        # self.container_for_tools.set
        self.container_for_tools.setFixedHeight(50)
        self.container_for_tools.setAlignment(Qt.AlignRight)
        self.container_for_tools.setSpacing(32)
        
        # 添加登录按钮
        self.login_pushbutton = SiPushButtonRefactor(self)
        self.login_pushbutton.setText("Login")
        self.login_pushbutton.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_person_passkey_regular"))
        self.login_pushbutton.adjustSize()
        self.login_pushbutton.clicked.connect(
            lambda: SiGlobal.siui.windows["MAIN_WINDOW"].layerModalDialog().setDialog(LoginDialog(self))
        )
        
        self.container_for_tools.addWidget(self.login_pushbutton)

        self.layerMain().addPage(ExampleHomepage(self),
                                 icon=SiGlobal.siui.iconpack.get("ic_fluent_home_filled"),
                                 hint="主页", side="top")
        self.layerMain().addPage(ExampleIcons(self),
                                 icon=SiGlobal.siui.iconpack.get("ic_fluent_diversity_filled"),
                                 hint="图标包", side="top")
        # self.layerMain().addPage(RefactoredWidgets(self),
        #                          icon=SiGlobal.siui.iconpack.get("ic_fluent_box_arrow_up_filled"),
        #                          hint="重构控件", side="top")
        self.layerMain().addPage(ExampleWidgets(self),
                                 icon=SiGlobal.siui.iconpack.get("ic_fluent_box_multiple_filled"),
                                 hint="控件", side="top")
        self.layerMain().addPage(ExampleContainer(self),
                                 icon=SiGlobal.siui.iconpack.get("ic_fluent_align_stretch_vertical_filled"),
                                 hint="容器", side="top")
        self.layerMain().addPage(ExampleOptionCards(self),
                                 icon=SiGlobal.siui.iconpack.get("ic_fluent_list_bar_filled"),
                                 hint="选项卡", side="top")
        self.layerMain().addPage(ExampleDialogs(self),
                                 icon=SiGlobal.siui.iconpack.get("ic_fluent_panel_separate_window_filled"),
                                 hint="消息与二级界面", side="top")
        self.layerMain().addPage(ExamplePageControl(self),
                                 icon=SiGlobal.siui.iconpack.get("ic_fluent_wrench_screwdriver_filled"),
                                 hint="页面控制", side="top")
        self.layerMain().addPage(ExampleFunctional(self),
                                 icon=SiGlobal.siui.iconpack.get("ic_fluent_puzzle_piece_filled"),
                                 hint="功能组件", side="top")

        self.layerMain().addPage(About(self),
                                 icon=SiGlobal.siui.iconpack.get("ic_fluent_info_filled"),
                                 hint="关于", side="bottom")

        self.layerMain().setPage(0)

        SiGlobal.siui.reloadAllWindowsStyleSheet()
        
    def showLoginDialog(self):
        pass

# if __name__ == "__main__":
#     app = QApplication([])
#     window = MySiliconApp()
#     window.show()
#     app.exec()