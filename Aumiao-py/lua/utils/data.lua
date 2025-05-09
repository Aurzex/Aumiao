-- data.lua
local json = require("cjson")
local lfs = require("lfs")

-- Base DataManager class
local DataManager = {}
DataManager.__index = DataManager

function DataManager:new(filename)
    local self = setmetatable({}, self)
    self.filename = filename
    self.data = self:load()
    return self
end

function DataManager:load()
    local file = io.open(self.filename, "r")
    if not file then
        return {}
    end
    local content = file:read("*all")
    file:close()

    local success, result = pcall(json.decode, content)
    return success and result or {}
end

function DataManager:save()
    local file = io.open(self.filename, "w")
    if not file then
        error("Cannot open file for writing: " .. self.filename)
    end
    file:write(json.encode(self.data))
    file:close()
end

function DataManager:update(new_data)
    for k, v in pairs(new_data) do
        self.data[k] = v
    end
    self:save()
end

function DataManager:getData()
    return self.data
end

-- Specific managers
local CacheManager = setmetatable({}, {
    __index = DataManager
})
CacheManager.__index = CacheManager

function CacheManager:create()
    return DataManager:new("data/cache.json")
end

local SettingManager = setmetatable({}, {
    __index = DataManager
})
SettingManager.__index = SettingManager

function SettingManager:create()
    return DataManager:new("data/setting.json")
end

-- Update CacheManager usage
CacheManager.new = CacheManager.create

-- Export
return {
    DataManager = DataManager,
    CacheManager = CacheManager,
    SettingManager = SettingManager
}
