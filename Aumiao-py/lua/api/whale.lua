-- whale.lua
local json = require("cjson")

-- Routine class (Singleton)
local Routine = {}
Routine.__index = Routine

local routine_instance = nil

function Routine.new()
    if routine_instance then
        return routine_instance
    end

    local self = setmetatable({}, Routine)
    self.acquire = require("utils.acquire").new()
    self.token = nil

    routine_instance = self
    return self
end

function Routine:set_token(token)
    self.token = token
    -- 设置请求头中的 Authorization
    self.acquire.default_headers = self.acquire.default_headers or {}
    self.acquire.default_headers["Authorization"] = token
end

function Routine:login(username, password, key, code)
    local response = self.acquire:post("https://api-whale.codemao.cn/admins/login", {
        headers = {
            ["Content-Type"] = "application/json"
        },
        data = {
            username = username,
            password = password,
            key = key,
            code = code
        }
    })

    if response.status_code == 200 then
        -- 如果登录成功，保存token
        if response.headers["authorization"] then
            self:set_token(response.headers["authorization"])
        end
        return response.json
    end
    return nil
end

function Routine:logout()
    local response = self.acquire:delete("https://api-whale.codemao.cn/admins/logout", {
        headers = {
            ["Authorization"] = self.token
        }
    })

    return response.status_code == 204
end

function Routine:get_data_info()
    local response = self.acquire:get("https://api-whale.codemao.cn/admins/info", {
        headers = {
            ["Authorization"] = self.token
        }
    })

    if response.status_code == 200 then
        return response.json
    end
    return nil
end

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

function Motion:handle_report(admin_id)
    local response = self.acquire:post("https://api-whale.codemao.cn/reports/handle", {
        headers = {
            ["Content-Type"] = "application/json"
        },
        data = {
            admin_id = admin_id
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

function Obtain:get_reports(page, limit)
    page = page or 1
    limit = limit or 20

    local response = self.acquire:get("https://api-whale.codemao.cn/reports", {
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
    Routine = Routine,
    Motion = Motion,
    Obtain = Obtain
}
