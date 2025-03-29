import { App } from "../../app.js";
import { FallTask, Rejected } from "../../utils.js";
import { CodeMaoClient, LoggedData } from "../CodeMaoClient.js";
import { AuthProvider } from "../auth.js";


export type LoginInfo = {
    user_info: {
        id: number;
        nickname: string;
        avatar_url: string;
        fullname: string;
        sex: 0 | 1;
        birthday: number;
        qq: string;
        description: string;
    };
    auth: {
        token: string;
        email: string;
        phone_number: string;
        has_password: boolean;
        is_weak_password: number;
    }
}

const FailedReasons: Record<string| number, string> = {
    400: "请求参数错误",
    403: "账号或密码错误",
}

export class Cred implements AuthProvider {
    static LOGIN_PID = "65edCTyg";
    constructor(protected app: App, protected client: CodeMaoClient) { }

    token: string = "";
    async login(): Promise<LoggedData | null> {
        const state: {
            username: string;
            password: string;
        } = {
            username: "",
            password: ""
        };

        const fall = new FallTask(this.app);
        fall.start(this.app.UI.color.blue("登录codemao.cn"));
        state.username = await fall.input("用户名:");
        state.password = await fall.password("密码:");
        fall.step(this.app.UI.color.gray(""), 1);

        let res = await fall.waitForLoading<LoginInfo | Rejected>(async (resolve, reject) => {
            let r = await this._SendLoginRequest(state.username, state.password);
            if (!Rejected.isRejected(r)) {
                resolve("");
            } else {
                reject(`登录失败！${r.message}\n可能的原因：${r.code ? FailedReasons[r.code] : "未知"}`);
            }
            return r;
        }, "正在登录…")

        if (!Rejected.isRejected(res) && (res as LoginInfo).auth.token) {
            fall.end(this.app.UI.color.green("登录成功！"));

            this.token = (res as LoginInfo).auth.token;
            return {
                id: (res as LoginInfo).user_info.id.toString(),
                nickname: (res as LoginInfo).user_info.nickname,
                token: this.token
            }
        } else {
            fall.end(this.app.UI.color.red("登录失败！"));
            return null;
        }
    }
    async isLogin(): Promise<boolean> {
        return !!(await this.client.syncDetails(true));
    }
    protected async _SendLoginRequest(username: string, password: string): Promise<LoginInfo | Rejected> {
        return this.client.request<LoginInfo>(CodeMaoClient.ENDPOINTS.login, {
            method: "POST",
            body: JSON.stringify({
                pid: Cred.LOGIN_PID,
                identity: username,
                password
            })
        })
    }
}

export class EnvCred extends Cred {
    constructor(protected app: App, protected client: CodeMaoClient) {
        super(app, client);
    }
    async login(): Promise<LoggedData | null> {
        const state: {
            username: string;
            password: string;
        } = {
            username: "",
            password: ""
        };

        const fall = new FallTask(this.app);
        fall.start(this.app.UI.color.blue("登录codemao.cn"));

        if (this.app.envConfig.CODEMAO_PASSWORD && this.app.envConfig.CODEMAO_USERNAME) {
            state.username = this.app.envConfig.CODEMAO_USERNAME;
            state.password = this.app.envConfig.CODEMAO_PASSWORD;
        } else if (process.env.PASSWORD && process.env.USERNAME) {
            state.username = process.env.USERNAME;
            state.password = process.env.PASSWORD;
        } else {
            fall.step(this.app.UI.color.yellow("没有找到凭据，当前配置的.env文件为：" + this.app.config.envFile + "\n如果你已有配置的env文件，请使用--env参数指定文件路径。"));
            state.username = await fall.input("用户名:");
            state.password = await fall.password("密码:");
        }

        this.app.Logger.debug(`login with username: [*****]`);

        fall.step(this.app.UI.color.gray(""), 1);

        let res = await fall.waitForLoading<LoginInfo | Rejected>(async (resolve, reject) => {
            let r = await this._SendLoginRequest(state.username, state.password);
            if (!Rejected.isRejected(r)) {
                resolve("");
            } else {
                reject(`登录失败！${r.message}\n可能的原因：${r.code ? FailedReasons[r.code] : "未知"}`);
            }
            return r;
        }, "正在登录…")

        if (!Rejected.isRejected(res) && (res as LoginInfo).auth.token) {
            fall.end(this.app.UI.color.green("登录成功！"));

            this.token = (res as LoginInfo).auth.token;
            return {
                id: (res as LoginInfo).user_info.id.toString(),
                nickname: (res as LoginInfo).user_info.nickname,
                token: this.token
            }
        } else {
            fall.end(this.app.UI.color.red("登录失败！"));
            return null;
        }
    }
    async isLogin(): Promise<boolean> {
        return super.isLogin();
    }
}
