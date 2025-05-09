-- user.lua
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

function Motion:verify_phone(phone)
    local response = self.acquire:post("https://api.codemao.cn/tiger/v3/web/accounts/phone/verify", {
        headers = {
            ["Content-Type"] = "application/json"
        },
        data = {
            phone = tostring(phone)
        }
    })

    return response.status_code == 200
end

function Motion:update_profile(nickname, description)
    local response = self.acquire:put("https://api.codemao.cn/creation-tools/v1/user", {
        headers = {
            ["Content-Type"] = "application/json"
        },
        data = {
            nickname = nickname,
            description = description
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

function Obtain:get_user_details(user_id)
    local response = self.acquire:get(string.format("https://api.codemao.cn/api/user/info/detail/%s", user_id))

    if response.status_code == 200 then
        return response.json
    end
    return nil
end

function Obtain:get_user_honor(user_id)
    local response = self.acquire:get("https://api.codemao.cn/creation-tools/v1/user/center/honor", {
        params = {
            user_id = user_id
        }
    })

    if response.status_code == 200 then
        return response.json
    end
    return nil
end

function Obtain:get_works_list(user_id, type, page, limit)
    type = type or "ALL" -- ALL, KITTEN, NEMO, PINGPONG
    page = page or 1
    limit = limit or 20

    local response = self.acquire:get("https://api.codemao.cn/creation-tools/v1/user/center/works", {
        params = {
            user_id = user_id,
            type = type,
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
