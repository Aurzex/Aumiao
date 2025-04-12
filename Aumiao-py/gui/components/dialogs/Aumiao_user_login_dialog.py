from siui.components import (
SiLabel,
SiLongPressButton,
SiPushButton,
SiLineEditWithItemName
)
from siui.core import SiColor, SiGlobal
from siui.templates.application.components.dialog.modal import SiModalDialog


class LoginDialog(SiModalDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setFixedWidth(500)
        self.icon().load(SiGlobal.siui.iconpack.get("ic_fluent_person_filled",
                                                    color_code=SiColor.mix(
                                                        self.getColor(SiColor.SVG_NORMAL),
                                                        self.getColor(SiColor.INTERFACE_BG_B),
                                                        0.05))
                         )

        label = SiLabel(self)
        label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_E)}")
        label.setText(
            f'<span style="color: {self.getColor(SiColor.TEXT_B)}">登入您的账号</span><br>'
        )
        label.adjustSize()
        self.contentContainer().addWidget(label)
        
        # 添加输入框
        self.demo_named_line_edit_1 = SiLineEditWithItemName(self)
        self.demo_named_line_edit_1.setName("编程猫账号")
        self.demo_named_line_edit_1.lineEdit().setText("")
        self.demo_named_line_edit_1.resize(512, 32)
        self.contentContainer().addWidget(self.demo_named_line_edit_1)
        
        
        loginButton : SiPushButton = SiPushButton(self)
        loginButton.setFixedHeight(32)
        loginButton.attachment().setText("登录")
        loginButton.colorGroup().assign(SiColor.BUTTON_PANEL, self.getColor(SiColor.INTERFACE_BG_D))
        loginButton.clicked.connect(SiGlobal.siui.windows["MAIN_WINDOW"].layerModalDialog().closeLayer)

        returnButton : SiPushButton = SiPushButton(self)
        returnButton.setFixedHeight(32)
        returnButton.attachment().setText("返回")
        returnButton.colorGroup().assign(SiColor.BUTTON_PANEL, self.getColor(SiColor.INTERFACE_BG_D))
        returnButton.clicked.connect(SiGlobal.siui.windows["MAIN_WINDOW"].layerModalDialog().closeLayer)

        # self.button3 = SiLongPressButton(self)
        # self.button3.setFixedHeight(32)
        # self.button3.attachment().setText("丢弃一切创作成果并退出")
        # self.button3.longPressed.connect(SiGlobal.siui.windows["MAIN_WINDOW"].layerModalDialog().closeLayer)

        self.buttonContainer().addWidget(loginButton)
        self.buttonContainer().addWidget(returnButton)
        # self.buttonContainer().addWidget(self.button3)

        SiGlobal.siui.reloadStyleSheetRecursively(self)
        self.adjustSize()

    def deleteLater(self):
        # print("你好")
        # self.button3.hold_thread.safe_to_stop = True
        # self.button3.hold_thread.wait()
        # self.button3.deleteLater()
        SiGlobal.siui.windows["TOOL_TIP"].setNowInsideOf(None)
        SiGlobal.siui.windows["TOOL_TIP"].hide_()
        super().deleteLater()