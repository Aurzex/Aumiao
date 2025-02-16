import { App } from "../app.js";
import { CodeMaoClient } from "../client/CodeMaoClient.js";
import { tip } from "../client/tips.js";
import { Opt } from "../commands.js";
import { UserDetails } from "../types/api.js";
import {
	FallTask,
	createDirIfNotExist,
	deepMergeObject,
	isFileExist,
	readJSON,
	readObject,
	resolve,
	writeJSON,
} from "../utils.js";

import { dirname } from "path";

export enum LoginType {
	Credentials = "credentials",
	Cookie = "cookie",
	EnvCred = "env-cred",
}
export type LoginStored = {
	data: {
		token?: string;
	};
};
const defaultStored: LoginStored = {
	data: {},
};

export default async function main(app: App) {
	const state: {
		file: string;
		stored: LoginStored;
		client: CodeMaoClient;
		localToken: string;
	} = {
		file: "",
		stored: defaultStored,
		client: new CodeMaoClient({ app }),
		localToken: await loadToken(app),
	};

	// normal login
	if (
		state.localToken &&
		!(await app.UI.confirm(
			"你已经储存了凭据并且已经准备好用于登录，重新登录会覆盖当前状态，你要重新登录吗？"
		))
	) {
		if (await tryLogin(app, state.client, state.localToken)) {
			await MainPanel(app, state.client)();
			return;
		}
	}

	// initial login
	app.Logger.verbose("login state initialized");
	await askLogin(app, state.client);

	await MainPanel(app, state.client)();
	return;
}

function getLoginFileLoc(app: App) {
	return app.options["file"] || resolve(app.config.tempDir, "login.json");
}

async function loadToken(app: App): Promise<string> {
	let file = getLoginFileLoc(app),
		data: LoginStored;
	if (!(await isFileExist(file))) {
		await createDirIfNotExist(dirname(file));
		await writeJSON(file, defaultStored);
		data = defaultStored;
	} else {
		data = await readJSON(file);
	}

	return readObject(data.data, "token") || "";
}

export async function askLogin(
	app: App,
	client: CodeMaoClient
): Promise<boolean> {
	let method = await app.UI.selectByObject("登录方式：", {
		文本凭据: LoginType.Credentials,
		Cookie: LoginType.Cookie,
		Env文件: LoginType.EnvCred,
	});
	app.Logger.debug(`selected login method: ${method}`);
	await client.tryLogin(undefined, method as LoginType);

	await writeJSON(
		getLoginFileLoc(app),
		deepMergeObject(defaultStored, client.getStorableData())
	);
	return true;
}

export async function tryLogin(
	app: App,
	client: CodeMaoClient,
	token: string
): Promise<boolean> {
	client.token = token;
	if (!client.token) {
		app.Logger.info("无可用本地凭据，需要重新登录");
		await writeJSON(getLoginFileLoc(app), defaultStored);
		return false;
	}

	let fall = new FallTask(app);
	if (
		!(await fall.waitForLoading(async (resolve, reject) => {
			let r = await client.syncDetails(true);
			if (r) resolve("");
			else reject("本地凭据已过期，请重新登录");
			return r;
		}, "正在登录…"))
	) {
		await writeJSON(getLoginFileLoc(app), defaultStored);
		return false;
	} else {
		app.Logger.verbose("login state initialized");
		await writeJSON(
			getLoginFileLoc(app),
			deepMergeObject(defaultStored, client.getStorableData())
		);
		return true;
	}
}

export function MainPanel(app: App, client: CodeMaoClient) {
	return async () => {
		let fall = new FallTask(app);
		const [userDetails, messageRecord] = await fall.waitForLoading<
			Promise<[UserDetails | null, number | undefined]>
		>(async (resolve, reject) => {
			return await Promise.all([
				client.syncDetails(true),
				client.getMessageRecordCount().then((v) =>
					v
						?.filter((v) => v.query_type === "COMMENT_REPLY")
						.map((v) => v.count)
						.reduce((a, b) => a + b, 0)
				),
			])
				.then((v) => (resolve(""), v))
				.catch((v) => (reject(v), v));
		}, "正在获取用户信息…");

		const panel = [
			`${app.UI.color.gray("欢迎回来,")} ${userDetails?.nickname || ""} ${
				!app.options[Opt.sensei] ? "" : "Sensei!"
			}`,
			`${app.UI.color.gray("ID:")} ${userDetails?.id || ""}`,
			`${app.UI.color.gray("未读消息:")} ${app.UI.color.yellow(
				messageRecord ? messageRecord.toString() : "0"
			)}`,
			`${app.UI.color.gray("Tips: " + tip())}`,
		];

		FallTask.fall(app, panel);
	};
}
