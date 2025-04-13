import { App } from "../app.js";
import { LoginStored, LoginType } from "../app/login.js";
import {
	CommunityAPI,
	MessageCount,
	UserAPI,
	UserDetails,
} from "../types/api.js";
import { Rejected, readObject } from "../utils.js";
import { AuthProvider } from "./auth.js";
import { Cookie } from "./auth/cookie.js";
import { Cred, EnvCred } from "./auth/cred.js";
import { ua } from "./ua.js";

type CodeMaoClientConfig = {
	app: App;
};

export type LoggedData = {
	id: string;
	nickname: string;
	token: string;
};

export class CodeMaoClient {
	static BASE_URL = "https://api.codemao.cn";
	static ENDPOINTS = {
		login: "/tiger/v3/web/accounts/login",
		message_record: "/web/message-record/count",
		user_details: "/web/users/details",
	};
	app: App;
	ua: string;

	authProvider: AuthProvider | null = null;
	token: string = "";
	loginInfo: LoggedData | null = null;
	userDetails: UserDetails | null = null;
	api: API;
	constructor(protected config: CodeMaoClientConfig) {
		this.app = config.app;
		this.ua = ua();
		this.api = new API(this);

		this.app.Logger.verbose("CodeMaoClient initialized");
	}
	async tryLogin(
		loginStored?: LoginStored,
		type: LoginType = LoginType.Credentials
	) {
		this.app.Logger.verbose("trying to login: " + type);
		if (loginStored && readObject((loginStored || {}).data, "token")) {
			this.token = readObject(loginStored.data, "token") as string;
		} else {
			this.authProvider = this.getAuthProvider(type);
			this.loginInfo = await this.authProvider.login();
			this.token = this.loginInfo?.token || "";
		}

		if (!this.token || !this.loginInfo) {
			this.app.Logger.error("登录失败！");
			this.app.exit(this.app.App.EXIT_CODES.ERROR);
			return;
		}

		return this;
	}
	getAuthProvider(type: LoginType): AuthProvider {
		return Reflect.construct(
			{
				[LoginType.Credentials]: Cred,
				[LoginType.Cookie]: Cookie,
				[LoginType.EnvCred]: EnvCred,
			}[type],
			[this.app, this]
		);
	}
	async request<T>(
		endpoint: string,
		options: RequestInit
	): Promise<T | Rejected> {
		this.app.Logger.verbose(
			`requesting ${endpoint} with options: ${JSON.stringify(options)}`
		);
		const res = await fetch(
			endpoint.startsWith("http")
				? endpoint
				: CodeMaoClient.BASE_URL + endpoint,
			{
				...options,
				headers: {
					"User-Agent": this.ua,
					"Content-Type": "application/json",
					...(options.headers || {}),
					...(this.token
						? {
								cookie: "authorization=" + this.token,
						  }
						: {}),
				},
			}
		);
		if (!res.ok) {
			try {
				let msg = await res.json();
				return new Rejected(
					`Request failed with status ${res.status}: ${
						msg?.error_message || JSON.stringify(msg)
					}`,
					res.status
				);
			} catch {
				return new Rejected(
					`Request failed with status ${res.status}: ${res.statusText}`,
					res.status
				);
			}
		}
		return (await res.json()) as T;
	}

	public getStorableData(): LoginStored {
		return {
			data: {
				token: this.token,
			},
		};
	}

	private async requestEndpoint<T>(
		endpoint: string,
		options: RequestInit,
		silent = false
	): Promise<T | null> {
		let res = await this.request<T>(endpoint, options);
		if (Rejected.isRejected(res)) {
			if (!silent)
				this.app.Logger.error(
					"Failed to request endpoint: " + endpoint + "\n" + res.toString()
				);
			return null;
		}
		return res;
	}

	public async syncDetails(silent = false) {
		return await this.requestEndpoint<UserDetails>(
			CodeMaoClient.ENDPOINTS.user_details,
			{
				method: "GET",
			},
			silent
		);
	}

	public async getMessageRecordCount() {
		return await this.requestEndpoint<MessageCount[]>(
			CodeMaoClient.ENDPOINTS.message_record,
			{
				method: "GET",
			}
		);
	}
}

class API {
	static BaseUrls = {
		API: "https://api.codemao.cn",
	};
	static Endpoints = {
		user: {
			info: {
				details: {
					get: "/api/user/info/detail",
				},
			},
			center: {
				honor: {
					get: "/creation-tools/v1/user/center/honor",
				},
			},
		},
		forum: {
			post: {
				replies: {
					get: ["/web/forums/posts/", "/replies"],
				},
				details: {
					get: ["/web/forums/posts/", "/details"],
				},
				hots: {
					get: "/web/forums/posts/hots/all",
				},
				all: {
					get: "/web/forums/posts/all/",
				},
			},
		},
	};
	constructor(protected client: CodeMaoClient) {}

	getUrl(endpoint: string[], end?: string): string;
	getUrl(endpoint: string[], end?: string[]): string;
	getUrl(endpoint: string, end?: string): string;
	getUrl(endpoint: string | string[], end?: string | string[]): string {
		if (Array.isArray(endpoint)) {
			let res = "",
				params = Array.isArray(end) ? end : [end];
			for (let i = 0; i < endpoint.length; i++) {
				res += endpoint[i];
				if (params[i]) res += params[i];
			}
			return res;
		}
		return (
			API.BaseUrls.API +
			endpoint +
			(endpoint.endsWith("/") ? "" : "/") +
			(end ? end : "")
		);
	}

	/**
	 * 获取用户详细信息
	 * @param userId 用户ID
	 */
	public async getUserDetail(
		userId: string
	): Promise<UserAPI.OtherUser | Rejected> {
		return await this.client.request<UserAPI.OtherUser>(
			this.getUrl(API.Endpoints.user.info.details.get, userId),
			{
				method: "GET",
			}
		);
	}
	/**
	 * 获取用户荣誉信息
	 * @param userId 用户ID
	 */
	public async getHonor(userId: string): Promise<UserAPI.Honor | Rejected> {
		return await this.client.request<UserAPI.Honor>(
			this.getUrl(API.Endpoints.user.center.honor.get, `?user_id=${userId}`),
			{
				method: "GET",
			}
		);
	}
	/**
	 * 获取帖子回复
	 * @param postId 帖子ID
	 * @param page 页码
	 * @param limit 每页数量(似乎最高是30)
	 */
	public async getPostReplies(
		postId: string,
		page: number,
		limit: number = 10
	): Promise<CommunityAPI.Replies | Rejected> {
		return await this.client.request<CommunityAPI.Replies>(
			this.getUrl(API.Endpoints.forum.post.replies.get, [
				postId,
				`?page=${page}&limit=${limit}&sort=-created_at`,
			]),
			{
				method: "GET",
			}
		);
	}
	/**
	 * 获取帖子详情
	 * @param postId 帖子ID
	 */
	public async getPostDetails(
		postId: string
	): Promise<CommunityAPI.Post | Rejected> {
		return await this.client.request<CommunityAPI.Post>(
			this.getUrl(API.Endpoints.forum.post.details.get, postId),
			{
				method: "GET",
			}
		);
	}
	/**
	 * 获得前三百个热门帖子
	 */
	public async getHotsPosts(): Promise<string[] | Rejected> {
		return await this.client.request<string[]>(
			this.getUrl(API.Endpoints.forum.post.hots.get),
			{
				method: "GET",
			}
		);
	}
	/**
	 * 获取帖子缓存，同时上限为30，不一定所有的帖子都会被返回
	 * @param postIds
	 */
	public async getPostCaches(postIds: string[]) {
		return await this.client.request<{ items: CommunityAPI.CachedPost[] }>(
			this.getUrl(
				API.Endpoints.forum.post.all.get,
				"?ids=" + postIds.join(",")
			),
			{
				method: "GET",
			}
		);
	}
}
