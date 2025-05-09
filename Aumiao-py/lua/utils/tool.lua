-- tool.lua
local json = require("cjson")
local os = require("os")

local Tool = {}

-- String operations
function Tool.is_empty(str)
    return str == nil or str == ""
end

function Tool.random_sleep(min, max)
    min = min or 1
    max = max or 3
    local sleep_time = min + math.random() * (max - min)
    os.execute(string.format("sleep %.2f", sleep_time))
end

function Tool.format_time(timestamp)
    return os.date("%Y-%m-%d %H:%M:%S", timestamp)
end

-- File operations
function Tool.read_file(filepath)
    local file = io.open(filepath, "r")
    if not file then
        return nil
    end
    local content = file:read("*all")
    file:close()
    return content
end

function Tool.write_file(filepath, content)
    local file = io.open(filepath, "w")
    if not file then
        return false
    end
    file:write(content)
    file:close()
    return true
end

-- JSON operations
function Tool.parse_json(str)
    if Tool.is_empty(str) then
        return nil
    end
    local success, result = pcall(json.decode, str)
    return success and result or nil
end

function Tool.to_json(data)
    local success, result = pcall(json.encode, data)
    return success and result or nil
end

-- URL operations
function Tool.build_url(base_url, params)
    if not params then
        return base_url
    end

    local query = {}
    for k, v in pairs(params) do
        table.insert(query, k .. "=" .. v)
    end

    if #query == 0 then
        return base_url
    end

    return base_url .. "?" .. table.concat(query, "&")
end

-- Error handling
function Tool.safe_call(func, ...)
    local success, result = pcall(func, ...)
    if not success then
        -- Log error
        print(string.format("Error: %s", result))
        return nil
    end
    return result
end

return Tool
