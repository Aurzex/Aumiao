-- forum.lua
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

function Motion:create_post(title, content, category_id)
    local response = self.acquire:post("https://api.codemao.cn/web/forums/posts", {
        headers = {
            ["Content-Type"] = "application/json"
        },
        data = {
            title = title,
            content = content,
            category_id = category_id
        }
    })

    if response.status_code == 200 then
        return response.json
    end
    return nil
end

function Motion:delete_post(post_id)
    local response = self.acquire:delete(string.format("https://api.codemao.cn/web/forums/posts/%d", post_id))

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

function Obtain:get_posts_details(ids)
    local params = {}

    -- 处理ids参数
    if type(ids) == "number" then
        params.ids = tostring(ids)
    elseif type(ids) == "table" then
        params.ids = table.concat(ids, ",")
    else
        return nil
    end

    local response = self.acquire:get("https://api.codemao.cn/web/forums/posts/all", {
        params = params
    })

    if response.status_code == 200 then
        return response.json
    end
    return nil
end

function Obtain:get_single_post_details(post_id)
    local response = self.acquire:get(string.format("https://api.codemao.cn/web/forums/posts/%d", post_id))

    if response.status_code == 200 then
        return response.json
    end
    return nil
end

function Obtain:get_post_comments(post_id, page, limit)
    page = page or 1
    limit = limit or 20

    local response = self.acquire:get(string.format("https://api.codemao.cn/web/forums/posts/%d/comments", post_id), {
        params = {
            page = page,
            limit = limit
        }
    })

    if response.status_code == 200 then
        return response.json
    end
    return nil
end

return {
    Motion = Motion,
    Obtain = Obtain
}
