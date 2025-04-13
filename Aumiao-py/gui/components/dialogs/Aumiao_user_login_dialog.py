from siui.components import (
SiLabel,
SiLongPressButton,
SiPushButton,
SiLineEditWithItemName
)
from siui.core import SiColor, SiGlobal
from siui.templates.application.components.dialog.modal import SiModalDialog
# from src import *
# from src.api import (
#     community,
#     user,
# )
# from src.utils import data

from PyQt5.QtWidgets import QMessageBox

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
        self.userAccountLineEdit = SiLineEditWithItemName(self)
        self.userAccountLineEdit.setName("编程猫账号")
        self.userAccountLineEdit.lineEdit().setText("")
        self.userAccountLineEdit.resize(512, 32)
        self.contentContainer().addWidget(self.userAccountLineEdit)
        
        # 添加密码框
        self.userPasswordLineEdit = SiLineEditWithItemName(self)
        self.userPasswordLineEdit.setName("密码")
        self.userPasswordLineEdit.lineEdit().setText("")
        self.userPasswordLineEdit.resize(512, 32)
        # self.userPasswordLineEdit.lineEdit().setEchoMode(SiLineEditWithItemName.Password)
        self.contentContainer().addWidget(self.userPasswordLineEdit)

        # 添加按钮
        loginButton : SiPushButton = SiPushButton(self)
        loginButton.setFixedHeight(32)
        loginButton.attachment().setText("登录")
        loginButton.colorGroup().assign(SiColor.BUTTON_PANEL, self.getColor(SiColor.INTERFACE_BG_D))
        loginButton.clicked.connect(self.login)

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

    def login(self) -> None:
        """登录"""
        # identity : str = self.userAccountLineEdit.lineEdit().text()
        # password = self.userPasswordLineEdit.lineEdit().text()
        # if identity and password:
        #     try:
        #         community.Login().login_token(identity=identity, password=password)  # noqa: F405
        #         _data = user.Obtain().get_data_details()  # noqa: F405
        #         account_data_manager = data.DataManager()  # noqa: F405
        #         account_data_manager.update({
        #             "ACCOUNT_DATA": {
        #                 "identity": identity,
        #                 "password": "******",
        #                 "id": _data["id"],
        #                 "nickname": _data["nickname"],
        #                 "create_time": _data["create_time"],
        #                 "description": _data["description"],
        #                 "author_level": _data["author_level"],
        #             },
        #         },)
        #         QMessageBox.information(self, "成功", "登录成功")  # noqa: F405
        #         self.isLogin = True
        #         self.set_button_disabled(self.isLogin)
        #     except Exception as e:
        #         QMessageBox.critical(self, "错误", f"登录失败: {e}")  # noqa: F405
        SiGlobal.siui.windows["MAIN_WINDOW"].layerModalDialog().closeLayer()