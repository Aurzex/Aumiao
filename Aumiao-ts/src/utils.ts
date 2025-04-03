import { App } from "./app.js";

import * as path from "path";
import { pathToFileURL } from 'url';
import fs from "fs/promises";
import { createObjectCsvWriter } from "csv-writer";
import _ from "lodash";

type LogLevel = "INFO" | "ERROR" | "DEBUG" | "WARN" | "LOG" | "VERBOSE" | "UNKNOWN";
type LogLevelConfig = {
    color: string;// typeof UI.Colors[keyof typeof UI.Colors];
    colorMessage?: (v: string) => string;
    name: string;
};

export class Logger {
    app: App;
    LevelConfig: Record<LogLevel, LogLevelConfig>;
    constructor(app: App) {
        this.app = app;
        this.LevelConfig = {
            INFO: {
                color: this.app.UI.Colors.Gray,
                colorMessage: (v) => this.app.UI.hex(this.app.UI.Colors.Gray)(v),
                name: "INFO"
            },
            ERROR: {
                color: this.app.UI.Colors.Red,
                colorMessage: (v) => this.app.UI.hex(this.app.UI.Colors.Red)(v),
                name: "ERROR"
            },
            DEBUG: {
                color: this.app.UI.Colors.Navy,
                colorMessage: (v) => this.app.UI.hex(this.app.UI.Colors.Navy)(v),
                name: "DEBUG"
            },
            WARN: {
                color: this.app.UI.Colors.Yellow,
                colorMessage: (v) => this.app.UI.hex(this.app.UI.Colors.Yellow)(v),
                name: "WARN"
            },
            LOG: {
                color: this.app.UI.Colors.White,
                name: "LOG"
            },
            VERBOSE: {
                color: this.app.UI.Colors.Gray,
                colorMessage: (v) => this.app.UI.hex(this.app.UI.Colors.Gray)(v),
                name: "VERBOSE"
            },
            UNKNOWN: {
                color: this.app.UI.Colors.White,
                name: "-"
            }
        };
    }

    Levels: Record<LogLevel, LogLevel> = {
        INFO: "INFO",
        ERROR: "ERROR",
        DEBUG: "DEBUG",
        WARN: "WARN",
        LOG: "LOG",
        VERBOSE: "VERBOSE",
        UNKNOWN: "UNKNOWN"
    };

    generate({ level = this.Levels.UNKNOWN, message }: { level: LogLevel, message: string | Error }) {
        return `${this.app.UI.hex(this.LevelConfig[level].color)("[" + level + "]")} ${this.LevelConfig[level]?.colorMessage?.(
            message instanceof Error ? message.message : message
        ) || message}`;
    }

    log(message: string): Logger;
    log(message: Error): Logger;
    log(message: string | Error): Logger {
        try {
            if (message instanceof Error) message = message.message + "\n" + message.stack;
        } catch { /* empty */ }
        console.log(this.generate({ level: this.Levels.LOG, message }));
        return this;
    }

    warn(message: string): Logger {
        console.warn(this.generate({ level: this.Levels.WARN, message }));
        return this;
    }

    info(message: string): Logger {
        console.info(this.generate({ level: this.Levels.INFO, message }));
        return this;
    }

    error(message: string | Error): Error {
        if (message instanceof Error) message = message.message + "\n" + message.stack;
        console.error(this.generate({ level: this.Levels.ERROR, message }));
        return new Error(message);
    }

    debug(message: string | Error): Logger {
        try {
            if (typeof message !== "string") message = JSON.stringify(message);
        } catch { /* empty */ }
        if (this.app.config.debug) {
            const trackedData = ["USERNAME", "PASSWORD", "CODEMAO_DB_FILE"];
            const envData = trackedData.map((key) => process.env[key]);

            let msg = message;
            envData.forEach((data, i) => {
                if (data) {
                    const safeData = _.escapeRegExp(data);
                    msg = msg.replace(new RegExp(safeData, 'g'), `${trackedData[i]}: [*****]`);
                }
            });

            console.debug(this.generate({ level: this.Levels.DEBUG, message: msg }));
        }
        return this;
    }

    verbose(message: string) {
        /*
        If sensitive data is written to a log entry it could be exposed to an attacker who gains access to the logs.
        */
        if (this.app.config.verbose || this.app.options["verbose"]) {
            const trackedData = ["USERNAME", "PASSWORD", "CODEMAO_DB_FILE"];
            const envData = trackedData.map((key) => process.env[key]);

            let msg = message;
            envData.forEach((data, i) => {
                if (data) {
                    const safeData = _.escapeRegExp(data);
                    msg = msg.replace(new RegExp(safeData, 'g'), `${trackedData[i]}: [*****]`);
                }
            });

            console.log(
                this.generate({ level: this.Levels.VERBOSE, message: msg })
            );
        }
    }

    tagless(message: string) {
        console.log(message);
        return this;
    }
}

export class RPM {
    static subscribers: RPM[] = [];
    static intervalId: null | number | NodeJS.Timeout = null;
    interval: number;
    queue: {
        task: (...args: Array<unknown>) => void;
        args: Array<unknown>;
    }[];
    lastRunTimestamp: number;
    static exit() {
        if (RPM.intervalId !== null) clearInterval(RPM.intervalId);
    }

    static tick() {
        for (const subscriber of RPM.subscribers) {
            subscriber.runNextTask();
        }
    }

    constructor(maxRPM: number) {
        this.interval = 60000 / maxRPM;
        this.queue = [];
        this.lastRunTimestamp = 0;
        RPM.subscribers.push(this);
        if (RPM.intervalId === null) {
            RPM.intervalId = setInterval(RPM.tick, this.interval);
        }
    }

    addTask(task: () => void, ...args: undefined[]) {
        this.queue.push({ task, args });
    }

    runNextTask() {
        if (this.queue.length > 0 && Date.now() - this.lastRunTimestamp >= this.interval) {
            const { task, args } = this.queue.shift()!;
            this.lastRunTimestamp = Date.now();
            task(...args);
        }
    }

    createTask(taskFunction: (...args: Array<unknown>) => any, ...args: any[]) {
        return async () => {
            return new Promise(resolve => {
                this.addTask(() => {
                    const f = taskFunction(...args);
                    if (f.then) f.then(resolve);
                    else resolve(f);
                });
            });
        };
    }

    exit() {
        RPM.exit();
    }
}

export class TaskPool {
    maxConcurrent: any;
    delayBetweenTasks: any;
    taskQueue: (() => Promise<unknown>)[];
    running: boolean;
    allTasksDone: null | Promise<unknown>;
    allTasksDoneResolve!: (value: unknown) => void;
    constructor(maxConcurrent: any, delayBetweenTasks: any) {
        this.maxConcurrent = maxConcurrent;
        this.delayBetweenTasks = delayBetweenTasks;
        this.taskQueue = [];
        this.running = false;
        this.allTasksDone = null;
    }

    addTask(asyncTask: any) {
        this.taskQueue.push(asyncTask);
        return this;
    }

    addTasks(asyncTasks: any) {
        this.taskQueue.push(...asyncTasks);
        return this;
    }

    start() {
        this.running = true;
        this.allTasksDone = new Promise(resolve => this.allTasksDoneResolve = resolve);
        this.runTasks();
        return this.allTasksDone;
    }

    runTasks() {
        const tasksPromises = [];
        for (let i = 0; i < this.maxConcurrent && this.taskQueue.length > 0; i++) {
            tasksPromises.push(this.executeNextTask());
        }
        Promise.allSettled(tasksPromises).then(() => {
            if (this.taskQueue.length > 0) {
                this.runTasks();
            } else {
                this.allTasksDoneResolve(void 0);
            }
        });
    }

    async executeNextTask(): Promise<unknown> {
        if (!this.running) return;
        await new Promise(resolve => setTimeout(resolve, this.delayBetweenTasks));
        if (this.taskQueue.length === 0) return;
        const task = this.taskQueue.shift()!;
        return task().finally(() => {
            if (this.running && this.taskQueue.length > 0) {
                return this.executeNextTask();
            }
        });
    }

    stop() {
        this.running = false;
        return this;
    }
}

export async function moduleLoader(mods: string[]) {
    const modules = mods.map(mod => {
        const modulePath = mod.startsWith(".") ? path.resolve("../", mod) : mod;
        const moduleURL = mod.startsWith(".") ? pathToFileURL(modulePath).href : modulePath;
        return import(moduleURL);
    });
    return Promise.all(modules);
}

export class Rejected extends Error {
    code: string | number | undefined;
    
    static isRejected(r: any): r is Rejected {
        return r instanceof Rejected;
    }

    constructor(message: string | undefined, code?: number | string) {
        super(message);
        this.name = "Rejected";
        this.code = code;
    }
    toString() {
        return this.message;
    }
}

export function randomInt(min: number, max: number) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

export function sleep(ms: number | undefined) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export function isValidUrl(string: string) {
    /*
    This part of the regular expression may cause exponential backtracking on strings starting with '0' and containing many repetitions of '0'.
    */
    const urlRegex = /^(https?:\/\/)?((([a-z\d]([a-z\d-]*[a-z\d])*)\.)+[a-z]{2,}|((\d{1,3}\.){3}\d{1,3}))(:\d+)?(\/[-a-z\d%_.~+]*)*(\?[;&a-z\d%_.~+=-]*)?(#[-a-z\d_]*)?$/i;
    return urlRegex.test(string);
}

export function deepMergeObject<T extends Record<string, any>>(
    a: T,
    b: Record<string, any>
): T {
    function deepMerge(target: Record<string, any>, source: Record<string, any>): Record<string, any> {
        Object.keys(source).forEach(key => {
            if (source[key] instanceof Object && target[key] instanceof Object) {
                target[key] = deepMerge(target[key], source[key]);
            } else {
                /*
                Most JavaScript objects inherit the properties of the built-in Object.prototype object. 
                Prototype pollution is a type of vulnerability in which an attacker is able to modify Object.prototype. 
                Since most objects inherit from the compromised Object.prototype, the attacker can use this to tamper with the application logic, 
                and often escalate to remote code execution or cross-site scripting.
                */
                if (Object.prototype.hasOwnProperty.call(source, key)) {
                    target[key] = source[key];
                }
            }
        });
        return target;
    }

    return deepMerge({ ...a }, b) as T;
}

export function readObject<T>(obj: Record<string, T> | undefined, key: string): T | undefined {
    return obj ? obj[key] : undefined;
}

export function resolve(p: string, d: string) {
    return path.resolve(p, d);
}

export async function createFileIfNotExist(path: string, content: string) {
    try {
        await fs.access(path);
    } catch {
        await fs.writeFile(path, content);
    }
}

export async function createDirIfNotExist(path: string) {
    try {
        await fs.access(path);
    } catch {
        await fs.mkdir(path, { recursive: true });
    }
}

export async function readJSON(path: string, onError?: (e: Error) => void) {
    try {
        const data = await fs.readFile(path, "utf-8");
        return JSON.parse(data);
    } catch (e) {
        if (onError) onError(e as Error);
        return {};
    }
}

export async function writeJSON(path: string, data: any) {
    await fs.writeFile(path, JSON.stringify(data, null, 2));
}

export async function isFileExist(path: string) {
    try {
        await fs.access(path);
        return true;
    } catch {
        return false;
    }
}

export function sliceString(str: string, n: number): string[] {
    return Array.from({ length: Math.ceil(str.length / n) }, (_, i) => str.slice(i * n, (i + 1) * n));
}

export function writeJSONToCSV(obj: Record<string, any>[], headers: {id: string, title: string}[], file: string) {
    let writer = createObjectCsvWriter({
        path: file,
        header: headers
    });
    return writer.writeRecords(obj);
}

class LoadingTask {
    static Frames = {
        0: ["-", "\\", "|", "/"],
        1: ['◴', '◷', '◶', '◵'],
        2: ['◐', '◓', '◑', '◒'],
        3: ['▖', '▘', '▝', '▗'],
    }

    text: string | undefined;
    frame: keyof typeof LoadingTask.Frames;
    _tick: number | undefined;
    _interval: NodeJS.Timeout | undefined;
    constructor(protected app: App, protected fallTask: FallTask, frame: keyof typeof LoadingTask.Frames = 0) {
        this.frame = frame;
    }
    start(str: string) {
        this.text = str;
        this._interval = setInterval(() => this.tick(), 100);
        return this;
    }
    clearLine(str?: string) {
        const clearLine = '\r' + ' '.repeat(process.stdout.columns);
        if (str && str.length) process.stdout.write(`${clearLine}\r${this.fallTask.getPrefix()} ${str}`);
        else process.stdout.write(`${clearLine}\r`);
    }
    end(str?: string) {
        if (this._interval) clearInterval(this._interval);
        this.clearLine(str);
    }
    tick() {
        if (this._tick === undefined) this._tick = 0;
        else this._tick++;
        let output = [this.getAnimation(this._tick), this.text].join(" ");
        this.clearLine(output);
        return this;
    }
    setText(str: string) {
        this.text = str;
        return this;
    }
    getAnimation(tick: number) {
        const frames = LoadingTask.Frames[this.frame];
        return frames[tick % frames.length];
    }
}

class ProgressTask extends LoadingTask {
    static MaxLength = 20;
    static ProgressBarFrames = {
        0: {
            active: "█",
            inactive: " "
        }
    }

    maxTask: number;
    currentTask: number;
    pframe: keyof typeof ProgressTask.ProgressBarFrames;
    constructor(
        protected app: App, 
        protected fallTask: FallTask, 
        frame: keyof typeof LoadingTask.Frames = 0, 
        pframe: keyof typeof ProgressTask.ProgressBarFrames = 0
    ) {
        super(app, fallTask, frame);

        this.maxTask = this.currentTask = 0;
        this.pframe = pframe;
    }
    setMaxTask(n: number) {
        this.maxTask = n;
        return this;
    }
    setCurrentTask(n: number) {
        this.currentTask = n;
        return this;
    }
    incrementTask() {
        this.currentTask++;
        return this;
    }
    tick() {
        if (this._tick === undefined) this._tick = 0;
        else this._tick++;
        // let output = [this.fallTask.getPrefix(), this.getAnimation(this._tick), , this.text].join(" ");
        let output = `${this.fallTask.getPrefix()} ${this.getAnimation(this._tick)} ${this.getProgressBar()} (${this.currentTask}/${this.maxTask}) ${this.text}`
        process.stdout.write(`\r${output}`);
        return this;
    }
    getProgressBar() {
        let prefixLength = this.fallTask.getPrefix().length + 2;
        let maxLength = (process.stdout.columns - prefixLength) > ProgressTask.MaxLength ? ProgressTask.MaxLength : process.stdout.columns;
        let progress = Math.floor((this.currentTask / this.maxTask) * maxLength);
        let bar = (this.getPFrame(true)).repeat(progress) + (this.getPFrame(false)).repeat(maxLength - progress);
        return bar;
    }
    getPFrame(active: boolean) {
        return ProgressTask.ProgressBarFrames[this.pframe][active ? "active" : "inactive"];
    }
    log(message: string) {
        this.clearLine(message);
        this.fallTask.step("");
        return this;
    }
}

export class FallTask {
    static LoadingTask = LoadingTask;
    static fall(app: App, tasks: string[]) {
        const fall = new FallTask(app);
        tasks.forEach((task, i) => {
            if (i === 0) fall.start(task);
            else if (i === tasks.length - 1) fall.end(task);
            else fall.step(task);
        });
    }
    constructor(protected app: App) { }
    start(str: string) {
        this.app.Logger.tagless(`${this.app.UI.color.gray("╭─")} ${str}`);
        return this;
    }
    step(str: string, steps = 0, space = 0) {
        for (let i = 0; i < steps; i++) {
            this.app.Logger.tagless(`${this.app.UI.color.gray("│ ")}`);
        }
        let o = str.split("\n")
            .map((line) => line.length > process.stdout.columns - (this.getPrefix().length + 2)
                ? sliceString(line, process.stdout.columns - (this.getPrefix().length + 2))
                : line
            )
            .map((line) => " ".repeat(space) + line);
        o.forEach((line) => {
            this.app.Logger.tagless(`${this.app.UI.color.gray("│ ")} ${line}`);
        });
        return this;
    }
    waitForLoading<T>(
        handler: (resolve: (message: string) => void, reject: (message: string) => void, setText: (text: string) => void) => Promise<T>,
        str: string,
        frame: keyof typeof LoadingTask.Frames = 0
    ) {
        const loadingTask = new LoadingTask(this.app, this, frame);
        loadingTask.start(this.app.UI.color.gray(str));
        return handler(
            (message: string) => loadingTask.end(this.app.UI.color.gray(message ? message + "\n" : "")),
            (message: string) => (loadingTask.end(), this.error(message)),
            (text: string) => loadingTask.setText(this.app.UI.color.gray(text))
        );
    }
    waitForProgress<T>(
        handler: (resolve: (message: string) => void, reject: (message: string) => void, progress: ProgressTask) => Promise<T>,
        str: string,
        maxTask: number,
        frame: keyof typeof LoadingTask.Frames = 0,
        pframe: keyof typeof ProgressTask.ProgressBarFrames = 0
    ) {
        const progressTask = new ProgressTask(this.app, this, frame, pframe);
        progressTask.start(this.app.UI.color.gray(str)).setMaxTask(maxTask);
        return handler(
            (message: string) => progressTask.end(this.app.UI.color.gray(message ? message + "\n" : "")),
            (message: string) => (progressTask.end(), this.error(message)),
            progressTask
        );
    }
    end(str: string) {
        this.app.Logger.tagless(`${this.app.UI.color.gray("╰─")} ${str}`);
        return this;
    }
    error(str: string) {
        str.split("\n").forEach((line) => {
            this.step(this.app.UI.color.red(line));
        });
        return this;
    }
    getPrefix() {
        return this.app.UI.color.gray("│ ");
    }
    async input(prompt: string, options?: import("inquirer").InputQuestionOptions) {
        return await this.app.UI.input(prompt, this.app.UI.color.gray("│ "), options);
    }
    async password(prompt: string) {
        return await this.app.UI.password(prompt, this.app.UI.color.gray("│ "));
    }
}

export async function readJSONData<T extends Record<string, any>>(p: string, defaultValue: T): Promise<T> {
    try {
        await createDirIfNotExist(path.dirname(p));
        if (await isFileExist(p)) {
            return await readJSON(p);
        } else {
            await createFileIfNotExist(p, JSON.stringify(defaultValue));
            return defaultValue;
        }
    } catch (e: any) {
        throw new Rejected(e.message);
    }
}

export async function writeJSONData(p: string, data: any) {
    try {
        await createDirIfNotExist(path.dirname(p));
        await writeJSON(p, data);
    } catch (e: any) {
        throw new Rejected(e.message);
    }
}

export async function execBash(command: string) {
    return new Promise(async (resolve, reject) => {
        (await import("child_process")).exec(command, (error: any, stdout: any) => {
            if (error) reject(error);
            else resolve(stdout);
        });
    });
}

export function removeHTMLTags(str: string) {
    return str.replace(/<script.*?>.*?<\/script\s*>/gis, '').replace(/<[^>]*>/g, '');
}
