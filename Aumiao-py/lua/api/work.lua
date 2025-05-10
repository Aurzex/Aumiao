-- work.lua
local json = require("cjson")

-- Motion class (Singleton)
local Motion = {}
Motion.__index = Motion

local motion_instance = nil

function Motion.new()
    if motion_instance then
        return motion_instance
    end

    local self = setmetatable({}, Motion)
    self.acquire = require("utils.acquire").new()

    motion_instance = self
    return self
end

function Motion:create_work_kitten(params)
    -- 验证必需参数
    assert(params.name, "name is required")
    assert(params.work_url, "work_url is required")
    assert(params.preview, "preview is required")
    assert(params.version, "version is required")

    -- 设置默认值
    params.orientation = params.orientation or 1
    params.sample_id = params.sample_id or ""
    params.work_source_label = params.work_source_label or 1
    params.save_type = params.save_type or 2

    -- 发送请求
    local response = self.acquire:post("https://api.codemao.cn/creation-tools/v1/works", {
        headers = {
            ["Content-Type"] = "application/json",
            ["User-Agent"] = "Mozilla/5.0"
        },
        data = {
            name = params.name,
            work_url = params.work_url,
            preview = params.preview,
            version = params.version,
            orientation = params.orientation,
            sample_id = params.sample_id,
            work_source_label = params.work_source_label,
            save_type = params.save_type
        }
    })

    return response.json
end

function Motion:reply_work()
    -- 实现自动回复作品功能
    local response = self.acquire:get("https://api.codemao.cn/creation-tools/v1/works/comments/to-reply", {
        headers = {
            ["User-Agent"] = "Mozilla/5.0"
        },
        params = {
            page = 1,
            limit = 20
        }
    })

    if response.status_code ~= 200 then
        return false
    end

    -- Process and reply to comments
    local comments = response.json.items
    for _, comment in ipairs(comments) do
        -- Generate and send reply
        self:post_work_comment(comment.work_id, "谢谢支持！")
        -- Add delay to avoid rate limiting
        os.execute("sleep 1")
    end

    return true
end

function Motion:post_work_comment(work_id, content)
    local response = self.acquire:post(string.format("https://api.codemao.cn/creation-tools/v1/works/%s/comments",
        work_id), {
        headers = {
            ["Content-Type"] = "application/json",
            ["User-Agent"] = "Mozilla/5.0"
        },
        data = {
            content = content
        }
    })

    return response.status_code == 200
end

-- Obtain class (Singleton)
local Obtain = {}
Obtain.__index = Obtain

local obtain_instance = nil

function Obtain.new()
    if obtain_instance then
        return obtain_instance
    end

    local self = setmetatable({}, Obtain)
    self.acquire = require("utils.acquire").new()

    obtain_instance = self
    return self
end

function Obtain:get_work_details(work_id)
    local response = self.acquire:get(string.format("https://api.codemao.cn/creation-tools/v1/works/%s", work_id), {
        headers = {
            ["User-Agent"] = "Mozilla/5.0"
        }
    })

    return response.json
end

return {
    Motion = Motion,
    Obtain = Obtain
}
