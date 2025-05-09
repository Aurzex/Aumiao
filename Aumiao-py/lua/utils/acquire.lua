-- acquire.lua
local http = require("socket.http")
local ltn12 = require("ltn12")
local json = require("cjson")

local Client = {}
Client.__index = Client

-- Constants
local LOG_DIR = "/.log"
local LOG_FILE_PATH = LOG_DIR .. "/" .. os.time() .. ".txt"

function Client.new()
    local self = setmetatable({}, Client)
    self.session = {} -- 模拟 requests.Session
    self.cookies = {} -- Cookie storage
    return self
end

function Client:request(method, url, options)
    options = options or {}
    local headers = options.headers or {}
    local data = options.data
    local params = options.params
    local timeout = options.timeout or 10

    -- Prepare request
    local request = {
        method = method,
        url = url,
        headers = headers,
        source = data and ltn12.source.string(json.encode(data)),
        sink = ltn12.sink.table({}),
        timeout = timeout
    }

    -- Add query parameters
    if params then
        local query = {}
        for k, v in pairs(params) do
            table.insert(query, k .. "=" .. v)
        end
        if #query > 0 then
            request.url = request.url .. "?" .. table.concat(query, "&")
        end
    end

    -- Make request
    local response = {}
    local ok, code, headers, status = http.request(request)

    if not ok then
        error("HTTP request failed: " .. code)
    end

    -- Parse response
    response.status_code = code
    response.headers = headers
    response.text = table.concat(request.sink)

    -- Try to parse JSON
    local success, result = pcall(json.decode, response.text)
    if success then
        response.json = result
    end

    return response
end

-- Shorthand methods
function Client:get(url, options)
    return self:request("GET", url, options)
end

function Client:post(url, options)
    return self:request("POST", url, options)
end

function Client:put(url, options)
    return self:request("PUT", url, options)
end

function Client:delete(url, options)
    return self:request("DELETE", url, options)
end

-- Cookie management
function Client:set_cookie(name, value, domain)
    self.cookies[domain] = self.cookies[domain] or {}
    self.cookies[domain][name] = value
end

function Client:get_cookie(name, domain)
    return self.cookies[domain] and self.cookies[domain][name]
end

return Client
