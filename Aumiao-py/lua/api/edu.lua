-- edu.lua
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
    self.community = require("api.community")

    motion_instance = self
    return self
end

function Motion:update_name(user_id, real_name)
    -- 获取时间戳
    local time_stamp = self.community.Obtain:get_timestamp().data

    -- 构造请求参数
    local response = self.acquire:get("https://eduzone.codemao.cn/edu/zone/account/updateName", {
        params = {
            TIME = time_stamp,
            userId = user_id,
            realName = real_name
        }
    })

    return response.status_code == 200
end

function Motion:get_teacher_info(user_id)
    local response = self.acquire:get("https://eduzone.codemao.cn/edu/zone/teacher/info", {
        params = {
            userId = user_id
        }
    })

    if response.status_code == 200 then
        return response.json
    end
    return nil
end

function Motion:get_student_info(user_id)
    local response = self.acquire:get("https://eduzone.codemao.cn/edu/zone/student/info", {
        params = {
            userId = user_id
        }
    })

    if response.status_code == 200 then
        return response.json
    end
    return nil
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

function Obtain:get_school_list()
    local response = self.acquire:get("https://eduzone.codemao.cn/edu/zone/school/list")

    if response.status_code == 200 then
        return response.json
    end
    return nil
end

function Obtain:get_class_list(school_id)
    local response = self.acquire:get("https://eduzone.codemao.cn/edu/zone/class/list", {
        params = {
            schoolId = school_id
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
