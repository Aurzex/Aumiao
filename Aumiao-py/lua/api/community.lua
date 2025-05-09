-- community.lua
local json = require("cjson")

-- Login class (Singleton)
local Login = {}
Login.__index = Login

local login_instance = nil

function Login.new()
    if login_instance then
        return login_instance
    end

    local self = setmetatable({}, Login)
    self.acquire = require("utils.acquire").new()
    self.tool = require("utils.tool")
    self.setting = require("utils.data").SettingManager():getData()

    login_instance = self
    return self
end

function Login:login_token(identity, password, pid)
    pid = pid or "65edCTyg"

    -- 构建登录请求
    local response = self.acquire:post("https://api.codemao.cn/tiger/v3/web/accounts/login", {
        headers = {
            ["Content-Type"] = "application/json",
            ["User-Agent"] = "Mozilla/5.0"
        },
        data = {
            identity = identity,
            password = password,
            pid = pid
        }
    })

    if response.status_code ~= 200 then
        return nil
    end

    -- 保存登录token
    local token = response.headers["authorization"]
    if token then
        self.acquire:set_cookie("authorization", token, "codemao.cn")
    end

    return response.json
end

function Login:logout(method)
    method = method or "web"

    if method == "web" then
        local response = self.acquire:post("https://api.codemao.cn/tiger/v3/web/accounts/logout", {
            headers = {
                ["Content-Type"] = "application/json",
                ["User-Agent"] = "Mozilla/5.0"
            }
        })
        return response.status_code == 200
    end

    return false
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
    self.tool = require("utils.tool")
    self.setting = require("utils.data").SettingManager():getData()

    motion_instance = self
    return self
end

function Motion:clear_comments(source_type, action_type)
    -- Implementation of clear_comments
    -- This would include the logic to clear comments based on source and action type
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
    self.tool = require("utils.tool")
    self.setting = require("utils.data").SettingManager():getData()

    obtain_instance = self
    return self
end

function Obtain:get_data_details()
    local response = self.acquire:get("https://api.codemao.cn/creation-tools/v1/user/details", {
        headers = {
            ["User-Agent"] = "Mozilla/5.0"
        }
    })

    if response.status_code ~= 200 then
        return nil
    end

    return response.json
end

return {
    Login = Login,
    Motion = Motion,
    Obtain = Obtain
}
